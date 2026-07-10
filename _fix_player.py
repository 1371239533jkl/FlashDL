import sys
path = r'c:\Users\18665\OneDrive\桌面\Qoder\video-downloader\ui\player_tab.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Step 1: Find insertion point
marker = 'class _FullscreenControlsOverlay(QWidget):'
if marker not in content:
    print('ERROR: marker not found', file=sys.stderr)
    sys.exit(1)

base_class = '''
class _OverlayBase(QWidget):
    """覆盖层基类，ponytail: 消除重复代码"""
    def __init__(self, player_tab, overlay_width=300):
        super().__init__(None)
        self._player_tab = player_tab
        self._overlay_width = overlay_width
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._sync_timer = QTimer(self)
        self._sync_timer.setInterval(80)
        self._sync_timer.timeout.connect(self._sync_position)
        self.hide()
    def paintEvent(self, event):
        from PyQt6.QtGui import QPainter, QColor, QPainterPath
        from PyQt6.QtCore import QRectF
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(18, 18, 40, 160))
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(4, 4, -4, -4), 12, 12)
        p.drawPath(path)
        p.end()
    def _sync_position(self):
        vr = self._player_tab.video_widget
        if not vr.isVisible():
            self.hide()
            return
        tl = vr.mapToGlobal(vr.rect().topLeft())
        self.setGeometry(tl.x(), tl.y(), min(self._overlay_width, vr.width()), vr.height())
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
'''

# Insert
content = content.replace(marker, base_class + marker)

# Fix inheritance
content = content.replace('class _VideoInfoOverlay(QWidget):', 'class _VideoInfoOverlay(_OverlayBase):')
content = content.replace('class _ShortcutOverlay(QWidget):', 'class _ShortcutOverlay(_OverlayBase):')

# Fix _VideoInfoOverlay.__init__ to use super().__init__(player_tab, overlay_width=300)
old_init = """    def __init__(self, player_tab: 'PlayerTab'):
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
        self.hide()"""
new_init = """    def __init__(self, player_tab: 'PlayerTab'):
        super().__init__(player_tab, overlay_width=300)
        self.setObjectName('VideoInfoOverlay')
        # 实时刷新视频信息
        self._info_timer = QTimer(self)
        self._info_timer.setInterval(500)
        self._info_timer.timeout.connect(self._refresh_info)
        self._build_ui()"""
if old_init in content:
    content = content.replace(old_init, new_init)
    print('Fixed _VideoInfoOverlay init')
else:
    print('Old _VideoInfoOverlay init not found')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('File written successfully')
