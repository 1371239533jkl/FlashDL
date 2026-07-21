# -*- coding: utf-8 -*-
"""下载任务模块 - 管理单个下载任务的完整生命周期"""

import json
import os
import sys
import time
import uuid
from pathlib import Path
from PyQt6.QtCore import QTimer, pyqtSignal

import config
from core.base_task import BaseDownloadTask
from core.download_worker import DownloadWorker
from core.url_validator import validate_url
from utils.format_utils import ensure_long_path
from utils.format_utils import format_size, format_speed, format_time
from utils.logger import get_logger

_log = get_logger('download_task')


class DownloadTask(BaseDownloadTask):
    """单个下载任务，协调多个DownloadWorker完成分块下载

    架构：直接写入输出文件，跳过临时文件和合并阶段。
    - prepare() 时预分配文件大小（truncate）
    - 每个 worker 直接 seek+write 到最终文件的对应偏移
    - 天然支持边下边播（下载期间文件即可被播放器打开）
    """

    # 信号
    progress_updated = pyqtSignal(str, dict)
    status_changed = pyqtSignal(str, str)
    completed = pyqtSignal(str, str)
    failed = pyqtSignal(str, str)

    STREAM_PLAY_MIN_PROGRESS = 5

    def __init__(self, url: str, save_dir: str, file_name: str = '',
                 thread_count: int = config.DEFAULT_THREAD_COUNT,
                 task_id: str = None, headers: dict = None):
        super().__init__(url, ensure_long_path(save_dir), file_name, task_id)
        self.thread_count = thread_count
        self.headers = headers or {}
        self.supports_range = False

        self.chunks = []
        self._workers = []

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_progress)

        self._state_dir = ensure_long_path(os.path.join(config.TEMP_DIR, self.task_id))

    def prepare(self) -> bool:
        """
        准备下载: 验证URL、获取文件信息、预创建输出文件、划分分块。
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

        # 预创建输出文件（预分配空间）
        save_path = self.save_path
        os.makedirs(self.save_dir, exist_ok=True)

        # 处理文件名冲突
        if os.path.exists(save_path):
            base, ext = os.path.splitext(self.file_name)
            counter = 1
            while os.path.exists(save_path):
                self.file_name = f"{base}({counter}){ext}"
                save_path = self.save_path
                counter += 1

        if self.total_size > 0:
            # 检查磁盘剩余空间（保留 100MB 缓冲）
            import shutil
            free_space = shutil.disk_usage(self.save_dir).free
            if free_space < self.total_size + 100 * 1024 * 1024:
                self.error_message = f'磁盘空间不足（需要 {format_size(self.total_size)}，可用 {format_size(free_space)}）'
                self._set_status(self.FAILED)
                return False
            # 预分配文件空间（稀疏文件，不占实际磁盘空间）
            # 仅在新任务或文件不存在时执行
            if not os.path.exists(save_path) or os.path.getsize(save_path) < self.total_size:
                try:
                    with open(save_path, 'wb') as f:
                        f.seek(self.total_size - 1)
                        f.write(b'\0')
                except OSError as e:
                    self.error_message = f'写入文件失败: {e}'
                    self._set_status(self.FAILED)
                    return False
        else:
            # 大小未知时创建空文件
            if not os.path.exists(save_path):
                open(save_path, 'wb').close()

        # 划分分块

        os.makedirs(self._state_dir, exist_ok=True)
        self._create_chunks()
        self.is_prepared = True
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
        self._speed_clear()


        # 检查是否有已停止的worker需要重新启动
        active_workers = [w for w in self._workers if w.isRunning()]
        if active_workers:
            for w in active_workers:
                w.resume()
        else:
            self._start_workers()
        self._timer.start(config.UI_UPDATE_INTERVAL)

    def cancel(self):
        """取消下载，保留已下载的输出文件"""
        self._timer.stop()
        self._stop_workers()
        # 清理状态文件，但保留输出文件（用户可手动删除）
        self._cleanup_state_dir(self._state_dir)
        self._set_status(self.FAILED)

    def retry(self) -> bool:
        """
        重试下载（断点续传）。
        基于输出文件已有大小恢复已下载量。
        返回是否可重试。
        """
        if self.status != self.FAILED:
            return False

        self._timer.stop()
        self._stop_workers()

        # 基于输出文件验证已下载的字节
        save_path = self.save_path
        if os.path.exists(save_path) and self.total_size > 0:
            actual_size = os.path.getsize(save_path)
            # 重新计算各分块的 downloaded_bytes
            for chunk in self.chunks:
                expected_end = min(chunk['end_byte'] + 1, actual_size) if chunk['end_byte'] >= 0 else actual_size
                already = max(0, expected_end - chunk['start_byte'])
                chunk['downloaded_bytes'] = already
            self.downloaded_size = actual_size

        # 重置失败分块，保留已完成分块
        for chunk in self.chunks:
            if chunk['status'] != 'completed':
                chunk['status'] = 'pending'

        self.error_message = ''
        self._speed_samples.clear()
        self._last_sample_size = self.downloaded_size
        self._last_sample_time = 0
        self._set_status(self.WAITING)
        self._save_state()
        return True

    def _create_chunks(self):
        """根据线程数划分下载分块（不再使用临时文件）"""
        self.chunks = []
        if self.total_size <= 0:
            # 文件大小未知，单块顺序下载
            self.chunks.append({
                'chunk_id': 0,
                'start_byte': 0,
                'end_byte': -1,
                'downloaded_bytes': 0,
                'status': 'pending',
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
            })

    def _start_workers(self):
        """为未完成的分块创建并启动工作线程"""
        self._stop_workers()
        # 等待旧线程真正退出后再创建新线程，避免 QThread 重复 start 崩溃
        for w in self._workers:
            if w.isRunning():
                w.wait(3000)
        self._workers = []

        # 计算每个 worker 的限速（总限速 / 活跃 worker 数）
        pending_chunks = [c for c in self.chunks if c['status'] != 'completed']
        active_count = len(pending_chunks)
        from config import get_speed_limit
        total_limit = get_speed_limit()
        per_worker_limit = (total_limit // active_count) if (total_limit > 0 and active_count > 0) else 0

        for chunk in self.chunks:
            if chunk['status'] == 'completed':
                continue
            worker = DownloadWorker(
                chunk_id=chunk['chunk_id'],
                url=self.url,
                output_path=self.save_path,
                start_byte=chunk['start_byte'],
                end_byte=chunk['end_byte'],
                downloaded_bytes=chunk['downloaded_bytes'],
                headers=self.headers,
                speed_limit=per_worker_limit
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
            w.wait(1000)

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
            self._stop_workers()
            # 直接标记完成（无需合并）
            self._cleanup_state_dir(self._state_dir)
            self._set_status(self.COMPLETED)
            self.completed.emit(self.task_id, self.save_path)

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

    def _update_progress(self):
        avg_speed = self._sample_speed()
        self._emit_progress(avg_speed)

    def _save_state(self):
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
            'headers': self.headers,
        }
        self._atomic_json_write(state, self._state_dir)

    @classmethod
    def load_from_state(cls, task_dir: str) -> 'DownloadTask':
        """从保存的状态文件恢复任务"""
        state_file = os.path.join(task_dir, 'task.json')
        if not os.path.exists(state_file):
            return None

        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
        except Exception as e:
            _log.warning(f'任务状态文件无法读取: {state_file} - {e}')
            return None

        task = cls(
            url=state['url'],
            save_dir=state['save_dir'],
            file_name=state['file_name'],
            thread_count=state['thread_count'],
            task_id=state['task_id'],
            headers=state.get('headers', {})
        )
        task.total_size = state['total_size']
        task.downloaded_size = state['downloaded_size']
        task.supports_range = state.get('supports_range', False)
        task.created_time = state.get('created_time', '')
        task.chunks = state.get('chunks', [])
        task.is_prepared = True
        task.status = task.PAUSED  # 恢复时始终为暂停状态

        # 验证输出文件完整性（替代旧的 temp_file 检测）
        save_path = task.save_path
        if os.path.exists(save_path) and task.total_size > 0:
            actual_size = os.path.getsize(save_path)
            # 重新校准分块的 downloaded_bytes
            for chunk in task.chunks:
                expected_end = min(chunk['end_byte'] + 1, actual_size) if chunk['end_byte'] >= 0 else actual_size
                already = max(0, expected_end - chunk['start_byte'])
                chunk['downloaded_bytes'] = already

        # 重新计算已下载总量
        task.downloaded_size = sum(c['downloaded_bytes'] for c in task.chunks)
        return task

    def _cleanup_state(self):
        """清理状态文件目录（委托基类）"""
        self._cleanup_state_dir(self._state_dir)
