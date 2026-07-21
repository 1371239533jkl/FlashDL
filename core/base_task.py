# -*- coding: utf-8 -*-
"""下载任务基类 — HTTP 和 BT/磁力任务共享的属性和方法"""

import json
import os
import shutil
import time
import uuid
from collections import deque

from PyQt6.QtCore import QObject

import config
from utils.format_utils import format_size, format_speed, format_time


class BaseDownloadTask(QObject):
    """HTTP 和 BT 下载任务的基类，提取共享逻辑"""

    # ── 通用状态常量 ──
    WAITING = 'waiting'
    DOWNLOADING = 'downloading'
    PAUSED = 'paused'
    MERGING = 'merging'
    COMPLETED = 'completed'
    FAILED = 'failed'

    def __init__(self, url: str, save_dir: str, file_name: str = '',
                 task_id: str = None):
        super().__init__()
        self.task_id = task_id or str(uuid.uuid4())[:8]
        self.url = url
        self.save_dir = save_dir
        self.file_name = file_name
        self.total_size = -1
        self.downloaded_size = 0
        self.status = self.WAITING
        self.error_message = ''
        self.created_time = time.strftime('%Y-%m-%d %H:%M:%S')
        self.is_prepared = False

        # 速度采样（滑动窗口）
        self._speed_samples = deque(maxlen=config.SPEED_WINDOW_SIZE)
        self._last_sample_size = 0
        self._last_sample_time = 0.0

    # ── 共享属性 ──

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
        """是否可边下边播（下载中或暂停且进度达标）"""
        return (self.status in (self.DOWNLOADING, self.PAUSED)
                and self.total_size > 0
                and self.progress >= getattr(self, 'STREAM_PLAY_MIN_PROGRESS', 5)
                and os.path.exists(self.save_path))

    def get_info(self) -> dict:
        """获取任务当前完整信息"""
        return {
            'task_id': self.task_id,
            'url': self.url,
            'file_name': self.file_name,
            'save_dir': self.save_dir,
            'total_size': self.total_size,
            'downloaded_size': self.downloaded_size,
            'thread_count': getattr(self, 'thread_count', 0),
            'status': self.status,
            'progress': self.progress,
            'created_time': self.created_time,
        }

    # ── 共享方法 ──

    def _set_status(self, status: str):
        self.status = status
        self.status_changed.emit(self.task_id, status)

    def _sample_speed(self) -> float:
        """记录速度采样点，返回当前平均速度 (bytes/s)"""
        now = time.time()
        elapsed = now - self._last_sample_time
        if elapsed >= config.SPEED_SAMPLE_INTERVAL:
            bytes_delta = self.downloaded_size - self._last_sample_size
            speed = bytes_delta / elapsed if elapsed > 0 else 0
            self._speed_samples.append(speed)
            self._last_sample_size = self.downloaded_size
            self._last_sample_time = now
        return sum(self._speed_samples) / len(self._speed_samples) if self._speed_samples else 0

    def _build_progress_info(self, avg_speed: float, **extra) -> dict:
        """构建统一的 progress_info 字典"""
        remaining = ((self.total_size - self.downloaded_size) / avg_speed
                     if avg_speed > 0 and self.total_size > 0
                     else float('inf'))
        info = {
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
        info.update(extra)
        return info

    def _emit_progress(self, avg_speed: float, **extra):
        """发射 progress_updated 信号"""
        self.progress_updated.emit(
            self.task_id, self._build_progress_info(avg_speed, **extra))

    def _cleanup_state_dir(self, dir_path: str):
        """清理状态文件目录"""
        try:
            if os.path.exists(dir_path):
                shutil.rmtree(dir_path)
        except Exception:
            pass

    def _atomic_json_write(self, data: dict, dir_path: str):
        """原子写入 JSON 状态文件"""
        os.makedirs(dir_path, exist_ok=True)
        tmp_path = os.path.join(dir_path, 'task.json.tmp')
        final_path = os.path.join(dir_path, 'task.json')
        try:
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, final_path)
        except Exception as e:
            import traceback
            traceback.print_exc()

    def _speed_clear(self):
        """重置速度采样"""
        self._speed_samples.clear()
        self._last_sample_size = 0
        self._last_sample_time = 0.0
