# -*- coding: utf-8 -*-
"""下载管理标签页 - URL输入、下载列表、进度显示、操作按钮"""

import os
import re
import subprocess
import time
from collections import deque
from PyQt6.QtCore import Qt, QMimeData, QPoint, QTimer
from PyQt6.QtGui import QDrag, QPaintEvent, QPainter, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QFileDialog, QProgressBar,
    QScrollArea, QFrame, QMessageBox, QPlainTextEdit, QApplication, QMenu
)

import config
from core.download_manager import DownloadManager
from core.download_task import DownloadTask
from data.database import Database
from utils.format_utils import format_size
from utils.signal_bus import signal_bus
from utils.settings import get as get_setting, set_value as set_setting
from ui.styles import get_tokens


class TaskCard(QFrame):
    """单个下载任务卡片"""

    def __init__(self, task_id: str, task_info: dict, download_manager: DownloadManager):
        super().__init__()
        self.task_id = task_id
        self.download_manager = download_manager
        self.setObjectName('TaskCard')
        self._queue_info = ''
        self._setup_ui(task_info)

    def _setup_ui(self, info: dict):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # 第一行: 文件名 + 文件大小
        row1 = QHBoxLayout()
        self.name_label = QLabel(info.get('file_name', '准备中...'))
        self.name_label.setObjectName('BoldLabel')
        row1.addWidget(self.name_label)
        row1.addStretch()
        total = info.get('total_size', -1)
        self.size_label = QLabel(format_size(total) if total > 0 else '未知大小')
        self.size_label.setObjectName('SecondaryLabel')
        row1.addWidget(self.size_label)
        layout.addLayout(row1)

        # 第二行: 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        layout.addWidget(self.progress_bar)

        # 第三行: 速度、进度百分比、剩余时间
        row3 = QHBoxLayout()
        self.speed_label = QLabel('等待中')
        self.speed_label.setObjectName('SecondaryLabel')
        row3.addWidget(self.speed_label)
        row3.addStretch()
        self.progress_label = QLabel('')
        self.progress_label.setObjectName('SecondaryLabel')
        row3.addWidget(self.progress_label)
        row3.addStretch()
        self.time_label = QLabel('')
        self.time_label.setObjectName('SecondaryLabel')
        row3.addWidget(self.time_label)
        layout.addLayout(row3)

        # 第四行: 操作按钮
        row4 = QHBoxLayout()
        row4.addStretch()

        self.btn_pause = QPushButton('暂停')
        self.btn_pause.setFixedWidth(70)
        self.btn_pause.clicked.connect(self._toggle_pause)
        row4.addWidget(self.btn_pause)

        self.btn_cancel = QPushButton('取消')
        self.btn_cancel.setFixedWidth(70)
        self.btn_cancel.setObjectName('DangerBtn')
        self.btn_cancel.clicked.connect(self._cancel)
        row4.addWidget(self.btn_cancel)

        self.btn_open_file = QPushButton('打开文件')
        self.btn_open_file.setFixedWidth(85)
        self.btn_open_file.clicked.connect(self._open_file)
        self.btn_open_file.hide()
        row4.addWidget(self.btn_open_file)

        self.btn_open_folder = QPushButton('文件夹')
        self.btn_open_folder.setFixedWidth(70)
        self.btn_open_folder.clicked.connect(self._open_folder)
        self.btn_open_folder.hide()
        row4.addWidget(self.btn_open_folder)

        self.btn_play = QPushButton('播放')
        self.btn_play.setFixedWidth(60)
        self.btn_play.setObjectName('PrimaryBtn')
        self.btn_play.clicked.connect(self._play_video)
        self.btn_play.hide()
        row4.addWidget(self.btn_play)

        self.btn_stream_play = QPushButton('🎬 边下边播')
        self.btn_stream_play.setFixedWidth(105)
        self.btn_stream_play.setObjectName('PrimaryBtn')
        self.btn_stream_play.setToolTip('边下载边播放（需下载进度 > 5%）')
        self.btn_stream_play.clicked.connect(self._stream_play)
        self.btn_stream_play.hide()
        row4.addWidget(self.btn_stream_play)

        self.btn_retry = QPushButton('重试')
        self.btn_retry.setFixedWidth(60)
        self.btn_retry.clicked.connect(self._retry)
        self.btn_retry.hide()
        row4.addWidget(self.btn_retry)

        layout.addLayout(row4)

        self._file_path = ''
        # 提前从文件名判断是否是视频（用于边下边播按钮显示）
        file_name = info.get('file_name', '')
        ext = os.path.splitext(file_name)[1].lower()
        self._is_video = ext in config.VIDEO_EXTENSIONS
        self._status = info.get('status', DownloadTask.WAITING)
        self._update_button_states()
        # 拖拽起始位置
        self._drag_start_pos = QPoint()
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mousePressEvent(self, event):
        """记录拖拽起始位置"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """达到拖拽阈值时启动拖拽"""
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, '_drag_start_pos'):
            dist = (event.position().toPoint() - self._drag_start_pos).manhattanLength()
            if dist >= QApplication.startDragDistance():
                drag = QDrag(self)
                mime = QMimeData()
                mime.setText(self.task_id)
                drag.setMimeData(mime)
                drag.exec(Qt.DropAction.MoveAction)
        super().mouseMoveEvent(event)

    def update_progress(self, progress_info: dict):
        """更新进度信息"""
        self.progress_bar.setValue(int(progress_info.get('progress', 0)))
        speed_text = progress_info.get('speed_text', '')
        # 显示 BT 连接数(如果有)
        peer_count = progress_info.get('peer_count')
        if peer_count is not None:
            speed_text += f'  [{peer_count}个连接]'
        self.speed_label.setText(speed_text)
        downloaded = progress_info.get('downloaded_text', '')
        total = progress_info.get('total_text', '')
        pct = progress_info.get('progress', 0)
        self.progress_label.setText(f'{downloaded} / {total}  ({pct:.1f}%)')
        self.time_label.setText(f"剩余 {progress_info.get('remaining_time', '--:--')}")
        # 进度更新时刷新按钮状态（边下边播按钮可能在跨过5%阈值后出现）
        self._update_button_states()

    def update_status(self, status: str):
        """更新任务状态"""
        self._status = status
        self._update_button_states()
        # 从失败重试时，恢复默认文字颜色
        if status != DownloadTask.FAILED:
            self.speed_label.setObjectName('')
            self.speed_label.style().unpolish(self.speed_label)
            self.speed_label.style().polish(self.speed_label)
        status_map = {
            DownloadTask.WAITING: self._queue_info or '等待中',
            DownloadTask.DOWNLOADING: '下载中',
            DownloadTask.PAUSED: '已暂停',
            DownloadTask.MERGING: '合并中...',
            DownloadTask.COMPLETED: '已完成',
            DownloadTask.FAILED: '下载失败',
            'resolving_metadata': '解析元数据...',
        }
        if status in (DownloadTask.WAITING, DownloadTask.PAUSED, DownloadTask.MERGING, 'resolving_metadata'):
            self.speed_label.setText(status_map.get(status, ''))

    def set_completed(self, file_path: str):
        """标记为下载完成"""
        self._file_path = file_path
        ext = os.path.splitext(file_path)[1].lower()
        self._is_video = ext in config.VIDEO_EXTENSIONS
        self.progress_bar.setValue(100)
        self.speed_label.setText('已完成')
        self.speed_label.setObjectName('StatusSuccess')
        self.speed_label.style().unpolish(self.speed_label)
        self.speed_label.style().polish(self.speed_label)
        self.time_label.setText('')
        self._update_button_states()

    def _update_button_states(self):
        is_active = self._status in (DownloadTask.DOWNLOADING, DownloadTask.PAUSED,
                                     DownloadTask.WAITING, 'resolving_metadata')
        is_done = self._status == DownloadTask.COMPLETED
        is_failed = self._status == DownloadTask.FAILED

        # 从任务对象更新 _is_video 和文件名（file_name 可能在 prepare() 后才确定）
        task = self.download_manager.tasks.get(self.task_id)
        if task and task.file_name and not self._is_video:
            ext = os.path.splitext(task.file_name)[1].lower()
            self._is_video = ext in config.VIDEO_EXTENSIONS
        if task and task.file_name and self.name_label.text() == '准备中...':
            self.name_label.setText(task.file_name)

        self.btn_pause.setVisible(is_active)
        self.btn_cancel.setVisible(is_active)
        self.btn_open_file.setVisible(is_done)
        self.btn_open_folder.setVisible(is_done)
        self.btn_play.setVisible(is_done and self._is_video)
        self.btn_retry.setVisible(is_failed)

        # 边下边播按钮：下载中/暂停、进度>=5%、文件存在
        can_stream = task and task.streamable and self._is_video
        self.btn_stream_play.setVisible(can_stream and not is_done and not is_failed)

        if self._status == DownloadTask.PAUSED:
            self.btn_pause.setText('继续')
        else:
            self.btn_pause.setText('暂停')

    def _toggle_pause(self):
        task = self.download_manager.tasks.get(self.task_id)
        if not task:
            return
        if task.status == DownloadTask.DOWNLOADING:
            self.download_manager.pause_task(self.task_id)
        elif task.status == DownloadTask.PAUSED:
            self.download_manager.resume_task(self.task_id)
        elif task.status == DownloadTask.WAITING:
            self.download_manager.start_task(self.task_id)

    def _cancel(self):
        reply = QMessageBox.question(self, '确认取消', '确定要取消此下载任务吗？',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.download_manager.cancel_task(self.task_id)

    def _retry(self):
        """重试失败的任务（断点续传）"""
        self.download_manager.retry_task(self.task_id)
        # 重置内联样式为默认（对象名恢复为默认标签）"""
        self.speed_label.setObjectName('')
        self.speed_label.style().unpolish(self.speed_label)
        self.speed_label.style().polish(self.speed_label)

    def _open_file(self):
        if self._file_path and os.path.exists(self._file_path):
            os.startfile(self._file_path)

    def _open_folder(self):
        if self._file_path and os.path.exists(self._file_path):
            subprocess.Popen(f'explorer /select,"{self._file_path}"')

    def _play_video(self):
        if self._file_path and os.path.exists(self._file_path):
            signal_bus.play_video.emit(self._file_path)

    def _stream_play(self):
        """边下边播：打开正在下载的文件进行播放"""
        task = self.download_manager.tasks.get(self.task_id)
        if not task:
            return
        save_path = task.save_path
        if not save_path or not os.path.exists(save_path):
            return
        signal_bus.play_video.emit(save_path)

    def contextMenuEvent(self, event):
        """右键菜单：复制链接 / 打开文件夹 / 查看详情"""
        menu = QMenu(self)
        copy_url_action = menu.addAction('复制链接')
        open_folder_action = menu.addAction('打开文件夹')
        menu.addSeparator()
        detail_action = menu.addAction('查看详情')
        action = menu.exec(event.globalPosition().toPoint())
        if action == copy_url_action:
            task = self.download_manager.tasks.get(self.task_id)
            if task and hasattr(task, 'url'):
                QApplication.clipboard().setText(task.url)
        elif action == open_folder_action:
            if self._file_path and os.path.exists(self._file_path):
                subprocess.Popen(f'explorer /select,"{self._file_path}"')
        elif action == detail_action:
            self._show_detail_dialog()

    def _show_detail_dialog(self):
        """显示任务详情对话框"""
        task = self.download_manager.tasks.get(self.task_id)
        if not task:
            return
        info_lines = [
            f'文件名: {task.file_name or "未知"}',
            f'大小: {format_size(task.total_size) if task.total_size > 0 else "未知"}',
            f'状态: {task.status}',
            f'URL: {getattr(task, "url", "N/A")}',
        ]
        QMessageBox.information(self, '任务详情', '\n'.join(info_lines))


class _ReorderWidget(QWidget):
    """支持拖拽排序的下载列表容器"""

    def __init__(self, parent_tab: 'DownloadTab'):
        super().__init__()
        self._parent_tab = parent_tab
        self.setAcceptDrops(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addStretch()
        self._drop_indicator = _DropIndicator(self)

    def layout(self) -> QVBoxLayout:
        return super().layout()

    def dragEnterEvent(self, event):
        if event.mimeData().hasText() and event.mimeData().text() in self._parent_tab._cards:
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        """移动时更新指示器位置"""
        if not event.mimeData().hasText():
            return
        event.acceptProposedAction()
        # 计算拖拽目标位置并更新指示器
        y = event.position().toPoint().y()
        insert_idx = self._get_insert_index(y)
        self._show_indicator(insert_idx)

    def dragLeaveEvent(self, event):
        """拖拽离开时隐藏指示器"""
        self._drop_indicator.hide()

    def dropEvent(self, event):
        """拖拽落下时重排卡片顺序"""
        self._drop_indicator.hide()
        if not event.mimeData().hasText():
            return
        dragged_task_id = event.mimeData().text()
        if dragged_task_id not in self._parent_tab._cards:
            return

        y = event.position().toPoint().y()
        insert_idx = self._get_insert_index(y)
        target_idx = self._get_card_index(dragged_task_id)

        if target_idx < 0 or target_idx == insert_idx or insert_idx < 0:
            return

        lay = self.layout()
        dragged_card = self._parent_tab._cards[dragged_task_id]

        # 从layout中移除然后插入到目标位置（注意layout有stretch占位）
        lay.removeWidget(dragged_card)

        # 找到layout中目标位置的widget
        total_items = lay.count() - 1  # 去掉最后的stretch
        # 确定位置：把卡片放到insert_idx对应的widget前面
        insert_pos = min(insert_idx, total_items)
        if insert_pos == total_items:
            # 放到最后（stretch前面）
            lay.insertWidget(lay.count() - 1, dragged_card)
        else:
            target_widget = lay.itemAt(insert_pos).widget()
            lay.insertWidget(lay.indexOf(target_widget), dragged_card)

        event.acceptProposedAction()

    def _get_card_index(self, task_id: str) -> int:
        """获取某个任务卡片在layout中的索引"""
        lay = self.layout()
        for i in range(lay.count()):
            item = lay.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), TaskCard):
                if item.widget().task_id == task_id:
                    return i
        return -1

    def _get_insert_index(self, y_pos: int) -> int:
        """根据鼠标Y坐标计算应插入到哪个卡片索引位置"""
        card_centers = []
        lay = self.layout()
        for i in range(lay.count()):
            item = lay.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), TaskCard):
                w = item.widget()
                center_y = w.y() + w.height() // 2
                card_centers.append((i, center_y))

        for i, center_y in card_centers:
            if y_pos < center_y:
                return i
        return len(card_centers)

    def _show_indicator(self, insert_idx: int):
        """在指定位置显示拖拽指示器"""
        lay = self.layout()
        if insert_idx >= lay.count() - 1:
            # 最后一条卡片下方
            last_card = None
            for i in range(lay.count() - 1, -1, -1):
                item = lay.itemAt(i)
                if item and item.widget() and isinstance(item.widget(), TaskCard):
                    last_card = item.widget()
                    break
            if last_card:
                self._drop_indicator.show_below(last_card)
        elif insert_idx == 0:
            # 第一条卡片上方
            item = lay.itemAt(0)
            if item and item.widget():
                self._drop_indicator.show_above(item.widget())
        else:
            item = lay.itemAt(insert_idx)
            if item and item.widget():
                self._drop_indicator.show_above(item.widget())
        self._drop_indicator.raise_()


class _DropIndicator(QFrame):
    """拖拽位置的指示线"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(3)
        self.hide()

    def show_above(self, widget):
        """显示在widget上方"""
        parent = widget.parent()
        if parent:
            pos = widget.mapTo(parent, QPoint(0, 0))
            margin = parent.layout().contentsMargins().left() if parent.layout() else 10
            self.setParent(parent)
            self.setFixedWidth(widget.width() - 20)
            self.move(margin, pos.y() - 1)
            self.show()
            self.raise_()

    def show_below(self, widget):
        """显示在widget下方"""
        parent = widget.parent()
        if parent:
            pos = widget.mapTo(parent, QPoint(0, widget.height()))
            margin = parent.layout().contentsMargins().left() if parent.layout() else 10
            self.setParent(parent)
            self.setFixedWidth(widget.width() - 20)
            self.move(margin, pos.y() - 1)
            self.show()
            self.raise_()

    def paintEvent(self, event):
        t = get_tokens()
        painter = QPainter(self)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(t.accent))
        painter.drawRoundedRect(self.rect(), 1, 1)


class DownloadTab(QWidget):
    """下载管理标签页"""

    def __init__(self, download_manager: DownloadManager):
        super().__init__()
        self.download_manager = download_manager
        self.db = Database()
        self._cards: dict[str, TaskCard] = {}
        # 剪贴板监控：记录最近 100 条已处理 URL 防止重复
        self._recent_urls: deque = deque(maxlen=100)
        # 后台 Worker 引用（防止 GC 回收导致线程中断）
        self._prepare_workers: list = []
        self._cleanup_workers: list = []
        self._setup_ui()
        self._connect_signals()
        # 剪贴板监听（可通过设置开关）
        clipboard = QApplication.clipboard()
        clipboard.dataChanged.connect(self._on_clipboard_changed)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # 输入区域
        input_frame = QFrame()
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(8)

        # URL输入行（支持多行粘贴批量添加）
        url_row = QHBoxLayout()
        url_label = QLabel('下载链接:')
        url_label.setFixedWidth(65)
        url_row.addWidget(url_label)

        input_container = QVBoxLayout()
        input_container.setSpacing(0)
        self.url_input = QPlainTextEdit()
        self.url_input.setPlaceholderText('输入下载链接 (HTTP/HTTPS/磁力链接)，支持多行批量粘贴')
        self.url_input.setMaximumHeight(60)  # 限制约3行高度
        input_container.addWidget(self.url_input)

        url_row.addLayout(input_container)
        self.btn_add = QPushButton('添加')
        self.btn_add.setObjectName('PrimaryBtn')
        self.btn_add.setFixedWidth(70)
        self.btn_add.clicked.connect(self._add_task)
        url_row.addWidget(self.btn_add)
        input_layout.addLayout(url_row)

        # 状态提示
        self.status_label = QLabel()
        self.status_label.setObjectName('StatusInfo')
        self.status_label.hide()
        input_layout.addWidget(self.status_label)

        # 保存路径 + 线程数
        saved_dir = get_setting('download_dir', config.DEFAULT_DOWNLOAD_DIR)
        saved_threads = get_setting('thread_count', config.DEFAULT_THREAD_COUNT)

        path_row = QHBoxLayout()
        path_label = QLabel('保存路径:')
        path_label.setFixedWidth(65)
        path_row.addWidget(path_label)
        self.path_input = QLineEdit(saved_dir)
        self.path_input.editingFinished.connect(self._save_download_settings)
        path_row.addWidget(self.path_input)
        btn_browse = QPushButton('浏览')
        btn_browse.setFixedWidth(60)
        btn_browse.clicked.connect(self._browse_save_dir)
        path_row.addWidget(btn_browse)

        path_row.addSpacing(16)
        thread_label = QLabel('线程数:')
        path_row.addWidget(thread_label)
        self.thread_combo = QComboBox()
        for i in [1, 2, 4, 8, 16]:
            self.thread_combo.addItem(str(i), i)
        self.thread_combo.setCurrentText(str(saved_threads))
        self.thread_combo.currentIndexChanged.connect(self._save_download_settings)
        self.thread_combo.setFixedWidth(60)
        path_row.addWidget(self.thread_combo)
        input_layout.addLayout(path_row)

        layout.addWidget(input_frame)

        # 操作按钮行
        action_row = QHBoxLayout()
        action_row.addStretch()

        # 速度限制下拉
        speed_label = QLabel('限速:')
        speed_label.setObjectName('SecondaryLabel')
        action_row.addWidget(speed_label)
        self.speed_limit_combo = QComboBox()
        self.speed_limit_combo.addItem('无限制', 0)
        self.speed_limit_combo.addItem('100 KB/s', 100 * 1024)
        self.speed_limit_combo.addItem('500 KB/s', 500 * 1024)
        self.speed_limit_combo.addItem('1 MB/s', 1024 * 1024)
        self.speed_limit_combo.addItem('2 MB/s', 2 * 1024 * 1024)
        self.speed_limit_combo.addItem('5 MB/s', 5 * 1024 * 1024)
        self.speed_limit_combo.addItem('10 MB/s', 10 * 1024 * 1024)
        # 恢复上次设置
        saved_speed = get_setting('download_speed_limit', config.DOWNLOAD_SPEED_LIMIT)
        for i in range(self.speed_limit_combo.count()):
            if self.speed_limit_combo.itemData(i) == saved_speed:
                self.speed_limit_combo.setCurrentIndex(i)
                config.DOWNLOAD_SPEED_LIMIT = saved_speed
                break
        self.speed_limit_combo.currentIndexChanged.connect(self._on_speed_limit_changed)
        self.speed_limit_combo.setFixedWidth(90)
        action_row.addWidget(self.speed_limit_combo)

        btn_pause_all = QPushButton('全部暂停')
        btn_pause_all.clicked.connect(self._pause_all)
        action_row.addWidget(btn_pause_all)
        btn_clear_completed = QPushButton('清除已完成')
        btn_clear_completed.clicked.connect(self._clear_completed)
        action_row.addWidget(btn_clear_completed)
        btn_clear_all = QPushButton('清除全部')
        btn_clear_all.setObjectName('DangerBtn')
        btn_clear_all.clicked.connect(self._clear_all_tasks)
        action_row.addWidget(btn_clear_all)
        layout.addLayout(action_row)

        # 下载列表(滚动区域，支持拖拽排序)
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._list_widget = _ReorderWidget(self)
        self._list_layout = self._list_widget.layout()

        self._scroll_area.setWidget(self._list_widget)
        layout.addWidget(self._scroll_area)

    def _connect_signals(self):
        signal_bus.task_created.connect(self._on_task_created)
        signal_bus.task_progress.connect(self._on_task_progress)
        signal_bus.task_status_changed.connect(self._on_task_status_changed)
        signal_bus.task_completed.connect(self._on_task_completed)
        signal_bus.task_failed.connect(self._on_task_failed)
        signal_bus.magnet_metadata_resolved.connect(self._on_magnet_metadata_resolved)

    def _add_task(self):
        """添加下载任务（支持批量多行URL，异步准备）"""
        raw_text = self.url_input.toPlainText().strip()
        if not raw_text:
            return
        save_dir = self.path_input.text().strip() or config.DEFAULT_DOWNLOAD_DIR
        thread_count = self.thread_combo.currentData()

        # 按换行分隔，过滤空白行和注释行（#开头）
        urls = [line.strip() for line in raw_text.split('\n')]
        urls = [u for u in urls if u and not u.startswith('#')]

        if not urls:
            return

        added_count = 0
        errors = []
        headers = {}
        for url in urls:
            try:
                task = self.download_manager.create_task(url, save_dir, '', thread_count, headers=headers)
                # 立即创建卡片（显示"准备中..."）
                card = TaskCard(task.task_id, task.get_info(), self.download_manager)
                self._cards[task.task_id] = card
                self._list_layout.insertWidget(self._list_layout.count() - 1, card)
                # 后台异步执行 prepare()
                from core.task_worker import PrepareWorker
                worker = PrepareWorker(task)
                worker.prepared.connect(self._on_prepare_done)
                worker.failed.connect(self._on_prepare_failed)
                self._prepare_workers.append(worker)
                worker.finished.connect(lambda w=worker: self._prepare_workers.remove(w) if w in self._prepare_workers else None)
                worker.start()
                added_count += 1
            except RuntimeError as e:
                errors.append(f'[{url[:50]}...] {e}')

        self.url_input.clear()

        # 滚动到列表底部
        self._scroll_to_bottom()

        # 提示添加结果
        if not errors and added_count > 0:
            self._show_status(f'已添加 {added_count} 个任务，准备中...')
        elif errors:
            self._show_status(f'添加完成: {added_count} 成功, {len(errors)} 失败',
                              is_error=True)
            QMessageBox.warning(
                self, '批量添加结果',
                f'成功添加 {added_count} 个任务\n'
                f'失败 {len(errors)} 个:\n' + '\n'.join(errors)
            )

    def _on_prepare_done(self, task_id: str, info: dict):
        """后台 prepare() 完成后，启动任务并更新卡片"""
        # 更新卡片显示（文件名、大小等）
        card = self._cards.get(task_id)
        if card:
            card.name_label.setText(info.get('file_name', ''))
            total = info.get('total_size', -1)
            if total > 0:
                card.size_label.setText(format_size(total))
        # 启动下载
        self.download_manager.start_task(task_id)

    def _on_prepare_failed(self, task_id: str, error: str):
        """后台 prepare() 失败时更新卡片"""
        card = self._cards.get(task_id)
        if card:
            card.speed_label.setText(f'失败: {error}')
            card.speed_label.setObjectName('StatusError')
            card.speed_label.style().unpolish(card.speed_label)
            card.speed_label.style().polish(card.speed_label)
            card.btn_pause.hide()
            card.btn_cancel.hide()
            card.btn_retry.show()
        # 记录失败到数据库
        task = self.download_manager.tasks.get(task_id)
        if task:
            self.db.add_record(
                task_id=task_id, url=task.url, file_name=task.file_name or '',
                save_path='', file_size=0,
                status='failed', created_time=task.created_time
            )

    def _on_magnet_metadata_resolved(self, task_id: str, files_info: list):
        """磁力链接元数据解析完成，弹出文件选择对话框"""
        from PyQt6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle('选择文件')
        dlg.setMinimumWidth(450)
        dlg_layout = QVBoxLayout(dlg)

        label = QLabel(f'共 {len(files_info)} 个文件，请选择要下载的文件：')
        dlg_layout.addWidget(label)

        checks = []
        for fi in files_info:
            cb = QCheckBox(f'{fi["name"]}  ({format_size(fi["size"])})')
            cb.setChecked(True)
            checks.append(cb)
            dlg_layout.addWidget(cb)

        # 全选/反选按钮
        btn_row = QHBoxLayout()
        btn_all = QPushButton('全选')
        btn_none = QPushButton('反选')
        btn_all.clicked.connect(lambda: [c.setChecked(True) for c in checks])
        btn_none.clicked.connect(lambda: [c.setChecked(not c.isChecked()) for c in checks])
        btn_row.addWidget(btn_all)
        btn_row.addWidget(btn_none)
        btn_row.addStretch()
        dlg_layout.addLayout(btn_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        dlg_layout.addWidget(buttons)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            selected = [fi['index'] for i, fi in enumerate(files_info) if checks[i].isChecked()]
            if not selected:
                return  # 用户未选择任何文件
            task = self.download_manager.tasks.get(task_id)
            if task:
                from core.magnet_download_task import MagnetDownloadTask
                task.set_file_priorities(selected)


    def _show_status(self, message: str, is_error: bool = False):
        """显示底部状态提示，3秒后自动消失"""
        self.status_label.setText(message)
        self.status_label.setObjectName('StatusError' if is_error else 'StatusSuccess')
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        self.status_label.show()
        QTimer.singleShot(3000, self.status_label.hide)

    def _scroll_to_bottom(self):
        """将下载列表滚动到底部"""
        self._scroll_area.verticalScrollBar().setValue(
            self._scroll_area.verticalScrollBar().maximum()
        )

    def _browse_save_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, '选择保存目录', self.path_input.text())
        if dir_path:
            self.path_input.setText(dir_path)
            set_setting('download_dir', dir_path)

    def _save_download_settings(self):
        """持久化保存当前下载设置"""
        set_setting('download_dir', self.path_input.text().strip())
        set_setting('thread_count', self.thread_combo.currentData())

    def _on_task_created(self, task_id: str, info: dict):
        """任务创建(含恢复的任务)"""
        if task_id not in self._cards:
            card = TaskCard(task_id, info, self.download_manager)
            self._cards[task_id] = card
            self._list_layout.insertWidget(self._list_layout.count() - 1, card)
        else:
            # 更新已有卡片的文件名和大小
            card = self._cards[task_id]
            card.name_label.setText(info.get('file_name', ''))
            total = info.get('total_size', -1)
            card.size_label.setText(format_size(total) if total > 0 else '未知大小')

    def _on_task_progress(self, task_id: str, progress_info: dict):
        card = self._cards.get(task_id)
        if card:
            card.update_progress(progress_info)

    def _on_task_status_changed(self, task_id: str, status: str):
        card = self._cards.get(task_id)
        if not card:
            return
        
        # 等待中时显示队列位置
        if status == DownloadTask.WAITING:
            queue_text = self.download_manager._get_queue_info(task_id)
            card._queue_info = queue_text
        else:
            card._queue_info = ''
        
        card.update_status(status)

    def _on_task_completed(self, task_id: str, file_path: str):
        card = self._cards.get(task_id)
        if card:
            card.set_completed(file_path)
            # 短暂高亮卡片（accent 边框，2 秒后恢复）
            card.setObjectName('TaskCardCompleted')
            card.style().unpolish(card)
            card.style().polish(card)
            QTimer.singleShot(2000, lambda c=card: self._reset_card_highlight(c))

        # 保存到历史记录
        task = self.download_manager.tasks.get(task_id)
        if task:
            self.db.add_record(
                task_id=task_id, url=task.url, file_name=task.file_name,
                save_path=file_path, file_size=task.total_size,
                status='completed', created_time=task.created_time,
                completed_time=time.strftime('%Y-%m-%d %H:%M:%S')
            )

    def _reset_card_highlight(self, card):
        """恢复任务卡片默认样式"""
        if card and card.objectName() != 'TaskCard':
            card.setObjectName('TaskCard')
            card.style().unpolish(card)
            card.style().polish(card)

    def _on_task_failed(self, task_id: str, error: str):
        card = self._cards.get(task_id)
        if card:
            card.speed_label.setText(f'失败: {error}')
            card.speed_label.setObjectName('StatusError')
            card.speed_label.style().unpolish(card.speed_label)
            card.speed_label.style().polish(card.speed_label)

        # 保存失败记录
        task = self.download_manager.tasks.get(task_id)
        if task:
            self.db.add_record(
                task_id=task_id, url=task.url, file_name=task.file_name,
                save_path='', file_size=task.total_size,
                status='failed', created_time=task.created_time
            )

    def _pause_all(self):
        for task_id, task in self.download_manager.tasks.items():
            if task.status == DownloadTask.DOWNLOADING:
                self.download_manager.pause_task(task_id)

    def _on_speed_limit_changed(self, index):
        """速度限制下拉改变时，更新全局限速配置"""
        speed_limit = self.speed_limit_combo.itemData(index)
        if speed_limit is not None:
            config.DOWNLOAD_SPEED_LIMIT = speed_limit
            set_setting('download_speed_limit', speed_limit)

    # URL 匹配正则（HTTP/HTTPS 和磁力链接）
    _URL_RE = re.compile(
        r'(https?://\S+|magnet:\?xt=urn:btih:[A-Za-z0-9]+[^\s]*)',
        re.IGNORECASE
    )

    def _on_clipboard_changed(self):
        """剪贴板内容变化时，检测是否包含可下载的链接"""
        if not get_setting('clipboard_monitor', True):
            return
        try:
            clipboard = QApplication.clipboard()
            text = clipboard.text()
        except Exception:
            return
        if not text:
            return
        # 智能防抖：内容相同则跳过（解决 Windows 剪贴板锁重复触发），
        # 内容不同则立即处理（快速复制多个链接不会丢失）
        if hasattr(self, '_last_clipboard_text') and self._last_clipboard_text == text:
            return
        self._last_clipboard_text = text
        urls = self._URL_RE.findall(text)
        if not urls:
            return
        # 过滤已处理过的 URL
        new_urls = [u for u in urls if u not in self._recent_urls]
        if not new_urls:
            return
        # 将新 URL 填入输入框（每行一个）
        current = self.url_input.toPlainText().strip()
        to_add = '\n'.join(new_urls)
        if current:
            self.url_input.setPlainText(current + '\n' + to_add)
        else:
            self.url_input.setPlainText(to_add)
        # 标记为已处理
        for u in new_urls:
            self._recent_urls.append(u)
        # 提示用户
        self._show_status(f'检测到 {len(new_urls)} 条新链接，已填入输入框')

    def _clear_completed(self):
        """清除已完成的下载任务（加确认）"""
        to_remove = []
        for task_id, card in self._cards.items():
            task = self.download_manager.tasks.get(task_id)
            if task and task.status in (DownloadTask.COMPLETED, DownloadTask.FAILED):
                to_remove.append(task_id)

        if not to_remove:
            return

        reply = QMessageBox.question(
            self, '确认清除',
            f'确定要清除 {len(to_remove)} 个已结束的下载任务吗？',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # UI 立即移除卡片
        for task_id in to_remove:
            card = self._cards.pop(task_id)
            card.hide()  # 先隐藏，立即生效
            self._list_layout.removeWidget(card)
            card.deleteLater()
        # 强制刷新布局
        self._list_layout.activate()
        self._list_widget.updateGeometry()
        # 后台异步清理（已完成的任务只需从内存移除，无需 cancel）
        for task_id in to_remove:
            self.download_manager.remove_task(task_id)

    def _clear_all_tasks(self):
        """清除所有下载任务（含进行中和等待），需确认"""
        total = len(self._cards)
        if total == 0:
            return

        active_count = sum(
            1 for t in self.download_manager.tasks.values()
            if t.status in ('downloading', 'resolving_metadata', 'waiting', 'merging')
        )

        msg = f'确定要清除全部 {total} 个下载任务吗？'
        if active_count > 0:
            msg += f'\n\n其中有 {active_count} 个任务正在进行中或等待中，将被取消并删除。'

        reply = QMessageBox.question(
            self, '确认清除全部', msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # UI 立即移除所有卡片
        for task_id in list(self._cards.keys()):
            card = self._cards.pop(task_id)
            card.hide()  # 先隐藏，立即生效
            self._list_layout.removeWidget(card)
            card.deleteLater()
        # 强制刷新布局
        self._list_layout.activate()
        self._list_widget.updateGeometry()
        # 后台异步清理活跃任务（cancel + 删除临时文件）
        from core.task_worker import CleanupWorker
        for task_id in list(self.download_manager.tasks.keys()):
            task = self.download_manager._tasks.pop(task_id, None)
            if task:
                if task.status == 'completed':
                    continue  # 已完成无需清理
                worker = CleanupWorker(task)
                worker.cleaned.connect(self._on_cleanup_done)
                self._cleanup_workers.append(worker)
                worker.finished.connect(lambda w=worker: self._cleanup_workers.remove(w) if w in self._cleanup_workers else None)
                worker.start()

    def _on_cleanup_done(self, task_id: str):
        """后台清理完成"""
        pass  # 卡片已在 UI 中移除，无需额外操作
