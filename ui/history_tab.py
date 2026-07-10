# -*- coding: utf-8 -*-
"""历史记录标签页 - 显示下载历史、搜索过滤、操作"""

import os
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QPainter, QPainterPath, QPen, QColor, QIcon
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QFrame, QMessageBox, QFileDialog
)

from data.database import Database
from utils.format_utils import format_size, safe_open_file, safe_open_folder
from utils.signal_bus import signal_bus


class HistoryCard(QFrame):
    """单条历史记录卡片"""

    def __init__(self, record: dict, db: Database, parent_tab):
        super().__init__()
        self.record = record
        self.db = db
        self.parent_tab = parent_tab
        self.setObjectName('HistoryCard')
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)

        # 状态圆点
        status = self.record.get('status', '')
        self.status_dot = QLabel('✓' if status == 'completed' else '✕')
        self.status_dot.setObjectName(
            'HistoryStatusSuccess' if status == 'completed' else 'HistoryStatusError')
        self.status_dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_dot.setFixedSize(20, 20)
        layout.addWidget(self.status_dot)

        # 中间信息区
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        name_label = QLabel(self.record.get('file_name', '未知文件'))
        name_label.setObjectName('BoldLabel')
        name_label.setMinimumWidth(0)
        info_layout.addWidget(name_label)

        meta_layout = QHBoxLayout()
        meta_layout.setSpacing(12)
        created = self.record.get('created_time', '')
        completed = self.record.get('completed_time', '')
        if completed:
            meta_text = f'{created}  →  {completed}'
        else:
            meta_text = str(created)
        meta_label = QLabel(meta_text)
        meta_label.setObjectName('SecondaryLabel')
        meta_layout.addWidget(meta_label)
        info_layout.addLayout(meta_layout)

        layout.addLayout(info_layout, 1)

        # 文件大小
        size = self.record.get('file_size', 0)
        self.size_label = QLabel(format_size(size) if size > 0 else '')
        self.size_label.setObjectName('MonoLabel')
        layout.addWidget(self.size_label)

        # 操作按钮（悬停才显示）
        save_path = self.record.get('save_path', '')
        self._action_widget = QWidget()
        action_layout = QHBoxLayout(self._action_widget)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(2)

        if status == 'completed' and save_path and os.path.exists(save_path):
            btn_open = QPushButton()
            btn_open.setObjectName('HistoryActionBtn')
            btn_open.setFixedSize(28, 28)
            btn_open.setIcon(self._make_play_icon())
            btn_open.setIconSize(btn_open.size() * 0.5)
            btn_open.setToolTip('打开文件')
            btn_open.clicked.connect(lambda p=save_path: safe_open_file(p))
            action_layout.addWidget(btn_open)

            btn_folder = QPushButton()
            btn_folder.setObjectName('HistoryActionBtn')
            btn_folder.setFixedSize(28, 28)
            btn_folder.setIcon(self._make_folder_icon())
            btn_folder.setIconSize(btn_folder.size() * 0.5)
            btn_folder.setToolTip('打开所在文件夹')
            btn_folder.clicked.connect(lambda p=save_path: safe_open_folder(p))
            action_layout.addWidget(btn_folder)

            from config import VIDEO_EXTENSIONS
            ext = os.path.splitext(save_path)[1].lower()
            if ext in VIDEO_EXTENSIONS:
                btn_play = QPushButton()
                btn_play.setObjectName('HistoryActionBtn')
                btn_play.setFixedSize(28, 28)
                btn_play.setIcon(self._make_play_icon())
                btn_play.setIconSize(btn_play.size() * 0.5)
                btn_play.setToolTip('在播放器播放')
                btn_play.clicked.connect(lambda: signal_bus.play_video.emit(save_path))
                action_layout.addWidget(btn_play)

        btn_delete = QPushButton()
        btn_delete.setObjectName('HistoryActionBtn')
        btn_delete.setFlat(True)
        btn_delete.setFixedSize(28, 28)
        btn_delete.setIcon(self._make_delete_icon())
        btn_delete.setIconSize(btn_delete.size() * 0.5)
        btn_delete.setToolTip('删除此记录')
        btn_delete.clicked.connect(self._delete_record)
        action_layout.addWidget(btn_delete)

        # 初始隐藏，hover时显示
        self._action_widget.hide()
        layout.addWidget(self._action_widget)

    def enterEvent(self, event):
        """鼠标进入时显示操作按钮"""
        if self._action_widget:
            self._action_widget.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """鼠标离开时隐藏操作按钮"""
        if self._action_widget:
            self._action_widget.hide()
        super().leaveEvent(event)

    # === 图标绘制 ===

    @staticmethod
    def _make_play_icon() -> QIcon:
        """绘制播放三角形图标 (主题自适应)"""
        from ui.styles import get_tokens
        t = get_tokens()
        pix = QPixmap(16, 16)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(t.text_secondary))
        path = QPainterPath()
        path.moveTo(3, 2)
        path.lineTo(3, 14)
        path.lineTo(14, 8)
        path.closeSubpath()
        p.drawPath(path)
        p.end()
        return QIcon(pix)

    @staticmethod
    def _make_folder_icon() -> QIcon:
        """绘制文件夹图标 (主题自适应)"""
        from ui.styles import get_tokens
        t = get_tokens()
        pix = QPixmap(16, 16)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(t.text_secondary), 1.5)
        p.setPen(pen)
        p.setBrush(QColor(t.text_secondary))
        path = QPainterPath()
        path.moveTo(2, 4)
        path.lineTo(6, 4)
        path.lineTo(7.5, 6)
        path.lineTo(14, 6)
        path.lineTo(14, 13)
        path.lineTo(2, 13)
        path.lineTo(2, 4)
        path.closeSubpath()
        p.drawPath(path)
        p.end()
        return QIcon(pix)

    @staticmethod
    def _make_delete_icon() -> QIcon:
        """绘制删除 X 图标 (主题自适应)"""
        from ui.styles import get_tokens
        t = get_tokens()
        pix = QPixmap(16, 16)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(t.error))
        pen = QPen(QColor(t.text_secondary), 2)
        p.setPen(pen)
        p.drawLine(3, 3, 13, 13)
        p.drawLine(13, 3, 3, 13)
        p.end()
        return QIcon(pix)

    def _delete_record(self):
        task_id = self.record.get('task_id', '')
        if task_id:
            self.db.delete_record(task_id)
        self.parent_tab.refresh()


class HistoryTab(QWidget):
    """历史记录标签页"""

    PAGE_SIZE = 50  # 每页加载条数

    def __init__(self):
        super().__init__()
        self.db = Database()
        self._cards = []
        self._current_filter = 'all'  # all | completed | failed
        self._page = 0
        self._total_count = 0
        self._loading = False  # 防止重复触发加载
        self._setup_ui()
        # 搜索防抖：300ms 内只触发一次查询
        from PyQt6.QtCore import QTimer
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._do_search)
        QTimer.singleShot(100, self.refresh)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        # 顶部工具栏行
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        # 搜索框（带占位图标）
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('搜索文件名...')
        self.search_input.textChanged.connect(self._on_search)
        self.search_input.setMaximumWidth(360)
        top_row.addWidget(self.search_input)

        # 过滤器药丸按钮
        self._filter_btns = {}
        filters = [
            ('all', '全部'),
            ('completed', '已完成'),
            ('failed', '失败'),
        ]
        for key, label in filters:
            btn = QPushButton(label)
            btn.setObjectName('FilterChip')
            btn.setCheckable(True)
            btn.setFixedHeight(28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, k=key: self._set_filter(k))
            self._filter_btns[key] = btn
            top_row.addWidget(btn)

        self._filter_btns['all'].setChecked(True)

        top_row.addStretch()

        btn_refresh = QPushButton('刷新')
        btn_refresh.setObjectName('SmallBtn')
        btn_refresh.setFixedWidth(56)
        btn_refresh.clicked.connect(self.refresh)
        top_row.addWidget(btn_refresh)

        btn_export = QPushButton('导出 CSV')
        btn_export.setObjectName('SmallBtn')
        btn_export.setFixedWidth(72)
        btn_export.clicked.connect(self._export_csv)
        top_row.addWidget(btn_export)

        btn_clear = QPushButton('清空')
        btn_clear.setObjectName('DangerBtn')
        btn_clear.setFixedWidth(56)
        btn_clear.clicked.connect(self._clear_all)
        top_row.addWidget(btn_clear)
        layout.addLayout(top_row)

        # 历史列表
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.verticalScrollBar().valueChanged.connect(self._on_scroll)
        self._scroll_area = scroll

        self._list_widget = QWidget()
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(2)
        self._list_layout.addStretch()

        scroll.setWidget(self._list_widget)
        layout.addWidget(scroll)

        # 空状态提示
        self.empty_label = QLabel('暂无下载历史')
        self.empty_label.setObjectName('EmptyState')
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty_label)

    def _set_filter(self, filter_key: str):
        """切换过滤器"""
        self._current_filter = filter_key
        for key, btn in self._filter_btns.items():
            btn.setChecked(key == filter_key)
        self.refresh()

    def _update_filter_style(self):
        """过滤器样式由QSS #FilterChip规则统一管理，此方法已废弃"""
        pass

    def refresh(self):
        """刷新历史记录列表（重置分页，加载第一页）"""
        self._page = 0
        self._total_count = 0
        self._clear_cards()
        self._load_more()

    def _load_more(self):
        """加载下一页历史记录"""
        if self._loading:
            return
        # 检查是否还有更多数据
        if self._page > 0 and len(self._cards) >= self._total_count:
            return
        self._loading = True
        keyword = self.search_input.text().strip()

        if self._current_filter == 'all':
            if keyword:
                records, total = self.db.search_records_page(keyword, self._page, self.PAGE_SIZE)
            else:
                records, total = self.db.get_records_page(self._page, self.PAGE_SIZE)
        else:
            records, total = self.db.get_records_by_status_page(
                self._current_filter, self._page, self.PAGE_SIZE, keyword
            )

        self._total_count = total
        self._page += 1

        if not records and not self._cards:
            self.empty_label.show()
            self._loading = False
            return

        self.empty_label.hide()
        for record in records:
            card = HistoryCard(record, self.db, self)
            self._cards.append(card)
            self._list_layout.insertWidget(self._list_layout.count() - 1, card)
        self._loading = False

    def _on_scroll(self, value):
        """滚动条触底时加载下一页"""
        scrollbar = self._scroll_area.verticalScrollBar()
        if value >= scrollbar.maximum() - 50:
            self._load_more()

    def _on_search(self, text: str):
        """搜索输入变化时重启防抖计时器"""
        self._search_timer.start()

    def _do_search(self):
        """防抖结束后执行搜索刷新"""
        self.refresh()

    def _clear_all(self):
        reply = QMessageBox.question(self, '确认清空', '确定要清空所有历史记录吗？',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.db.clear_all()
            self.refresh()

    def _export_csv(self):
        """导出历史记录为 CSV 文件"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, '导出历史记录', 'download_history.csv',
            'CSV 文件 (*.csv);;所有文件 (*)'
        )
        if not file_path:
            return
        try:
            count = self.db.export_csv(file_path)
            QMessageBox.information(self, '导出成功', f'成功导出 {count} 条历史记录到:\n{file_path}')
        except Exception as e:
            QMessageBox.warning(self, '导出失败', f'导出失败: {e}')

    def _clear_cards(self):
        for card in self._cards:
            self._list_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()
