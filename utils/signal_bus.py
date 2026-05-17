# -*- coding: utf-8 -*-
"""全局信号总线 - 用于模块间解耦通信"""

from PyQt6.QtCore import QObject, pyqtSignal


class _SignalBus(QObject):
    """全局信号总线单例，跨模块传递信号"""

    # 下载相关信号
    task_created = pyqtSignal(str, dict)            # (task_id, task_info)
    task_progress = pyqtSignal(str, dict)            # (task_id, progress_data)
    task_status_changed = pyqtSignal(str, str)       # (task_id, new_status)
    task_completed = pyqtSignal(str, str)            # (task_id, file_path)
    task_failed = pyqtSignal(str, str)               # (task_id, error_message)

    # 播放器相关信号
    play_video = pyqtSignal(str)                     # (file_path)

    # UI相关信号
    show_notification = pyqtSignal(str, str)         # (title, message)


# 全局单例
signal_bus = _SignalBus()
