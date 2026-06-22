# -*- coding: utf-8 -*-
"""后台任务 Worker — 将耗时操作移出主线程，避免 UI 卡顿"""

from PyQt6.QtCore import QThread, pyqtSignal
from utils.logger import get_logger

_log = get_logger('task_worker')


class PrepareWorker(QThread):
    """后台执行 task.prepare()，完成后发信号

    用于磁力链接 session 初始化、HTTP URL 验证等耗时操作。
    """
    prepared = pyqtSignal(str, dict)   # task_id, info
    failed = pyqtSignal(str, str)      # task_id, error

    def __init__(self, task, parent=None):
        super().__init__(parent)
        self._task = task

    def run(self):
        task_id = self._task.task_id
        try:
            ok = self._task.prepare()
            if ok:
                self.prepared.emit(task_id, self._task.get_info())
            else:
                self.failed.emit(task_id, self._task.error_message or 'prepare() 返回 False')
        except Exception as e:
            _log.error(f'PrepareWorker 异常: {e}')
            self.failed.emit(task_id, str(e))


class CleanupWorker(QThread):
    """后台执行任务清理（cancel + 删除临时文件）

    用于任务取消/移除时的 _stop_workers / remove_torrent / shutil.rmtree 等耗时操作。
    """
    cleaned = pyqtSignal(str)  # task_id

    def __init__(self, task, parent=None):
        super().__init__(parent)
        self._task = task

    def run(self):
        task_id = self._task.task_id
        try:
            if self._task.status != 'completed':
                self._task.cancel()
        except Exception as e:
            _log.warning(f'CleanupWorker 清理异常 ({task_id}): {e}')
        self.cleaned.emit(task_id)
