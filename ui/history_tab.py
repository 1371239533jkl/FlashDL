# -*- coding: utf-8 -*-
"""历史记录标签页 - 显示下载历史、搜索过滤、操作"""

import os
import subprocess
import time
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QPainter, QPainterPath, QPen, QColor, QIcon
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QFrame, QMessageBox
)

from data.database import Database
from utils.format_utils import format_size
from utils.signal_bus import signal_bus


class HistoryCard(QFrame):
    """单条历史记录卡片"""

    def __init__(self, record: dict, db: Database, parent_tab):
        super().__init__()
        self.record = record
        self.db = db
        self.parent_tab = parent_tab
        self.setObjectName('TaskCard')
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # 第一行: 文件名 + 状态
        row1 = QHBoxLayout()
        status = self.record.get('status', '')
        icon = '✓' if status == 'completed' else '✗'
        color = '#66BB6A' if status == 'completed' else '#EF5350'

        name_label = QLabel(f'{icon} {self.record.get("file_name", "未知文件")}')
        name_label.setStyleSheet(f'font-weight: bold; font-size: 14px; color: {color};')
        row1.addWidget(name_label)
        row1.addStretch()

        size = self.record.get('file_size', 0)
        size_label = QLabel(format_size(size) if size > 0 else '')
        size_label.setObjectName('SecondaryLabel')
        row1.addWidget(size_label)
        layout.addLayout(row1)

        # 第二行: 时间信息
        row2 = QHBoxLayout()
        created = self.record.get('created_time', '')
        completed = self.record.get('completed_time', '')
        time_text = f'创建时间: {created}'
        if completed:
            time_text += f'  |  完成时间: {completed}'
        time_label = QLabel(time_text)
        time_label.setObjectName('SecondaryLabel')
        row2.addWidget(time_label)
        row2.addStretch()
        layout.addLayout(row2)

        # 第三行: 操作按钮（画出来的图标）
        row3 = QHBoxLayout()
        row3.addStretch()

        save_path = self.record.get('save_path', '')
        if status == 'completed' and save_path and os.path.exists(save_path):
            btn_open = QPushButton()
            btn_open.setFixedSize(30, 26)
            btn_open.setIcon(self._make_play_icon())
            btn_open.setIconSize(btn_open.size() * 0.6)
            btn_open.setToolTip('打开文件')
            btn_open.clicked.connect(lambda: os.startfile(save_path))
            row3.addWidget(btn_open)

            btn_folder = QPushButton()
            btn_folder.setFixedSize(30, 26)
            btn_folder.setIcon(self._make_folder_icon())
            btn_folder.setIconSize(btn_folder.size() * 0.6)
            btn_folder.setToolTip('打开所在文件夹')
            btn_folder.clicked.connect(lambda: subprocess.Popen(f'explorer /select,"{save_path}"'))
            row3.addWidget(btn_folder)

            # 检查是否是视频文件
            from config import VIDEO_EXTENSIONS
            ext = os.path.splitext(save_path)[1].lower()
            if ext in VIDEO_EXTENSIONS:
                btn_play = QPushButton()
                btn_play.setFixedSize(30, 26)
                btn_play.setIcon(self._make_play_icon())
                btn_play.setIconSize(btn_play.size() * 0.6)
                btn_play.setToolTip('在播放器播放')
                btn_play.clicked.connect(lambda: signal_bus.play_video.emit(save_path))
                row3.addWidget(btn_play)

        btn_delete = QPushButton()
        btn_delete.setFixedSize(30, 26)
        btn_delete.setIcon(self._make_delete_icon())
        btn_delete.setIconSize(btn_delete.size() * 0.6)
        btn_delete.setToolTip('删除此记录')
        btn_delete.clicked.connect(self._delete_record)
        row3.addWidget(btn_delete)

        layout.addLayout(row3)

    # === 图标绘制 ===

    @staticmethod
    def _make_play_icon() -> QIcon:
        """绘制播放三角形图标"""
        pix = QPixmap(16, 16)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#CCCCCC'))
        # 画三角形
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
        """绘制文件夹图标"""
        pix = QPixmap(16, 16)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor('#CCCCCC'), 1.5)
        p.setPen(pen)
        p.setBrush(QColor('#CCCCCC'))
        # 文件夹主体（梯形+矩形）
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
        """绘制删除 X 图标"""
        pix = QPixmap(16, 16)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor('#CCCCCC'), 2)
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

    def __init__(self):
        super().__init__()
        self.db = Database()
        self._cards = []
        self._setup_ui()
        # 延迟加载历史记录
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, self.refresh)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # 搜索和操作栏
        top_row = QHBoxLayout()
        search_label = QLabel('搜索:')
        top_row.addWidget(search_label)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('按文件名搜索...')
        self.search_input.textChanged.connect(self._on_search)
        top_row.addWidget(self.search_input)

        btn_refresh = QPushButton('刷新')
        btn_refresh.setFixedWidth(60)
        btn_refresh.clicked.connect(self.refresh)
        top_row.addWidget(btn_refresh)

        btn_clear = QPushButton('清空历史')
        btn_clear.setFixedWidth(80)
        btn_clear.setObjectName('DangerBtn')
        btn_clear.clicked.connect(self._clear_all)
        top_row.addWidget(btn_clear)
        layout.addLayout(top_row)

        # 历史列表
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._list_widget = QWidget()
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(8)
        self._list_layout.addStretch()

        scroll.setWidget(self._list_widget)
        layout.addWidget(scroll)

        # 空状态提示
        self.empty_label = QLabel('暂无下载历史')
        self.empty_label.setObjectName('SecondaryLabel')
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet('font-size: 16px; padding: 40px;')
        layout.addWidget(self.empty_label)

    def refresh(self):
        """刷新历史记录列表"""
        keyword = self.search_input.text().strip()
        if keyword:
            records = self.db.search_records(keyword)
        else:
            records = self.db.get_all_records()

        self._clear_cards()

        if not records:
            self.empty_label.show()
            return

        self.empty_label.hide()
        for record in records:
            card = HistoryCard(record, self.db, self)
            self._cards.append(card)
            self._list_layout.insertWidget(self._list_layout.count() - 1, card)

    def _on_search(self, text: str):
        self.refresh()

    def _clear_all(self):
        reply = QMessageBox.question(self, '确认清空', '确定要清空所有历史记录吗？',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.db.clear_all()
            self.refresh()

    def _clear_cards(self):
        for card in self._cards:
            self._list_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()
