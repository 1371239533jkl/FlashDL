"""Fix player_tab.py: insert _OverlayBase and update inheritance."""
path = r'c:\Users\18665\OneDrive\桌面\Qoder\video-downloader\ui\player_tab.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find line numbers for each class
class_lines = {}
for i, line in enumerate(lines):
    stripped = line.strip()
    if stripped.startswith('class _'):
        name = stripped.split('(')[0].replace('class ', '').strip()
        class_lines[name] = i

print(f"Classes found: {class_lines}")

overlay_base_lines = [
    '\n',
    'class _OverlayBase(QWidget):\n',
    '    """覆盖层基类：独立的无边框半透明 Tool 窗口，ponytail: 消除重复代码"""\n',
    '\n',
    "    def __init__(self, player_tab: 'PlayerTab', overlay_width: int = 300):\n",
    '        super().__init__(None)\n',
    '        self._player_tab = player_tab\n',
    '        self._overlay_width = overlay_width\n',
    '        self.setWindowFlags(\n',
    '            Qt.WindowType.FramelessWindowHint\n',
    '            | Qt.WindowType.Tool\n',
    '            | Qt.WindowType.WindowStaysOnTopHint\n',
    '        )\n',
    '        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)\n',
    '        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)\n',
    '        self._sync_timer = QTimer(self)\n',
    '        self._sync_timer.setInterval(80)\n',
    '        self._sync_timer.timeout.connect(self._sync_position)\n',
    '        self.hide()\n',
    '\n',
    '    def paintEvent(self, event):\n',
    '        from PyQt6.QtGui import QPainter, QColor, QPainterPath\n',
    '        from PyQt6.QtCore import QRectF\n',
    '        painter = QPainter(self)\n',
    '        painter.setRenderHint(QPainter.RenderHint.Antialiasing)\n',
    '        painter.setPen(Qt.PenStyle.NoPen)\n',
    '        painter.setBrush(QColor(18, 18, 40, 160))\n',
    '        path = QPainterPath()\n',
    '        path.addRoundedRect(QRectF(self.rect()).adjusted(4, 4, -4, -4), 12, 12)\n',
    '        painter.drawPath(path)\n',
    '        painter.end()\n',
    '\n',
    '    def _sync_position(self):\n',
    '        vr = self._player_tab.video_widget\n',
    '        if not vr.isVisible():\n',
    '            self.hide()\n',
    '            return\n',
    '        top_left = vr.mapToGlobal(vr.rect().topLeft())\n',
    '        self.setGeometry(top_left.x(), top_left.y(),\n',
    '                         min(self._overlay_width, vr.width()), vr.height())\n',
    '\n',
    '    def show_overlay(self):\n',
    '        self._sync_position()\n',
    '        self.show()\n',
    '        self.setFocus()\n',
    '        self._sync_timer.start()\n',
    '\n',
    '    def _close(self):\n',
    '        self._sync_timer.stop()\n',
    '        self.hide()\n',
    '        self._player_tab.video_widget.setFocus()\n',
    '\n',
    '    def keyPressEvent(self, event):\n',
    '        self._close()\n',
    '\n',
    '    def mousePressEvent(self, event):\n',
    '        self._close()\n',
    '\n',
]

# Insert _OverlayBase before _FullscreenControlsOverlay
insert_at = class_lines['_FullscreenControlsOverlay']
for line in reversed(overlay_base_lines):
    lines.insert(insert_at, line)

# Update inheritance
for i, line in enumerate(lines):
    if line.strip() == 'class _VideoInfoOverlay(QWidget):':
        lines[i] = line.replace('(QWidget)', '(_OverlayBase)')
        print(f'Fixed _VideoInfoOverlay at line {i+1}')
    if line.strip() == 'class _ShortcutOverlay(QWidget):':
        lines[i] = line.replace('(QWidget)', '(_OverlayBase)')
        print(f'Fixed _ShortcutOverlay at line {i+1}')

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('Done')
