# -*- coding: utf-8 -*-
"""磁力链接下载任务 - 基于 libtorrent 的 BT 下载任务类"""

import base64
import json
import os
import time
import uuid
from collections import deque
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

import config
from core.magnet_session_manager import MagnetSessionManager, is_libtorrent_available
from core.url_validator import validate_url
from utils.format_utils import format_size, format_speed, format_time, ensure_long_path
from utils.logger import get_logger

_log = get_logger('magnet_task')

if is_libtorrent_available():
    import libtorrent as lt


class MagnetDownloadTask(QObject):
    """磁力链接下载任务，与 DownloadTask 具有相同的信号接口"""

    # 信号(与 DownloadTask 完全一致)
    progress_updated = pyqtSignal(str, dict)    # (task_id, progress_info)
    status_changed = pyqtSignal(str, str)       # (task_id, new_status)
    completed = pyqtSignal(str, str)            # (task_id, file_path)
    failed = pyqtSignal(str, str)               # (task_id, error)

    # 任务状态常量(兼容 DownloadTask + 新增元数据解析状态)
    WAITING = 'waiting'
    RESOLVING_METADATA = 'resolving_metadata'
    DOWNLOADING = 'downloading'
    PAUSED = 'paused'
    COMPLETED = 'completed'
    FAILED = 'failed'

    def __init__(self, url: str, save_dir: str, file_name: str = '',
                 task_id: str = None):
        super().__init__()
        self.task_id = task_id or str(uuid.uuid4())[:8]
        self.url = url
        self.save_dir = ensure_long_path(save_dir)
        self.file_name = file_name
        self.total_size = -1
        self.downloaded_size = 0
        self.thread_count = 0  # BT下载不使用线程数概念，但保持接口兼容
        self.status = self.WAITING
        self.error_message = ''
        self.created_time = time.strftime('%Y-%m-%d %H:%M:%S')

        self._handle = None  # libtorrent torrent_handle
        self._session_mgr = MagnetSessionManager.get_instance()
        self._metadata_resolved = False
        self._metadata_start_time = 0
        self._speed_samples = deque(maxlen=config.SPEED_WINDOW_SIZE)
        self._last_sample_size = 0
        self._last_sample_time = 0
        self._handle_invalid_count = 0  # handle 连续失效次数

        # 进度轮询定时器
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_progress)

        # 任务临时目录
        self._temp_dir = ensure_long_path(os.path.join(config.MAGNET_TEMP_DIR, self.task_id))

    @property
    def save_path(self) -> str:
        return os.path.join(self.save_dir, self.file_name)

    @property
    def progress(self) -> float:
        if self.total_size <= 0:
            return 0.0
        return min(self.downloaded_size / self.total_size * 100, 100.0)

    @property
    def streamable(self) -> bool:
        """是否可边下边播（下载中或暂停均可）"""
        return (self.status in (self.DOWNLOADING, self.PAUSED)
                and self.total_size > 0
                and self.progress >= 5     # 最低 5%
                and os.path.exists(self.save_path))

    def get_info(self) -> dict:
        """获取任务当前完整信息(与 DownloadTask.get_info 格式一致)"""
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
        """准备下载: 验证磁力链接、添加到 session"""
        info = validate_url(self.url)
        if not info['valid']:
            self.error_message = info['error']
            self._set_status(self.FAILED)
            return False

        if not self.file_name:
            self.file_name = info['file_name']

        # 确保 session 已初始化
        if not self._session_mgr.initialized:
            self._session_mgr.initialize()

        try:
            os.makedirs(self.save_dir, exist_ok=True)
            self._handle = self._session_mgr.add_magnet(self.url, self.save_dir)
        except Exception as e:
            self.error_message = f'添加磁力链接失败: {e}'
            self._set_status(self.FAILED)
            return False

        self._metadata_start_time = time.time()
        os.makedirs(self._temp_dir, exist_ok=True)
        self._save_state()
        return True

    def start(self):
        """启动/恢复下载"""
        if self.status == self.COMPLETED:
            return
        if self._handle and self._handle.is_valid():
            self._handle.resume()

        if self._metadata_resolved:
            self._set_status(self.DOWNLOADING)
        else:
            self._set_status(self.RESOLVING_METADATA)
            self._metadata_start_time = time.time()

        self._last_sample_size = self.downloaded_size
        self._last_sample_time = time.time()
        self._timer.start(config.BT_POLL_INTERVAL)

    def pause(self):
        """暂停下载"""
        if self.status not in (self.DOWNLOADING, self.RESOLVING_METADATA):
            return
        self._timer.stop()
        if self._handle and self._handle.is_valid():
            self._handle.pause()
            self._save_resume_data()  # 暂停时保存断点数据（用户操作，可接受短暂阻塞）
        self._set_status(self.PAUSED)

    def resume(self):
        """恢复下载"""
        if self.status != self.PAUSED:
            return
        if self._handle and self._handle.is_valid():
            self._handle.resume()

        if self._metadata_resolved:
            self._set_status(self.DOWNLOADING)
        else:
            self._set_status(self.RESOLVING_METADATA)
            self._metadata_start_time = time.time()

        self._last_sample_size = self.downloaded_size
        self._last_sample_time = time.time()
        self._speed_samples.clear()
        self._timer.start(config.BT_POLL_INTERVAL)

    def cancel(self):
        """取消下载，清理文件"""
        self._timer.stop()
        if self._handle and self._handle.is_valid():
            self._session_mgr.remove_torrent(self._handle, delete_files=True)
            self._handle = None
        self._cleanup_temp()
        self._set_status(self.FAILED)

    def _update_progress(self):
        """定时轮询 torrent 状态并更新进度"""
        if not self._handle or not self._handle.is_valid():
            self._handle_invalid_count += 1
            if self._handle_invalid_count >= 10:  # 连续10次(约5秒)无效则标记失败
                self._timer.stop()
                self.error_message = '种子连接已断开'
                self._set_status(self.FAILED)
                self.failed.emit(self.task_id, self.error_message)
            return

        self._handle_invalid_count = 0  # 恢复后重置计数

        try:
            status = self._handle.status()
        except Exception as e:
            _log.warning(f'获取种子状态失败: {self.task_id} - {e}')
            self._handle_invalid_count += 1
            if self._handle_invalid_count >= 10:
                self._timer.stop()
                self.error_message = '种子连接已断开'
                self._set_status(self.FAILED)
                self.failed.emit(self.task_id, self.error_message)
            return

        # 元数据解析检查
        if not self._metadata_resolved:
            if status.has_metadata:
                self._on_metadata_resolved()
            else:
                # 检查解析超时
                elapsed = time.time() - self._metadata_start_time
                if elapsed > config.BT_METADATA_TIMEOUT:
                    self._timer.stop()
                    self.error_message = '元数据解析超时，请检查磁力链接或网络连接'
                    self._set_status(self.FAILED)
                    self.failed.emit(self.task_id, self.error_message)
                    return
                # 解析中的进度信息
                progress_info = {
                    'task_id': self.task_id,
                    'downloaded_size': 0,
                    'total_size': -1,
                    'progress': 0,
                    'speed': 0,
                    'speed_text': '解析元数据...',
                    'remaining_time': '--:--',
                    'downloaded_text': '0 B',
                    'total_text': '未知',
                    'peer_count': status.num_peers,
                    'seed_count': status.num_seeds,
                    'status': self.status,
                }
                self.progress_updated.emit(self.task_id, progress_info)
                return

        # 更新下载量
        self.downloaded_size = status.total_done
        self.total_size = status.total_wanted if status.total_wanted > 0 else self.total_size

        # 速度采样
        now = time.time()
        elapsed = now - self._last_sample_time
        if elapsed >= config.SPEED_SAMPLE_INTERVAL:
            bytes_delta = self.downloaded_size - self._last_sample_size
            speed = bytes_delta / elapsed if elapsed > 0 else 0
            self._speed_samples.append(speed)
            self._last_sample_size = self.downloaded_size
            self._last_sample_time = now

        avg_speed = sum(self._speed_samples) / len(self._speed_samples) if self._speed_samples else 0
        remaining = (self.total_size - self.downloaded_size) / avg_speed if avg_speed > 0 and self.total_size > 0 else float('inf')

        progress_info = {
            'task_id': self.task_id,
            'downloaded_size': self.downloaded_size,
            'total_size': self.total_size,
            'progress': self.progress,
            'speed': status.download_rate,
            'speed_text': format_speed(status.download_rate),
            'remaining_time': format_time(remaining),
            'downloaded_text': format_size(self.downloaded_size),
            'total_text': format_size(self.total_size) if self.total_size > 0 else '未知',
            'peer_count': status.num_peers,
            'seed_count': status.num_seeds,
            'status': self.status,
        }
        self.progress_updated.emit(self.task_id, progress_info)

        # 检查是否下载完成
        if status.is_seeding or (self.total_size > 0 and self.downloaded_size >= self.total_size):
            self._on_download_completed()

    def _on_metadata_resolved(self):
        """元数据解析完成，获取真实文件信息"""
        self._metadata_resolved = True
        try:
            torrent_info = self._handle.torrent_file()
            if torrent_info:
                name = torrent_info.name()
                if name:
                    self.file_name = name
                self.total_size = torrent_info.total_size()
            else:
                _log.warning(f'磁力元数据无效: {self.task_id}')
        except Exception as e:
            _log.warning(f'解析磁力元数据失败: {self.task_id} - {e}')
            # 保持默认值（已初始化的空文件名/unknown大小）

        self._set_status(self.DOWNLOADING)
        self._save_state()
        # 通知 UI 更新文件名和大小
        from utils.signal_bus import signal_bus
        signal_bus.task_created.emit(self.task_id, self.get_info())

    def _on_download_completed(self):
        """下载完成处理"""
        self._timer.stop()

        # 确定最终文件路径（处理多文件种子）
        try:
            if self._handle and self._handle.is_valid():
                ti = self._handle.torrent_file()
                if ti and ti.num_files() > 1:
                    # 多文件种子：文件在 save_dir/torrent_name/ 子目录下
                    file_path = os.path.join(self.save_dir, ti.name())
                else:
                    file_path = os.path.join(self.save_dir, self.file_name)
            else:
                file_path = os.path.join(self.save_dir, self.file_name)
        except Exception:
            file_path = os.path.join(self.save_dir, self.file_name)

        self._cleanup_temp()
        self._set_status(self.COMPLETED)
        self.completed.emit(self.task_id, file_path)

    def _set_status(self, status: str):
        self.status = status
        self.status_changed.emit(self.task_id, status)

    def _save_state(self):
        """保存任务状态到JSON文件(非阻塞，不获取resume_data)"""
        state = {
            'task_type': 'magnet',
            'task_id': self.task_id,
            'url': self.url,
            'file_name': self.file_name,
            'save_dir': self.save_dir,
            'total_size': self.total_size,
            'downloaded_size': self.downloaded_size,
            'status': self.status,
            'created_time': self.created_time,
            'metadata_resolved': self._metadata_resolved,
        }
        os.makedirs(self._temp_dir, exist_ok=True)
        tmp_path = os.path.join(self._temp_dir, 'task.json.tmp')
        final_path = os.path.join(self._temp_dir, 'task.json')
        try:
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, final_path)
        except Exception as e:
            _log.warning(f'磁力任务状态保存失败: {self.task_id} - {e}')

    def _save_resume_data(self):
        """保存 BT 断点续传数据（可能有短暂阻塞，仅在暂停时调用）"""
        if not self._handle or not self._handle.is_valid() or not self._metadata_resolved:
            return
        try:
            rd = self._session_mgr.get_resume_data(self._handle)
            if not rd:
                return
            resume_data_b64 = base64.b64encode(rd).decode('ascii')
            # 读取已有状态，追加 resume_data 后写回
            state_file = os.path.join(self._temp_dir, 'task.json')
            if os.path.exists(state_file):
                with open(state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                state['resume_data'] = resume_data_b64
                tmp_path = state_file + '.tmp'
                with open(tmp_path, 'w', encoding='utf-8') as f:
                    json.dump(state, f, ensure_ascii=False, indent=2)
                os.replace(tmp_path, state_file)
        except Exception as e:
            _log.warning(f'断点数据保存失败: {self.task_id} - {e}')

    @classmethod
    def load_from_state(cls, task_dir: str) -> 'MagnetDownloadTask':
        """从保存的状态文件恢复磁力下载任务"""
        state_file = os.path.join(task_dir, 'task.json')
        if not os.path.exists(state_file):
            return None

        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
        except Exception as e:
            _log.warning(f'磁力任务状态文件损坏: {state_file} - {e}')
            return None

        if state.get('task_type') != 'magnet':
            return None

        task = cls(
            url=state['url'],
            save_dir=state['save_dir'],
            file_name=state.get('file_name', ''),
            task_id=state['task_id']
        )
        task.total_size = state.get('total_size', -1)
        task.downloaded_size = state.get('downloaded_size', 0)
        task.created_time = state.get('created_time', '')
        task._metadata_resolved = state.get('metadata_resolved', False)
        task.status = task.PAUSED  # 恢复时始终为暂停状态

        # 恢复 torrent handle
        session_mgr = MagnetSessionManager.get_instance()
        if not session_mgr.initialized:
            session_mgr.initialize()

        resume_data_b64 = state.get('resume_data', '')
        try:
            if resume_data_b64:
                rd = base64.b64decode(resume_data_b64)
                task._handle = session_mgr.add_torrent_from_resume(rd, task.save_dir)
            else:
                task._handle = session_mgr.add_magnet(task.url, task.save_dir)

            if task._handle and task._handle.is_valid():
                task._handle.pause()  # 恢复后先暂停
            else:
                task.error_message = '无法恢复种子连接，请重新添加'
                task._set_status(task.FAILED)
        except Exception as e:
            _log.warning(f'磁力任务恢复失败: {task.task_id} - {e}')
            task.error_message = f'恢复失败: {e}'
            task._set_status(task.FAILED)

        return task

    def _cleanup_temp(self):
        """清理临时状态文件"""
        import shutil
        try:
            if os.path.exists(self._temp_dir):
                shutil.rmtree(self._temp_dir)
        except Exception:
            pass
