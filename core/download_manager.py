# -*- coding: utf-8 -*-
"""下载管理器 - 统一管理所有下载任务、任务队列与并发控制，支持 HTTP 和磁力链接"""

import json
import os
from PyQt6.QtCore import QObject

import config
from core.download_task import DownloadTask
from core.magnet_session_manager import is_libtorrent_available
from utils.signal_bus import signal_bus
from utils.settings import get as get_setting

# 磁力任务的活跃状态集合
_ACTIVE_STATUSES = {'downloading', 'resolving_metadata'}


class DownloadManager(QObject):
    """全局下载管理器"""

    def __init__(self):
        super().__init__()
        self._tasks = {}  # task_id -> DownloadTask 或 MagnetDownloadTask

    @property
    def tasks(self) -> dict:
        return self._tasks

    def create_task(self, url: str, save_dir: str, file_name: str = '',
                    thread_count: int = config.DEFAULT_THREAD_COUNT,
                    headers: dict = None):
        """
        创建下载任务(工厂模式)。
        根据 URL 协议自动创建 HTTP 任务或磁力下载任务。
        磁力链接在 libtorrent 不可用时抛出 RuntimeError。
        """
        url = url.strip()
        if url.startswith('magnet:'):
            if not is_libtorrent_available():
                raise RuntimeError(
                    '未检测到 libtorrent 库，无法下载磁力链接。\n'
                    '请使用命令安装: pip install libtorrent'
                )
            from core.magnet_download_task import MagnetDownloadTask
            task = MagnetDownloadTask(url, save_dir, file_name)
        else:
            task = DownloadTask(url, save_dir, file_name, thread_count, headers=headers)

        self._register_task(task)
        return task

    @property
    def _max_concurrent(self) -> int:
        return get_setting('max_concurrent_tasks', config.MAX_CONCURRENT_TASKS)

    def start_task(self, task_id: str) -> bool:
        """准备并启动一个任务"""
        task = self._tasks.get(task_id)
        if not task:
            return False

        if task.status == 'waiting':
            if not task.prepare():
                signal_bus.task_failed.emit(task_id, task.error_message)
                return False
            signal_bus.task_created.emit(task_id, task.get_info())

        # 检查并发限制(downloading 和 resolving_metadata 都算活跃)
        active = sum(1 for t in self._tasks.values() if t.status in _ACTIVE_STATUSES)
        if active >= self._max_concurrent:
            return False

        task.start()
        return True

    def pause_task(self, task_id: str):
        task = self._tasks.get(task_id)
        if task:
            task.pause()

    def resume_task(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task:
            return False

        active = sum(1 for t in self._tasks.values() if t.status in _ACTIVE_STATUSES)
        if active >= self._max_concurrent:
            return False

        task.resume()
        return True

    def cancel_task(self, task_id: str):
        task = self._tasks.get(task_id)
        if task:
            task.cancel()

    def retry_task(self, task_id: str) -> bool:
        """
        重试失败的任务（断点续传）。
        重置失败分块状态为 pending，保留已下载的临时文件，重新启动下载。
        """
        task = self._tasks.get(task_id)
        if not task:
            return False
        if not task.retry():
            return False
        # 使用 start_task 重新进入队列（会检查并发限制）
        return self.start_task(task_id)

    def remove_task(self, task_id: str):
        """从管理器中移除任务"""
        task = self._tasks.pop(task_id, None)
        if task:
            if task.status != 'completed':
                task.cancel()  # 未完成的任务才清理临时文件
            # 已完成的任务只从内存移除，保留已下载的文件

    def load_unfinished_tasks(self):
        """从临时目录加载所有未完成的任务(HTTP + 磁力)"""
        # 加载 HTTP 任务
        self._load_tasks_from_dir(config.TEMP_DIR)
        # 加载磁力任务
        self._load_tasks_from_dir(config.MAGNET_TEMP_DIR)

    def _load_tasks_from_dir(self, base_dir: str):
        """从指定目录加载未完成的任务"""
        if not os.path.exists(base_dir):
            return

        for name in os.listdir(base_dir):
            task_dir = os.path.join(base_dir, name)
            if not os.path.isdir(task_dir):
                continue
            state_file = os.path.join(task_dir, 'task.json')
            if not os.path.exists(state_file):
                continue
            if name in self._tasks:
                continue

            # 读取 task_type 决定用哪个类恢复
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                task_type = state.get('task_type', 'http')
            except Exception:
                continue

            task = None
            if task_type == 'magnet' and is_libtorrent_available():
                from core.magnet_download_task import MagnetDownloadTask
                task = MagnetDownloadTask.load_from_state(task_dir)
            elif task_type != 'magnet':
                task = DownloadTask.load_from_state(task_dir)

            if task:
                self._register_task(task)
                signal_bus.task_created.emit(task.task_id, task.get_info())

    def save_all_tasks(self):
        """保存所有任务状态（退出前调用）"""
        for task in self._tasks.values():
            if task.status in _ACTIVE_STATUSES:
                task.pause()  # pause() 内部会保存状态
            elif task.status == 'paused':
                if hasattr(task, '_save_state'):
                    task._save_state()  # 也刷新暂停任务的状态

    def _register_task(self, task):
        """注册任务并连接信号"""
        self._tasks[task.task_id] = task
        task.progress_updated.connect(self._on_progress)
        task.status_changed.connect(self._on_status_changed)
        task.completed.connect(self._on_completed)
        task.failed.connect(self._on_failed)

    def _on_progress(self, task_id: str, progress_info: dict):
        signal_bus.task_progress.emit(task_id, progress_info)

    def _on_status_changed(self, task_id: str, status: str):
        signal_bus.task_status_changed.emit(task_id, status)
        # 任务完成或失败时，尝试启动等待中的任务
        if status in ('completed', 'failed'):
            self._try_start_next()

    def _on_completed(self, task_id: str, file_path: str):
        signal_bus.task_completed.emit(task_id, file_path)
        signal_bus.show_notification.emit('下载完成', f'{os.path.basename(file_path)} 已下载完成')
        # 播放提示音（可通过设置关闭）
        from utils.settings import get as get_setting
        if get_setting('completion_sound', True):
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_OK)
            except Exception:
                pass

        # 检查是否需要执行下载完成后操作
        self._check_completion_action()

    def _check_completion_action(self):
        """所有活跃任务完成后执行用户设置的操作"""
        active = sum(1 for t in self._tasks.values()
                     if t.status in ('downloading', 'resolving_metadata', 'waiting'))
        if active > 0:
            return

        from utils.settings import get as get_setting
        action = get_setting('completion_action', 'none')
        if action == 'none':
            return

        import subprocess
        try:
            if action == 'shutdown':
                subprocess.Popen(['shutdown', '/s', '/t', '60'],
                                 creationflags=subprocess.CREATE_NO_WINDOW)
                signal_bus.show_notification.emit(
                    '自动关机', '所有任务已完成，60 秒后关机')
            elif action == 'hibernate':
                subprocess.Popen(['shutdown', '/h'],
                                 creationflags=subprocess.CREATE_NO_WINDOW)
            elif action == 'open_folder':
                download_dir = get_setting('download_dir', config.DEFAULT_DOWNLOAD_DIR)
                os.startfile(download_dir)
        except Exception:
            pass

    def _on_failed(self, task_id: str, error: str):
        signal_bus.task_failed.emit(task_id, error)

    def _get_queue_info(self, task_id: str) -> str:
        """获取等待任务的队列位置信息"""
        total_waiting = sum(1 for t in self._tasks.values() if t.status == 'waiting')
        if total_waiting <= 0:
            return ''
        position = 1
        for t in self._tasks.values():
            if t.task_id == task_id:
                break
            if t.status == 'waiting':
                position += 1
        return f'排队中 (第{position}/{total_waiting}位)'

    def _try_start_next(self):
        """尝试启动队列中等待的任务（尽可能填满所有空闲槽位）"""
        while True:
            active = sum(1 for t in self._tasks.values() if t.status in _ACTIVE_STATUSES)
            if active >= self._max_concurrent:
                return
            for task in self._tasks.values():
                if task.status == 'waiting':
                    self.start_task(task.task_id)
                    break
            else:
                # 没有更多等待任务了
                return
