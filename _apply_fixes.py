"""Apply all player_tab.py fixes in one pass."""
import sys

path = r'c:\Users\18665\OneDrive\桌面\Qoder\video-downloader\ui\player_tab.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

changes = 0

# === FIX 1: Replace eventFilter main window section ===
old = '''        # 主窗口事件（全屏时拦截）
        if obj is main_win and self._is_fullscreen:
            if event.type() == QEvent.Type.KeyPress:
                key = event.key()
                if key == Qt.Key.Key_Escape:
                    self._exit_fullscreen()
                    return True
                if key == Qt.Key.Key_Space:
                    self._toggle_play()
                    return True
                if key == Qt.Key.Key_Left:
                    self._skip(-10000)
                    self._show_fullscreen_controls()
                    return True
                if key == Qt.Key.Key_Right:
                    self._skip(10000)
                    self._show_fullscreen_controls()
                    return True
                if key == Qt.Key.Key_Up:
                    vol = min(100, self.volume_slider.value() + 5)
                    self.volume_slider.setValue(vol)
                    self.fullscreen_controls._volume_slider.blockSignals(True)
                    self.fullscreen_controls._volume_slider.setValue(vol)
                    self.fullscreen_controls._volume_slider.blockSignals(False)
                    self._show_fullscreen_controls()
                    return True
                if key == Qt.Key.Key_Down:
                    vol = max(0, self.volume_slider.value() - 5)
                    self.volume_slider.setValue(vol)
                    self.fullscreen_controls._volume_slider.blockSignals(True)
                    self.fullscreen_controls._volume_slider.setValue(vol)
                    self.fullscreen_controls._volume_slider.blockSignals(False)
                    self._show_fullscreen_controls()
                    return True
                if key == Qt.Key.Key_S:
                    self._take_screenshot()
                    return True
                if key == Qt.Key.Key_A:
                    self._cycle_aspect_ratio()
                    return True
                if key == Qt.Key.Key_I:
                    self._show_video_info()
                    return True
                if key == Qt.Key.Key_H or key == Qt.Key.Key_Question:
                    self._toggle_shortcut_overlay()
                    return True
            return super().eventFilter(obj, event)'''

new = '''        # 主窗口事件（全屏时拦截）
        if obj is main_win and self._is_fullscreen:
            if event.type() == QEvent.Type.KeyPress:
                if self._handle_player_key(event.key()):
                    return True
            return super().eventFilter(obj, event)'''

if old in content:
    content = content.replace(old, new)
    changes += 1
    print('Fix 1 applied: simplified main window eventFilter')
else:
    print('WARN: Fix 1 marker not found')

# === FIX 2: Replace eventFilter video_widget key section ===
old = '''        # 键盘事件
        if etype == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Escape and self._is_fullscreen:
                self._exit_fullscreen()
                return True
            if key == Qt.Key.Key_Space:
                self._toggle_play()
                return True
            if key == Qt.Key.Key_Left:
                self._skip(-10000)
                if self._is_fullscreen:
                    self._show_fullscreen_controls()
                return True
            if key == Qt.Key.Key_Right:
                self._skip(10000)
                if self._is_fullscreen:
                    self._show_fullscreen_controls()
                return True
            if key == Qt.Key.Key_Up:
                vol = min(100, self.volume_slider.value() + 5)
                self.volume_slider.setValue(vol)
                if self._is_fullscreen:
                    self._show_fullscreen_controls()
                return True
            if key == Qt.Key.Key_Down:
                vol = max(0, self.volume_slider.value() - 5)
                self.volume_slider.setValue(vol)
                if self._is_fullscreen:
                    self._show_fullscreen_controls()
                return True
            if key == Qt.Key.Key_F or key == Qt.Key.Key_F11:
                self._toggle_fullscreen()
                return True
            if key == Qt.Key.Key_S:
                self._take_screenshot()
                return True
            if key == Qt.Key.Key_A:
                self._cycle_aspect_ratio()
                return True
            if key == Qt.Key.Key_I:
                self._show_video_info()
                return True
            if key == Qt.Key.Key_H or key == Qt.Key.Key_Question:
                self._toggle_shortcut_overlay()
                return True'''

new = '''        # 键盘事件
        if etype == QEvent.Type.KeyPress:
            if self._handle_player_key(event.key()):
                return True'''

if old in content:
    content = content.replace(old, new)
    changes += 1
    print('Fix 2 applied: simplified video_widget eventFilter')
else:
    print('WARN: Fix 2 marker not found')

# === FIX 3: Add _handle_player_key method ===
old = '''    def _toggle_fullscreen(self):
        if self._is_fullscreen:
            self._exit_fullscreen()
        else:
            self._enter_fullscreen()

    def _enter_fullscreen(self):'''

new = '''    def _toggle_fullscreen(self):
        if self._is_fullscreen:
            self._exit_fullscreen()
        else:
            self._enter_fullscreen()

    def _handle_player_key(self, key: int) -> bool:
        """统一处理播放器快捷键，返回 True 表示已处理"""
        if key == Qt.Key.Key_Escape and self._is_fullscreen:
            self._exit_fullscreen()
            return True
        if key == Qt.Key.Key_Space:
            self._toggle_play()
            return True
        if key == Qt.Key.Key_Left:
            self._skip(-10000)
            if self._is_fullscreen:
                self._show_fullscreen_controls()
            return True
        if key == Qt.Key.Key_Right:
            self._skip(10000)
            if self._is_fullscreen:
                self._show_fullscreen_controls()
            return True
        if key == Qt.Key.Key_Up:
            vol = min(100, self.volume_slider.value() + 5)
            self.volume_slider.setValue(vol)
            if self._is_fullscreen:
                self.fullscreen_controls._volume_slider.blockSignals(True)
                self.fullscreen_controls._volume_slider.setValue(vol)
                self.fullscreen_controls._volume_slider.blockSignals(False)
                self._show_fullscreen_controls()
            return True
        if key == Qt.Key.Key_Down:
            vol = max(0, self.volume_slider.value() - 5)
            self.volume_slider.setValue(vol)
            if self._is_fullscreen:
                self.fullscreen_controls._volume_slider.blockSignals(True)
                self.fullscreen_controls._volume_slider.setValue(vol)
                self.fullscreen_controls._volume_slider.blockSignals(False)
                self._show_fullscreen_controls()
            return True
        if key == Qt.Key.Key_F or key == Qt.Key.Key_F11:
            self._toggle_fullscreen()
            return True
        if key == Qt.Key.Key_S:
            self._take_screenshot()
            return True
        if key == Qt.Key.Key_A:
            self._cycle_aspect_ratio()
            return True
        if key == Qt.Key.Key_I:
            self._show_video_info()
            return True
        if key == Qt.Key.Key_H or key == Qt.Key.Key_Question:
            self._toggle_shortcut_overlay()
            return True
        return False

    def _enter_fullscreen(self):'''

if old in content:
    content = content.replace(old, new)
    changes += 1
    print('Fix 3 applied: added _handle_player_key method')
else:
    print('WARN: Fix 3 marker not found')

# === FIX 4: Dynamic stylesheet for fullscreen controls ===
old = '''    def _build_ui(self):
        self.setFixedHeight(80)
        t = get_tokens()

        container = QWidget(self)
        container.setObjectName('FSControlsContainer')
        container.setStyleSheet(f"""
            #FSControlsContainer {{
                background-color: rgba(0, 0, 0, 200);
            }}
            QLabel {{ color: #FFFFFF; font-size: 12px; }}
            QPushButton {{
                color: #FFFFFF; background: transparent;
                border: 1px solid rgba(255,255,255,80);
                border-radius: 6px; font-size: 14px;
                padding: 2px 8px;
            }}
            QPushButton:hover {{ background: rgba(255,255,255,40); }}
            QSlider::groove:horizontal {{
                height: 6px; background: rgba(255,255,255,60); border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                width: 14px; height: 14px; margin: -4px 0;
                background: #FFFFFF; border-radius: 7px;
            }}
            QSlider::sub-page:horizontal {{ background: {t.accent}; border-radius: 3px; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(container)

        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(16, 8, 16, 8)
        main_layout.setSpacing(4)'''

new = '''    def _build_ui(self):
        self.setFixedHeight(80)

        container = QWidget(self)
        container.setObjectName('FSControlsContainer')
        self._fs_container = container
        self._apply_style()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(container)

        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(16, 8, 16, 8)
        main_layout.setSpacing(4)'''

if old in content:
    content = content.replace(old, new)
    changes += 1
    print('Fix 4 applied: dynamic fullscreen stylesheet')
else:
    print('WARN: Fix 4 marker not found')

# === FIX 5: Add _apply_style method and call in attach ===
old = '''        main_layout.addLayout(btn_row)

    def attach(self, video_widget):
        """绑定到全屏的视频控件（初始隐藏，鼠标移动时显示）"""
        self._attached = True
        # 同步当前状态'''

new = '''        main_layout.addLayout(btn_row)

    def _apply_style(self):
        """动态生成全屏控制条样式（主题切换时可更新）"""
        t = get_tokens()
        self._fs_container.setStyleSheet(f"""
            #FSControlsContainer {{
                background-color: rgba(0, 0, 0, 200);
            }}
            QLabel {{ color: #FFFFFF; font-size: 12px; }}
            QPushButton {{
                color: #FFFFFF; background: transparent;
                border: 1px solid rgba(255,255,255,80);
                border-radius: 6px; font-size: 14px;
                padding: 2px 8px;
            }}
            QPushButton:hover {{ background: rgba(255,255,255,40); }}
            QSlider::groove:horizontal {{
                height: 6px; background: rgba(255,255,255,60); border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                width: 14px; height: 14px; margin: -4px 0;
                background: #FFFFFF; border-radius: 7px;
            }}
            QSlider::sub-page:horizontal {{ background: {t.accent}; border-radius: 3px; }}
        """)

    def attach(self, video_widget):
        """绑定到全屏的视频控件（初始隐藏，鼠标移动时显示）"""
        self._attached = True
        # 刷新样式（主题可能已切换）
        self._apply_style()
        # 同步当前状态'''

if old in content:
    content = content.replace(old, new)
    changes += 1
    print('Fix 5 applied: _apply_style method')
else:
    print('WARN: Fix 5 marker not found')

# === FIX 6: Insert _OverlayBase class ===
old = '''        self._update_subtitle_delay_label()


class _FullscreenControlsOverlay(QWidget):'''

new = '''        self._update_subtitle_delay_label()


class _OverlayBase(QWidget):
    """覆盖层基类：无边框半透明 Tool 窗口，ponytail: 消除重复代码"""

    def __init__(self, player_tab: 'PlayerTab', overlay_width: int = 300):
        super().__init__(None)
        self._player_tab = player_tab
        self._overlay_width = overlay_width
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._sync_timer = QTimer(self)
        self._sync_timer.setInterval(80)
        self._sync_timer.timeout.connect(self._sync_position)
        self.hide()

    def paintEvent(self, event):
        from PyQt6.QtGui import QPainter, QColor, QPainterPath
        from PyQt6.QtCore import QRectF
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(18, 18, 40, 160))
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(4, 4, -4, -4), 12, 12)
        painter.drawPath(path)
        painter.end()

    def _sync_position(self):
        vr = self._player_tab.video_widget
        if not vr.isVisible():
            self.hide()
            return
        top_left = vr.mapToGlobal(vr.rect().topLeft())
        self.setGeometry(top_left.x(), top_left.y(),
                         min(self._overlay_width, vr.width()), vr.height())

    def show_overlay(self):
        self._sync_position()
        self.show()
        self.setFocus()
        self._sync_timer.start()

    def _close(self):
        self._sync_timer.stop()
        self.hide()
        self._player_tab.video_widget.setFocus()

    def keyPressEvent(self, event):
        self._close()

    def mousePressEvent(self, event):
        self._close()


class _FullscreenControlsOverlay(QWidget):'''

if old in content:
    content = content.replace(old, new)
    changes += 1
    print('Fix 6 applied: inserted _OverlayBase class')
else:
    print('WARN: Fix 6 marker not found')

# === FIX 7: Update _VideoInfoOverlay inheritance ===
old = '''class _VideoInfoOverlay(QWidget):
    """视频信息半透明覆盖层（独立 Tool 窗口，悬浮在 mpv 视频之上），按 I 键显示"""

    def __init__(self, player_tab: 'PlayerTab'):
        super().__init__(None)
        self._player_tab = player_tab
        self.setObjectName('VideoInfoOverlay')
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        # 跟随窗口位置同步
        self._sync_timer = QTimer(self)
        self._sync_timer.setInterval(80)
        self._sync_timer.timeout.connect(self._sync_position)
        # 实时刷新视频信息
        self._info_timer = QTimer(self)
        self._info_timer.setInterval(500)
        self._info_timer.timeout.connect(self._refresh_info)
        self._build_ui()
        self.hide()'''

new = '''class _VideoInfoOverlay(_OverlayBase):
    """视频信息半透明覆盖层（独立 Tool 窗口，悬浮在 mpv 视频之上），按 I 键显示"""

    def __init__(self, player_tab: 'PlayerTab'):
        super().__init__(player_tab, overlay_width=300)
        self.setObjectName('VideoInfoOverlay')
        # 实时刷新视频信息
        self._info_timer = QTimer(self)
        self._info_timer.setInterval(500)
        self._info_timer.timeout.connect(self._refresh_info)
        self._build_ui()'''

if old in content:
    content = content.replace(old, new)
    changes += 1
    print('Fix 7 applied: _VideoInfoOverlay inherits _OverlayBase')

    # Also remove duplicate methods from _VideoInfoOverlay
    old_extra = '''    def paintEvent(self, event):
        from PyQt6.QtGui import QPainter, QColor, QPainterPath
        from PyQt6.QtCore import QRectF
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        # 半透明：视频内容可透出
        painter.setBrush(QColor(18, 18, 40, 160))
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(4, 4, -4, -4), 12, 12)
        painter.drawPath(path)
        painter.end()

    def _sync_position(self):
        """跟随主窗口移动/缩放"""
        vr = self._player_tab.video_widget
        if not vr.isVisible():
            self.hide()
            return
        top_left = vr.mapToGlobal(vr.rect().topLeft())
        self.setGeometry(top_left.x(), top_left.y(),
                         min(300, vr.width()), vr.height())'''
    content = content.replace(old_extra, '')

    # Fix show_overlay
    old_show = '''    def show_overlay(self):
        self._sync_position()
        self.show()
        self.setFocus()
        self._sync_timer.start()
        self._last_snapshot = None
        self._info_timer.start()
        self._refresh_info()'''
    new_show = '''    def show_overlay(self):
        super().show_overlay()
        self._last_snapshot = None
        self._info_timer.start()
        self._refresh_info()

    def _close(self):
        self._info_timer.stop()
        super()._close()'''
    content = content.replace(old_show, new_show)

    # Remove old _close from _VideoInfoOverlay
    old_close = '''    def _close(self):
        self._sync_timer.stop()
        self._info_timer.stop()
        self.hide()
        self._player_tab.video_widget.setFocus()

    def keyPressEvent(self, event):
        self._close()

    def mousePressEvent(self, event):
        self._close()


'''
    if old_close in content:
        content = content.replace(old_close, '\n')
        print('Fix 7b: removed duplicate _close/keyEvent from _VideoInfoOverlay')
else:
    print('WARN: Fix 7 marker not found')

# === FIX 8: Update _ShortcutOverlay inheritance ===
old = '''class _ShortcutOverlay(QWidget):
    """键盘快捷键速查半透明覆盖层（独立 Tool 窗口，悬浮在 mpv 视频之上），按 ? 或 H 键显示"""

    SHORTCUTS = [
        ('播放控制', [
            ('Space', '播放 / 暂停'),
            ('← / →', '快退 / 快进 10 秒'),
            ('↑ / ↓', '音量增大 / 减小'),
            ('N', '下一个视频'),
            ('P', '上一个视频'),
            ('S', '截图'),
            ('A', '切换宽高比'),
            ('I', '视频信息'),
        ]),
        ('视图', [
            ('F / F11', '切换全屏'),
            ('Esc', '退出全屏'),
            ('? / H', '显示快捷键'),
        ]),
    ]

    def __init__(self, player_tab: 'PlayerTab'):
        super().__init__(None)
        self._player_tab = player_tab
        self.setObjectName('ShortcutOverlay')
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        # 跟随窗口位置同步
        self._sync_timer = QTimer(self)
        self._sync_timer.setInterval(80)
        self._sync_timer.timeout.connect(self._sync_position)
        self._build_ui()
        self.hide()

    def paintEvent(self, event):
        from PyQt6.QtGui import QPainter, QColor, QPainterPath
        from PyQt6.QtCore import QRectF
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        # 半透明：视频内容可透出
        painter.setBrush(QColor(18, 18, 40, 160))
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(4, 4, -4, -4), 12, 12)
        painter.drawPath(path)
        painter.end()

    def _sync_position(self):
        """跟随主窗口移动/缩放"""
        vr = self._player_tab.video_widget
        if not vr.isVisible():
            self.hide()
            return
        top_left = vr.mapToGlobal(vr.rect().topLeft())
        self.setGeometry(top_left.x(), top_left.y(),
                         min(340, vr.width()), vr.height())

    def _build_ui(self):'''

new = '''class _ShortcutOverlay(_OverlayBase):
    """键盘快捷键速查半透明覆盖层（独立 Tool 窗口，悬浮在 mpv 视频之上），按 ? 或 H 键显示"""

    SHORTCUTS = [
        ('播放控制', [
            ('Space', '播放 / 暂停'),
            ('← / →', '快退 / 快进 10 秒'),
            ('↑ / ↓', '音量增大 / 减小'),
            ('N', '下一个视频'),
            ('P', '上一个视频'),
            ('S', '截图'),
            ('A', '切换宽高比'),
            ('I', '视频信息'),
        ]),
        ('视图', [
            ('F / F11', '切换全屏'),
            ('Esc', '退出全屏'),
            ('? / H', '显示快捷键'),
        ]),
    ]

    def __init__(self, player_tab: 'PlayerTab'):
        super().__init__(player_tab, overlay_width=340)
        self.setObjectName('ShortcutOverlay')
        self._build_ui()

    def _build_ui(self):'''

if old in content:
    content = content.replace(old, new)
    changes += 1
    print('Fix 8 applied: _ShortcutOverlay inherits _OverlayBase')

    # Remove duplicate show_overlay, _close, keyPressEvent, mousePressEvent from _ShortcutOverlay
    old_extra2 = '''    def show_overlay(self):
        self._sync_position()
        self.show()
        self.setFocus()
        self._sync_timer.start()

    def _close(self):
        self._sync_timer.stop()
        self.hide()
        self._player_tab.video_widget.setFocus()

    def keyPressEvent(self, event):
        self._close()

    def mousePressEvent(self, event):
        self._close()'''
    content = content.replace(old_extra2, '')
    print('Fix 8b: removed duplicate methods from _ShortcutOverlay')
else:
    print('WARN: Fix 8 marker not found')

print(f'\nTotal changes applied: {changes}/8')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('File written successfully')
