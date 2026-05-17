# -*- coding: utf-8 -*-
"""下载任务模块 - 管理单个下载任务的完整生命周期"""

import json
import os
import sys
import time
import uuid
from collections import deque
from pathlib import Path
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

import config
from core.download_worker import DownloadWorker
from core.url_validator import validate_url
from utils.format_utils import ensure_long_path
from utils.format_utils import format_size, format_speed, format_time


class DownloadTask(QObject):
    """单个下载任务，协调多个DownloadWorker完成分块下载"""

    # 信号
    progress_updated = pyqtSignal(str, dict)    # (task_id, progress_info)
    status_changed = pyqtSignal(str, str)       # (task_id, new_status)
    completed = pyqtSignal(str, str)            # (task_id, file_path)
    failed = pyqtSignal(str, str)               # (task_id, error)

    # 任务状态常量
    WAITING = 'waiting'
    DOWNLOADING = 'downloading'
    PAUSED = 'paused'
    MERGING = 'merging'
    COMPLETED = 'completed'
    FAILED = 'failed'

    def __init__(self, url: str, save_dir: str, file_name: str = '',
                 thread_count: int = config.DEFAULT_THREAD_COUNT,
                 task_id: str = None, headers: dict = None):
        super().__init__()
        self.task_id = task_id or str(uuid.uuid4())[:8]
        self.url = url
        self.save_dir = ensure_long_path(save_dir)
        self.file_name = file_name
        self.thread_count = thread_count
        self.headers = headers or {}
        self.total_size = -1
        self.downloaded_size = 0
        self.supports_range = False
        self.status = self.WAITING
        self.error_message = ''
        self.created_time = time.strftime('%Y-%m-%d %H:%M:%S')

        self.chunks = []           # 分块信息列表
        self._workers = []         # 工作线程列表
        self._speed_samples = deque(maxlen=config.SPEED_WINDOW_SIZE)
        self._last_sample_size = 0
        self._last_sample_time = 0

        # 进度更新定时器
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_progress)

        # 任务临时目录
        self._temp_dir = ensure_long_path(os.path.join(config.TEMP_DIR, self.task_id))

    @property
    def save_path(self) -> str:
        return os.path.join(self.save_dir, self.file_name)

    @property
    def progress(self) -> float:
        if self.total_size <= 0:
            return 0.0
        return min(self.downloaded_size / self.total_size * 100, 100.0)

    def get_info(self) -> dict:
        """获取任务当前完整信息"""
        return {
            'task_id': self.task_id,
            'url': self.url,
            'file_name': self.file_name,
            'save_dir': self.save_dir,
            'total_size': self.total_size,
            'downloaded_size': self.downloaded_size,
            'thread_count': self.thread_count,
            'status': self.status,
            'progress': self.progress,
            'created_time': self.created_time,
        }

    def prepare(self) -> bool:
        """
        准备下载: 验证URL、获取文件信息、划分分块。
        返回是否成功。
        """
        info = validate_url(self.url, headers=self.headers)
        if not info['valid']:
            self.error_message = info['error']
            self._set_status(self.FAILED)
            return False

        if not self.file_name:
            self.file_name = info['file_name']
        self.total_size = info['file_size']
        self.supports_range = info['supports_range']

        # 不支持Range或文件大小未知时降级为单线程
        if not self.supports_range or self.total_size <= 0:
            self.thread_count = 1

        # 划分分块
        os.makedirs(self._temp_dir, exist_ok=True)
        self._create_chunks()
        self._save_state()
        return True

    def start(self):
        """启动下载"""
        if self.status in (self.COMPLETED, self.MERGING):
            return
        self._set_status(self.DOWNLOADING)
        self._last_sample_size = self.downloaded_size
        self._last_sample_time = time.time()
        self._start_workers()
        self._timer.start(config.UI_UPDATE_INTERVAL)

    def pause(self):
        """暂停下载"""
        if self.status != self.DOWNLOADING:
            return
        self._set_status(self.PAUSED)
        self._timer.stop()
        for w in self._workers:
            w.pause()
        self._save_state()

    def resume(self):
        """恢复下载"""
        if self.status != self.PAUSED:
            return
        self._set_status(self.DOWNLOADING)
        self._last_sample_size = self.downloaded_size
        self._last_sample_time = time.time()
        self._speed_samples.clear()

        # 检查是否有已停止的worker需要重新启动
        active_workers = [w for w in self._workers if w.isRunning()]
        if active_workers:
            for w in active_workers:
                w.resume()
        else:
            self._start_workers()
        self._timer.start(config.UI_UPDATE_INTERVAL)

    def cancel(self):
        """取消下载，清理临时文件"""
        self._timer.stop()
        self._stop_workers()
        self._cleanup_temp()
        self._set_status(self.FAILED)

    def retry(self) -> bool:
        """
        重试下载（断点续传）。
        重置失败分块的状态为 pending，保留已完成分块的临时文件。
        返回是否可重试。
        """
        if self.status != self.FAILED:
            return False

        self._timer.stop()
        self._stop_workers()

        # 重置失败分块，保留已完成分块
        for chunk in self.chunks:
            if chunk['status'] != 'completed':
                chunk['status'] = 'pending'
                # 验证临时文件的实际大小
                temp_file = chunk['temp_file']
                if os.path.exists(temp_file):
                    actual = os.path.getsize(temp_file)
                    chunk['downloaded_bytes'] = actual
                else:
                    chunk['downloaded_bytes'] = 0

        # 重新计算已下载总量
        self.downloaded_size = sum(c['downloaded_bytes'] for c in self.chunks
                                   if c['status'] == 'completed' or os.path.exists(c['temp_file']))

        self.error_message = ''
        self._speed_samples.clear()
        self._last_sample_size = self.downloaded_size
        self._last_sample_time = 0
        self._set_status(self.WAITING)
        self._save_state()
        return True

    def _create_chunks(self):
        """根据线程数划分下载分块"""
        self.chunks = []
        if self.total_size <= 0:
            # 文件大小未知，单块下载
            self.chunks.append({
                'chunk_id': 0,
                'start_byte': 0,
                'end_byte': -1,  # 未知终止位置
                'downloaded_bytes': 0,
                'status': 'pending',
                'temp_file': os.path.join(self._temp_dir, 'chunk_0.tmp')
            })
            return

        chunk_size = self.total_size // self.thread_count
        for i in range(self.thread_count):
            start = i * chunk_size
            end = (i + 1) * chunk_size - 1 if i < self.thread_count - 1 else self.total_size - 1
            self.chunks.append({
                'chunk_id': i,
                'start_byte': start,
                'end_byte': end,
                'downloaded_bytes': 0,
                'status': 'pending',
                'temp_file': os.path.join(self._temp_dir, f'chunk_{i}.tmp')
            })

    def _start_workers(self):
        """为未完成的分块创建并启动工作线程"""
        self._stop_workers()
        self._workers = []

        for chunk in self.chunks:
            if chunk['status'] == 'completed':
                continue
            worker = DownloadWorker(
                chunk_id=chunk['chunk_id'],
                url=self.url,
                temp_file=chunk['temp_file'],
                start_byte=chunk['start_byte'],
                end_byte=chunk['end_byte'],
                downloaded_bytes=chunk['downloaded_bytes'],
                headers=self.headers
            )
            worker.chunk_progress.connect(self._on_chunk_progress)
            worker.chunk_completed.connect(self._on_chunk_completed)
            worker.chunk_error.connect(self._on_chunk_error)
            self._workers.append(worker)
            worker.start()

    def _stop_workers(self):
        """停止所有工作线程"""
        for w in self._workers:
            w.stop()
        for w in self._workers:
            w.wait(3000)

    def _on_chunk_progress(self, chunk_id: int, new_bytes: int):
        """分块下载进度回调"""
        if chunk_id < len(self.chunks):
            self.chunks[chunk_id]['downloaded_bytes'] += new_bytes
            self.downloaded_size += new_bytes

    def _on_chunk_completed(self, chunk_id: int):
        """分块下载完成回调"""
        if chunk_id < len(self.chunks):
            self.chunks[chunk_id]['status'] = 'completed'

        # 检查是否所有分块都已完成
        if all(c['status'] == 'completed' for c in self.chunks):
            self._timer.stop()
            self._set_status(self.MERGING)
            self._merge_chunks()

    def _on_chunk_error(self, chunk_id: int, error: str):
        """分块下载出错回调（不停止其他下载中的分块）"""
        if chunk_id < len(self.chunks):
            self.chunks[chunk_id]['status'] = 'failed'
        self.error_message = error

        # 检查是否所有分块都已失败（没有还能下载的了）
        remaining = sum(1 for c in self.chunks if c['status'] not in ('completed', 'failed'))
        if remaining == 0:
            self._timer.stop()
            self._stop_workers()
            self._save_state()
            self._set_status(self.FAILED)
            self.failed.emit(self.task_id, error)

    def _merge_chunks(self):
        """合并所有分块为最终文件"""
        try:
            os.makedirs(self.save_dir, exist_ok=True)
            save_path = self.save_path

            # 处理文件名冲突
            if os.path.exists(save_path):
                base, ext = os.path.splitext(self.file_name)
                counter = 1
                while os.path.exists(save_path):
                    self.file_name = f"{base}({counter}){ext}"
                    save_path = self.save_path
                    counter += 1

            # 验证分块完整性：检查所有 completed chunk 的临时文件是否存在
            missing_chunks = [c for c in self.chunks
                              if c['status'] == 'completed' and not os.path.exists(c['temp_file'])]
            if missing_chunks:
                ids = ', '.join(str(c['chunk_id']) for c in missing_chunks)
                raise IOError(f'分块文件丢失: [{ids}]')

            with open(save_path, 'wb') as out_file:
                for chunk in sorted(self.chunks, key=lambda c: c['chunk_id']):
                    chunk_path = chunk['temp_file']
                    if os.path.exists(chunk_path):
                        with open(chunk_path, 'rb') as chunk_file:
                            while True:
                                buf = chunk_file.read(config.CHUNK_BUFFER_SIZE * 128)
                                if not buf:
                                    break
                                out_file.write(buf)

            # 验证合并后文件大小（仅当 total_size 已知时）
            if self.total_size > 0:
                actual_size = os.path.getsize(save_path)
                if actual_size != self.total_size:
                    print(f'[警告] 文件大小不匹配: 预期 {self.total_size}, 实际 {actual_size}',
                          file=sys.stderr)

            self._cleanup_temp()
            self._set_status(self.COMPLETED)
            self.completed.emit(self.task_id, save_path)

        except Exception as e:
            self.error_message = f'文件合并失败: {e}'
            self._set_status(self.FAILED)
            self.failed.emit(self.task_id, self.error_message)

    def _update_progress(self):
        """定时更新进度信息并发送信号"""
        now = time.time()
        elapsed = now - self._last_sample_time
        if elapsed >= config.SPEED_SAMPLE_INTERVAL:
            bytes_delta = self.downloaded_size - self._last_sample_size
            speed = bytes_delta / elapsed if elapsed > 0 else 0
            self._speed_samples.append(speed)
            self._last_sample_size = self.downloaded_size
            self._last_sample_time = now

        # 计算平均速度
        avg_speed = sum(self._speed_samples) / len(self._speed_samples) if self._speed_samples else 0
        remaining = (self.total_size - self.downloaded_size) / avg_speed if avg_speed > 0 and self.total_size > 0 else float('inf')

        progress_info = {
            'task_id': self.task_id,
            'downloaded_size': self.downloaded_size,
            'total_size': self.total_size,
            'progress': self.progress,
            'speed': avg_speed,
            'speed_text': format_speed(avg_speed),
            'remaining_time': format_time(remaining),
            'downloaded_text': format_size(self.downloaded_size),
            'total_text': format_size(self.total_size) if self.total_size > 0 else '未知',
            'status': self.status,
        }
        self.progress_updated.emit(self.task_id, progress_info)

    def _set_status(self, status: str):
        self.status = status
        self.status_changed.emit(self.task_id, status)

    def _save_state(self):
        """保存任务状态到JSON文件(原子写入)"""
        state = {
            'task_type': 'http',
            'task_id': self.task_id,
            'url': self.url,
            'file_name': self.file_name,
            'save_dir': self.save_dir,
            'total_size': self.total_size,
            'downloaded_size': self.downloaded_size,
            'thread_count': self.thread_count,
            'supports_range': self.supports_range,
            'status': self.status,
            'created_time': self.created_time,
            'chunks': self.chunks,
        }
        os.makedirs(self._temp_dir, exist_ok=True)
        tmp_path = os.path.join(self._temp_dir, 'task.json.tmp')
        final_path = os.path.join(self._temp_dir, 'task.json')
        try:
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            if os.path.exists(final_path):
                os.remove(final_path)
            os.rename(tmp_path, final_path)
        except Exception:
            print(f'[警告] 任务状态保存失败: {self.task_id}', file=sys.stderr)

    @classmethod
    def load_from_state(cls, task_dir: str) -> 'DownloadTask':
        """从保存的状态文件恢复任务"""
        state_file = os.path.join(task_dir, 'task.json')
        if not os.path.exists(state_file):
            return None

        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
        except Exception:
            print(f'[警告] 任务状态文件无法读取: {state_file}', file=sys.stderr)
            return None

        task = cls(
            url=state['url'],
            save_dir=state['save_dir'],
            file_name=state['file_name'],
            thread_count=state['thread_count'],
            task_id=state['task_id']
        )
        task.total_size = state['total_size']
        task.downloaded_size = state['downloaded_size']
        task.supports_range = state.get('supports_range', False)
        task.created_time = state.get('created_time', '')
        task.chunks = state.get('chunks', [])
        task.status = task.PAUSED  # 恢复时始终为暂停状态

        # 验证临时文件完整性
        for chunk in task.chunks:
            if chunk['status'] != 'completed':
                temp_file = chunk['temp_file']
                if os.path.exists(temp_file):
                    actual_size = os.path.getsize(temp_file)
                    chunk['downloaded_bytes'] = actual_size
                else:
                    chunk['downloaded_bytes'] = 0

        # 重新计算已下载总量
        task.downloaded_size = sum(c['downloaded_bytes'] for c in task.chunks)
        return task

    def _cleanup_temp(self):
        """清理临时文件"""
        import shutil
        try:
            if os.path.exists(self._temp_dir):
                shutil.rmtree(self._temp_dir)
        except Exception:
            pass
