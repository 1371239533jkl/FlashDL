# -*- coding: utf-8 -*-
"""下载时间窗口调度器。"""

from datetime import datetime

from PyQt6.QtCore import QObject, QTimer

from utils.settings import get as get_setting


class DownloadScheduler(QObject):
    """按用户设置的每日时间窗口暂停或继续下载队列。"""

    def __init__(self, manager):
        super().__init__(manager)
        self._manager = manager
        self._paused_by_schedule = set()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.apply)
        self._timer.start(30_000)

    @staticmethod
    def _in_window(start: str, end: str, now: str) -> bool:
        if start == end:
            return True
        if start < end:
            return start <= now < end
        return now >= start or now < end

    def downloads_allowed(self) -> bool:
        if not get_setting('schedule_enabled', False):
            return True
        now = datetime.now().strftime('%H:%M')
        return self._in_window(
            get_setting('schedule_start_time', '02:00'),
            get_setting('schedule_end_time', '06:00'), now)

    def refresh(self):
        """设置保存后立即应用新的时间窗口。"""
        self.apply()

    def apply(self):
        if self.downloads_allowed():
            for task_id in tuple(self._paused_by_schedule):
                task = self._manager.tasks.get(task_id)
                if task and task.status == task.PAUSED:
                    self._manager.resume_task(task_id)
                self._paused_by_schedule.discard(task_id)
            self._manager._try_start_next()
            return

        for task_id, task in self._manager.tasks.items():
            if task.status == 'downloading':
                self._paused_by_schedule.add(task_id)
                self._manager.pause_task(task_id)
