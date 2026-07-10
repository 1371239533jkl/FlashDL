# -*- coding: utf-8 -*-
"""下载管理标签页 - URL输入、下载列表、进度显示、操作按钮"""

import os
import re
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
from utils.format_utils import format_size, safe_open_file, safe_open_folder
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
        self.name_label.setObjectName('TaskName')
        row1.addWidget(self.name_label)
        row1.addStretch()
        total = info.get('total_size', -1)
        self.size_label = QLabel(format_size(total) if total > 0 else '未知大小')
        self.size_label.setObjectName('TaskSize')
        row1.addWidget(self.size_label)
        layout.addLayout(row1)

        # 第二行: 进度条 + 百分比
        prog_row = QHBoxLayout()
        prog_row.setSpacing(12)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(4)
        prog_row.addWidget(self.progress_bar)
        self.progress_pct = QLabel('')
        self.progress_pct.setObjectName('MonoLabel')
        self.progress_pct.setFixedWidth(40)
        self.progress_pct.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        prog_row.addWidget(self.progress_pct)
        layout.addLayout(prog_row)

        # 第三行: 速度 / 已下载 / 剩余时间 (统计行)
        row3 = QHBoxLayout()
        row3.setSpacing(12)

        stat_speed = QVBoxLayout()
        stat_speed.setSpacing(2)
        sl1 = QLabel('速度')
        sl1.setObjectName('StatLabel')
        stat_speed.addWidget(sl1)
        self.speed_label = QLabel('等待中')
        self.speed_label.setObjectName('StatValue')
        stat_speed.addWidget(self.speed_label)
        row3.addLayout(stat_speed)

        stat_dl = QVBoxLayout()
        stat_dl.setSpacing(2)
        sl2 = QLabel('已下载')
        sl2.setObjectName('StatLabel')
        stat_dl.addWidget(sl2)
        self.downloaded_label = QLabel('')
        self.downloaded_label.setObjectName('StatValue')
        stat_dl.addWidget(self.downloaded_label)
        row3.addLayout(stat_dl)

        stat_remain = QVBoxLayout()
        stat_remain.setSpacing(2)
        sl3 = QLabel('剩余')
        sl3.setObjectName('StatLabel')
        stat_remain.addWidget(sl3)
        self.time_label = QLabel('')
        self.time_label.setObjectName('StatValue')
        stat_remain.addWidget(self.time_label)
        row3.addLayout(stat_remain)

        row3.addStretch()
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

        self.btn_stream_play = QPushButton('▶ 边下边播')
        self.btn_stream_play.setFixedWidth(90)
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
        pct = progress_info.get('progress', 0)
        self.progress_bar.setValue(int(pct))
        self.progress_pct.setText(f'{pct:.1f}%')
        speed_text = progress_info.get('speed_text', '')
        # 显示 BT 连接数(如果有)
        peer_count = progress_info.get('peer_count')
        if peer_count is not None:
            speed_text += f'  [{peer_count}个连接]'
        self.speed_label.setText(speed_text)
        downloaded = progress_info.get('downloaded_text', '')
        self.downloaded_label.setText(downloaded)
        self.time_label.setText(progress_info.get('remaining_time', '--:--'))
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
        safe_open_file(self._file_path)

    def _open_folder(self):
        safe_open_folder(self._file_path)

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
            safe_open_folder(self._file_path)
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
        # 进度更新节流：每个任务最多 10fps，避免信号风暴
        self._last_progress_update: dict[str, float] = {}
        self._status_bar_throttle = 0.0
        self._setup_ui()
        self._connect_signals()
        # 剪贴板监听（可通过设置开关）
        clipboard = QApplication.clipboard()
        clipboard.dataChanged.connect(self._on_clipboard_changed)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # ── URL 输入区 (HTML匹配: textarea + 右侧按钮组) ──
        input_frame = QFrame()
        input_frame.setObjectName('UrlInputArea')
        input_frame.setFixedHeight(56)

        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(8)

        self.url_input = QPlainTextEdit()
        self.url_input.setPlaceholderText('粘贴下载链接或磁力链接...  (HTTP / HTTPS / magnet / BT)')
        self.url_input.setFixedHeight(56)
        input_layout.addWidget(self.url_input)

        # 按钮组固定 56px 高，与文本框等高
        btn_group_widget = QWidget()
        btn_group_widget.setFixedSize(120, 56)
        btn_group = QVBoxLayout(btn_group_widget)
        btn_group.setContentsMargins(0, 0, 0, 0)
        btn_group.setSpacing(8)
        self.btn_add = QPushButton('+ 添加下载')
        self.btn_add.setObjectName('PrimaryBtn')
        self.btn_add.setFixedHeight(24)
        self.btn_add.clicked.connect(self._add_task)
        btn_group.addWidget(self.btn_add)

        btn_import = QPushButton('从文件导入')
        btn_import.setObjectName('GhostBtn')
        btn_import.setFixedHeight(24)
        btn_import.clicked.connect(self._import_from_file)
        btn_group.addWidget(btn_import)
        input_layout.addWidget(btn_group_widget)




        # 状态提示（隐藏时不加入布局，避免占用空间）
        self.status_label = QLabel()
        self.status_label.setObjectName('StatusInfo')
        self.status_label.setVisible(False)

        layout.addWidget(input_frame)

        # ── 工具栏 (HTML匹配: 保存路径 + 线程 + 限速 + 操作) ──
        toolbar = QFrame()
        toolbar.setObjectName('DownloadToolbar')
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(6, 4, 6, 4)
        toolbar_layout.setSpacing(6)

        saved_dir = get_setting('download_dir', config.DEFAULT_DOWNLOAD_DIR)
        saved_threads = get_setting('thread_count', config.DEFAULT_THREAD_COUNT)

        tl = QLabel('保存至')
        tl.setObjectName('ToolbarLabel')
        toolbar_layout.addWidget(tl)

        self.path_input = QLineEdit(saved_dir)
        self.path_input.setObjectName('ToolbarPath')
        self.path_input.setMinimumWidth(200)
        self.path_input.editingFinished.connect(self._save_download_settings)
        toolbar_layout.addWidget(self.path_input, 1)

        btn_browse = QPushButton('浏览')
        btn_browse.setObjectName('SmallBtn')
        btn_browse.setFixedWidth(48)
        btn_browse.clicked.connect(self._browse_save_dir)
        toolbar_layout.addWidget(btn_browse)

        # 分隔线
        div1 = QWidget()
        div1.setObjectName('ToolbarDivider')
        toolbar_layout.addWidget(div1)

        tl2 = QLabel('线程')
        tl2.setObjectName('ToolbarLabel')
        toolbar_layout.addWidget(tl2)

        self.thread_combo = QComboBox()
        for i in [1, 2, 4, 8, 16]:
            self.thread_combo.addItem(str(i), i)
        self.thread_combo.setCurrentText(str(saved_threads))
        self.thread_combo.currentIndexChanged.connect(self._save_download_settings)
        self.thread_combo.setFixedWidth(50)
        toolbar_layout.addWidget(self.thread_combo)

        # 分隔线
        div2 = QWidget()
        div2.setObjectName('ToolbarDivider')
        toolbar_layout.addWidget(div2)

        tl3 = QLabel('限速')
        tl3.setObjectName('ToolbarLabel')
        toolbar_layout.addWidget(tl3)

        self.speed_limit_combo = QComboBox()
        self.speed_limit_combo.addItem('无限制', 0)
        self.speed_limit_combo.addItem('1 MB/s', 1024 * 1024)
        self.speed_limit_combo.addItem('5 MB/s', 5 * 1024 * 1024)
        self.speed_limit_combo.addItem('10 MB/s', 10 * 1024 * 1024)
        saved_speed = get_setting('download_speed_limit', config.DOWNLOAD_SPEED_LIMIT)
        for i in range(self.speed_limit_combo.count()):
            if self.speed_limit_combo.itemData(i) == saved_speed:
                self.speed_limit_combo.setCurrentIndex(i)
                config.DOWNLOAD_SPEED_LIMIT = saved_speed
                break
        self.speed_limit_combo.currentIndexChanged.connect(self._on_speed_limit_changed)
        self.speed_limit_combo.setFixedWidth(80)
        toolbar_layout.addWidget(self.speed_limit_combo)

        toolbar_layout.addStretch()

        self.btn_pause_all = QPushButton('全部暂停')
        self.btn_pause_all.setObjectName('SmallBtn')
        self.btn_pause_all.clicked.connect(self._toggle_pause_all)
        toolbar_layout.addWidget(self.btn_pause_all)
        btn_clear_completed = QPushButton('清除已完成')
        btn_clear_completed.setObjectName('SmallBtn')
        btn_clear_completed.clicked.connect(self._clear_completed)
        toolbar_layout.addWidget(btn_clear_completed)
        btn_clear_all = QPushButton('清除全部')
        btn_clear_all.setObjectName('DangerBtn')
        btn_clear_all.setProperty('class', 'btn-sm')
        btn_clear_all.clicked.connect(self._clear_all_tasks)
        toolbar_layout.addWidget(btn_clear_all)

        self.toolbar = toolbar
        layout.addWidget(self.toolbar)

        # ── 下载列表(滚动区域，支持拖拽排序) ──
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._list_widget = _ReorderWidget(self)
        self._list_layout = self._list_widget.layout()

        # 空状态提示
        self._empty_state = self._create_empty_state()
        self._list_layout.insertWidget(self._list_layout.count() - 1, self._empty_state)

        self._scroll_area.setWidget(self._list_widget)
        layout.addWidget(self._scroll_area, 1)

        # ── 状态栏 ──
        status_bar = QFrame()
        status_bar.setObjectName('DownloadStatusBar')
        status_bar_layout = QHBoxLayout(status_bar)
        status_bar_layout.setContentsMargins(6, 2, 6, 2)
        status_bar_layout.setSpacing(8)

        self._status_dot = QLabel()
        self._status_dot.setObjectName('StatusDot')
        self._status_dot.setProperty('idle', True)
        status_bar_layout.addWidget(self._status_dot)

        self._status_text = QLabel('就绪')
        self._status_text.setObjectName('MonoLabel')
        status_bar_layout.addWidget(self._status_text)

        status_bar_layout.addStretch()

        self._status_speed = QLabel('')
        self._status_speed.setObjectName('MonoAccent')
        status_bar_layout.addWidget(self._status_speed)

        layout.addWidget(status_bar)

    def _create_empty_state(self) -> QWidget:
        """创建列表空状态提示"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 36, 0, 36)
        layout.setSpacing(12)
        layout.addStretch()

        icon = QLabel('↓')
        icon.setObjectName('EmptyStateIcon')
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        text = QLabel('暂无下载任务')
        text.setObjectName('EmptyStateText')
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(text)

        hint = QLabel('在上方粘贴链接，点击"添加下载"开始')
        hint.setObjectName('EmptyStateHint')
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        layout.addStretch()
        return widget

    def _update_empty_state(self):
        """根据任务数量显示/隐藏空状态"""
        has_cards = len(self._cards) > 0
        if self._empty_state.isVisible() == has_cards:
            self._empty_state.setVisible(not has_cards)
            self._list_layout.activate()

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
                self._update_empty_state()
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
        # 动态插入到工具栏上方
        if self.status_label.parent() is None:
            self.layout().insertWidget(self.layout().indexOf(self.toolbar), self.status_label)
        self.status_label.setVisible(True)
        QTimer.singleShot(3000, self._hide_status)

    def _hide_status(self):
        """隐藏状态提示并从布局移除"""
        self.status_label.setVisible(False)
        self.layout().removeWidget(self.status_label)
        self.status_label.setParent(None)

    def _scroll_to_bottom(self):
        """将下载列表滚动到底部"""
        self._scroll_area.verticalScrollBar().setValue(
            self._scroll_area.verticalScrollBar().maximum()
        )

    def _import_from_file(self):
        """从文本文件导入下载链接"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, '导入下载链接', '',
            '文本文件 (*.txt);;所有文件 (*)')
        if not file_path:
            return
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            if content:
                current = self.url_input.toPlainText().strip()
                if current:
                    self.url_input.setPlainText(current + '\n' + content)
                else:
                    self.url_input.setPlainText(content)
                self._show_status('已导入链接列表')
        except Exception as e:
            self._show_status(f'导入失败: {e}', is_error=True)

    def _update_status_bar(self):
        """更新底部状态栏"""
        tasks = self.download_manager.tasks
        total = len(tasks)
        active = sum(1 for t in tasks.values()
                     if t.status in (DownloadTask.DOWNLOADING, 'resolving_metadata'))
        completed = sum(1 for t in tasks.values() if t.status == DownloadTask.COMPLETED)
        waiting = sum(1 for t in tasks.values() if t.status in (DownloadTask.WAITING, DownloadTask.PAUSED))

        if total == 0:
            self._status_dot.setProperty('idle', True)
            self._status_dot.style().unpolish(self._status_dot)
            self._status_dot.style().polish(self._status_dot)
            self._status_text.setText('就绪')
            self._status_speed.setText('')
        elif active > 0:
            self._status_dot.setProperty('idle', False)
            self._status_dot.style().unpolish(self._status_dot)
            self._status_dot.style().polish(self._status_dot)
            parts = [f'{total} 个任务']
            if active: parts.append(f'下载中: {active}')
            if waiting: parts.append(f'等待中: {waiting}')
            if completed: parts.append(f'已完成: {completed}')
            self._status_text.setText(' · '.join(parts))
            self._status_speed.setText('')
        else:
            self._status_dot.setProperty('idle', True)
            self._status_dot.style().unpolish(self._status_dot)
            self._status_dot.style().polish(self._status_dot)
            parts = [f'{total} 个任务']
            if completed: parts.append(f'已完成: {completed}')
            self._status_text.setText(' · '.join(parts))
            self._status_speed.setText('')

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
            self._update_empty_state()
        else:
            # 更新已有卡片的文件名和大小
            card = self._cards[task_id]
            card.name_label.setText(info.get('file_name', ''))
            total = info.get('total_size', -1)
            card.size_label.setText(format_size(total) if total > 0 else '未知大小')
        self._update_status_bar()

    def _on_task_progress(self, task_id: str, progress_info: dict):
        # 节流：每个任务最多 10fps，避免信号风暴
        now = time.time()
        task_count = len(self.download_manager.tasks)
        interval = 0.1 if task_count <= 5 else (0.2 if task_count <= 20 else 0.5)
        if now - self._last_progress_update.get(task_id, 0) < interval:
            return
        self._last_progress_update[task_id] = now

        card = self._cards.get(task_id)
        if card:
            card.update_progress(progress_info)
        # 状态栏最多 2fps
        if now - self._status_bar_throttle >= 0.5:
            self._status_bar_throttle = now
            self._update_status_bar()

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
        self._update_status_bar()

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
        self._update_status_bar()

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
        self._update_status_bar()
        if task:
            self.db.add_record(
                task_id=task_id, url=task.url, file_name=task.file_name,
                save_path='', file_size=task.total_size,
                status='failed', created_time=task.created_time
            )

    def _toggle_pause_all(self):
        """切换全部暂停/全部继续"""
        active = [t for t in self.download_manager.tasks.values()
                  if t.status == DownloadTask.DOWNLOADING]
        if active:
            for t in active:
                self.download_manager.pause_task(t.task_id)
            self.btn_pause_all.setText('全部继续')
        else:
            for t in self.download_manager.tasks.values():
                if t.status in (DownloadTask.PAUSED, DownloadTask.WAITING):
                    self.download_manager.resume_task(t.task_id)
            self.btn_pause_all.setText('全部暂停')

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
        if not text or not isinstance(text, str):
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
        self._update_empty_state()
        # 强制刷新布局
        self._list_layout.activate()
        self._list_widget.updateGeometry()
        self._update_status_bar()
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
        self._update_empty_state()
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
