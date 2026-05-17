# -*- coding: utf-8 -*-
"""字幕渲染组件 - 使用独立透明窗口叠加在视频上方显示字幕"""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QLabel, QWidget

import config


class SubtitleWidget(QWidget):
    """
    字幕覆盖窗口。
    使用独立的无边框透明窗口覆盖在 QVideoWidget 上方，
    解决 QVideoWidget 原生渲染表面遮挡子控件的问题。
    """

    def __init__(self, video_widget):
        # 作为独立顶层窗口，不设 parent（避免被嵌入布局）
        super().__init__(None)
        self._video_widget = video_widget

        # 无边框 + 透明 + 始终在最上层 + 不获取焦点
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # 内部 QLabel 显示字幕文字
        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setWordWrap(True)
        font_size = config.SUBTITLE_FONT_SIZE
        self._label.setStyleSheet(f"""
            QLabel {{
                background-color: rgba(0, 0, 0, 180);
                color: #FFFFFF;
                font-size: {font_size}px;
                font-weight: bold;
                padding: 6px 16px;
                border-radius: 4px;
            }}
        """)

        # 定时器跟踪视频窗口位置
        self._track_timer = QTimer(self)
        self._track_timer.setInterval(50)
        self._track_timer.timeout.connect(self._update_position)

        self._visible = False
        self.hide()

    def set_text(self, text: str):
        """设置字幕文本"""
        self._label.setText(text)
        self._visible = True
        self._update_position()
        self.show()
        if not self._track_timer.isActive():
            self._track_timer.start()

    def clear(self):
        """清空字幕并停止定时器"""
        self._label.setText('')
        self._visible = False
        self.hide()
        if self._track_timer.isActive():
            self._track_timer.stop()

    def show_overlay(self):
        """开始显示并跟踪（仅当有字幕文本时启动定时器）"""
        if self._visible and self._label.text():
            self.show()
            if not self._track_timer.isActive():
                self._track_timer.start()

    def hide_overlay(self):
        """隐藏覆盖窗口"""
        self.hide()
        self._track_timer.stop()

    def cleanup(self):
        """清理资源"""
        self._track_timer.stop()
        self.hide()

    def _update_position(self):
        """根据视频控件的全局位置定位字幕窗口"""
        vw = self._video_widget
        if vw is None or not vw.isVisible():
            return

        # 获取视频控件在屏幕上的全局坐标和尺寸
        try:
            global_pos = vw.mapToGlobal(vw.rect().topLeft())
        except RuntimeError:
            return
        vw_width = vw.width()
        vw_height = vw.height()

        # 字幕宽度：视频区域的 80%
        max_width = int(vw_width * 0.8)
        self._label.setMaximumWidth(max_width)
        self._label.adjustSize()

        label_w = self._label.width()
        label_h = self._label.height()

        # 居中于视频底部，留 40px 底边距
        x = global_pos.x() + (vw_width - label_w) // 2
        y = global_pos.y() + vw_height - label_h - 40

        self.setFixedSize(label_w, label_h)
        self.move(x, max(global_pos.y(), y))
