# -*- coding: utf-8 -*-
"""主窗口 - 无边框窗口、标签页管理、系统托盘"""

from PyQt6.QtCore import Qt, QPoint, QSize, QRect, QCoreApplication
from PyQt6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor, QPen, QPolygon
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTabWidget, QSystemTrayIcon, QMenu, QApplication
)

import config
from utils.signal_bus import signal_bus
from utils.settings import get as get_setting, set_value as set_setting
from ui.styles import get_stylesheet, get_current_theme, set_current_theme, get_tokens


class MainWindow(QMainWindow):
    """应用程序主窗口"""

    def __init__(self, download_manager):
        super().__init__()
        self.download_manager = download_manager
        self._drag_pos = None
        self._resizing = False
        self._resize_edge = None
        self._resize_margin = 6
        self._is_maximized = False

        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setMinimumSize(config.MIN_WINDOW_WIDTH, config.MIN_WINDOW_HEIGHT)
        self._restore_geometry()
        self.setWindowTitle(config.APP_NAME)

        # 生成应用图标
        self._app_icon = self._create_app_icon()
        self.setWindowIcon(self._app_icon)

        self._setup_ui()
        self._setup_tray()
        self._connect_signals()

    def _create_app_icon(self) -> QIcon:
        """生成应用图标 (accent 渐变背景 + 白色下载箭头)"""
        t = get_tokens()
        pixmap = QPixmap(64, 64)
        pixmap.fill(QColor(t.bg_elevated))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        # 圆角矩形背景
        painter.setBrush(QColor(t.accent))
        painter.drawRoundedRect(QRect(2, 2, 60, 60), 14, 14)
        # 白色下载箭头
        painter.setBrush(QColor('#FFFFFF'))
        painter.drawRect(QRect(24, 14, 16, 24))
        arrow = QPolygon([QPoint(14, 36), QPoint(50, 36), QPoint(32, 50)])
        painter.drawPolygon(arrow)
        painter.end()
        return QIcon(pixmap)

    def _setup_ui(self):
        """构建界面 - 侧边栏 + (标题栏 + 标签页)"""
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── 左侧边栏 ──
        self._sidebar = self._create_sidebar()
        root_layout.addWidget(self._sidebar)

        # ── 右侧主体 ──
        main_area = QWidget()
        main_layout = QVBoxLayout(main_area)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 自定义标题栏
        self._title_bar = self._create_title_bar()
        main_layout.addWidget(self._title_bar)

        # 标签页
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)
        # 隐藏原生标签栏（使用自定义 TabBar 替代 QTabBar）
        self.tab_widget.tabBar().hide()
        # 禁用键盘方向键切换标签页（会与全屏播放快捷键冲突）
        # 但播放器页面需要方向键，所以仅当非播放器页面时才忽略
        _orig = self.tab_widget.keyPressEvent
        def _filtered(event):
            if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
                if self.tab_widget.currentWidget() is self.player_tab:
                    QCoreApplication.sendEvent(self.player_tab.video_widget, event)
                    return
                event.ignore()
            else:
                _orig(event)
        self.tab_widget.keyPressEvent = _filtered
        main_layout.addWidget(self.tab_widget)

        root_layout.addWidget(main_area)

        # 延迟导入标签页(避免循环导入)
        from ui.download_tab import DownloadTab
        from ui.player_tab import PlayerTab
        from ui.history_tab import HistoryTab

        self.download_tab = DownloadTab(self.download_manager)
        self.player_tab = PlayerTab()
        self.history_tab = HistoryTab()

        self.tab_widget.addTab(self.download_tab, '下载管理')
        self.tab_widget.addTab(self.player_tab, '视频播放')
        self.tab_widget.addTab(self.history_tab, '历史记录')

    def _create_sidebar(self) -> QWidget:
        """创建左侧 48px 图标导航栏（使用自绘图标）"""
        sidebar = QWidget()
        sidebar.setObjectName('Sidebar')
        sidebar.setFixedWidth(config.SIDEBAR_WIDTH)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(6, 12, 6, 12)
        layout.setSpacing(4)

        icons_data = [
            (0, 'download', '下载管理'),
            (1, 'play', '视频播放'),
            (2, 'history', '历史记录'),
        ]
        self._sidebar_icons: dict[int, QPushButton] = {}
        for tab_idx, icon_type, tip in icons_data:
            btn = QPushButton()
            btn.setObjectName('SidebarIcon')
            btn.setToolTip(tip)
            btn.setFixedSize(36, 36)
            btn.setIcon(self._make_sidebar_icon(icon_type))
            btn.setIconSize(QSize(24, 24))
            btn.clicked.connect(lambda checked, i=tab_idx: self._on_sidebar_click(i))
            self._sidebar_icons[tab_idx] = btn
            layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        # 标记初始激活
        self._sidebar_icons[0].setProperty('active', True)
        self._sidebar_icons[0].setIcon(self._make_sidebar_icon('download', active=True))
        self._sidebar_icons[0].style().unpolish(self._sidebar_icons[0])
        self._sidebar_icons[0].style().polish(self._sidebar_icons[0])

        layout.addStretch()

        # 设置按钮
        btn_settings = QPushButton()
        btn_settings.setObjectName('SidebarIcon')
        btn_settings.setToolTip('设置')
        btn_settings.setFixedSize(36, 36)
        btn_settings.setIcon(self._make_sidebar_icon('settings'))
        btn_settings.setIconSize(QSize(24, 24))
        btn_settings.clicked.connect(self._open_settings)
        layout.addWidget(btn_settings, alignment=Qt.AlignmentFlag.AlignHCenter)

        # 快捷键提示：sidebar 仅 48px，使用极简文案避免文字被截断；完整提示放在 tooltip 中
        shortcut_hint = QLabel('1/2/3\n切换页')
        shortcut_hint.setObjectName('SidebarShortcut')
        shortcut_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shortcut_hint.setWordWrap(True)
        shortcut_hint.setToolTip('Ctrl+1/2/3 切换页面')
        layout.addWidget(shortcut_hint, alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)

        return sidebar

    
    def _make_sidebar_icon(self, icon_type: str, active: bool = False) -> QIcon:
        """绘制侧边栏单色图标（24px，更显眼，缓存避免重复创建）"""
        cache_key = (icon_type, active, get_current_theme())
        if not hasattr(self, '_icon_cache'):
            self._icon_cache = {}
        if cache_key in self._icon_cache:
            return self._icon_cache[cache_key]

        from ui.styles import get_tokens
        t = get_tokens()
        size = 36
        icon_size = 24
        color = t.accent if active else t.text_secondary
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        x = (size - icon_size) // 2  # = 6
        y = (size - icon_size) // 2  # = 6
        if icon_type == 'download':
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(color))
            p.drawRect(x + 9, y + 2, 6, 11)
            triangle = QPolygon([
                QPoint(x + 3, y + 13),
                QPoint(x + 21, y + 13),
                QPoint(x + 12, y + 22)
            ])
            p.drawPolygon(triangle)
        elif icon_type == 'play':
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(color))
            triangle = QPolygon([
                QPoint(x + 4, y + 3),
                QPoint(x + 4, y + 21),
                QPoint(x + 20, y + 12)
            ])
            p.drawPolygon(triangle)
        elif icon_type == 'history':
            p.setBrush(Qt.BrushStyle.NoBrush)
            pen = QPen(QColor(color), 2)
            p.setPen(pen)
            p.drawEllipse(x + 2, y + 2, 20, 20)
            p.drawLine(x + 12, y + 7, x + 12, y + 13)
            p.drawLine(x + 12, y + 13, x + 17, y + 13)
        elif icon_type == 'settings':
            p.setBrush(Qt.BrushStyle.NoBrush)
            pen = QPen(QColor(color), 2)
            p.setPen(pen)
            # 三条水平线 + 滑动圆点（调音台图标）
            p.drawLine(x + 2, y + 5, x + 20, y + 5)
            p.drawLine(x + 2, y + 12, x + 20, y + 12)
            p.drawLine(x + 2, y + 19, x + 20, y + 19)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(color))
            p.drawEllipse(x + 7, y + 2, 7, 7)
            p.drawEllipse(x + 13, y + 9, 7, 7)
            p.drawEllipse(x + 4, y + 16, 7, 7)
        p.end()
        icon = QIcon(pix)
        self._icon_cache[cache_key] = icon
        return icon



    def _on_sidebar_click(self, index: int):
        """侧边栏导航点击"""
        self.tab_widget.setCurrentIndex(index)
        self._update_sidebar_active(index)

    def _on_tab_changed(self, index: int):
        """标签页切换时同步侧边栏"""
        self._update_sidebar_active(index)

    def _update_sidebar_active(self, index: int):
        """更新侧边栏图标激活状态"""
        icons = ['download', 'play', 'history']
        for i, btn in self._sidebar_icons.items():
            is_active = (i == index)
            btn.setProperty('active', is_active)
            btn.setIcon(self._make_sidebar_icon(icons[i], active=is_active))
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _create_title_bar(self) -> QWidget:
        """创建自定义标题栏 (44px)"""
        bar = QWidget()
        bar.setObjectName('TitleBar')
        bar.setFixedHeight(config.TITLE_BAR_HEIGHT)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(4)

        # 标题
        title = QLabel('FlashDL')
        title.setObjectName('TitleLabel')
        layout.addWidget(title)

        version = QLabel(f'v{config.APP_VERSION}')
        version.setObjectName('TitleVersion')
        layout.addWidget(version)

        layout.addStretch()

        # 主题切换按钮
        self._btn_theme = QPushButton('☀')
        self._btn_theme.setObjectName('TitleBtn')
        self._btn_theme.setFixedSize(28, 28)
        self._btn_theme.setToolTip('切换浅色/深色主题')
        self._btn_theme.clicked.connect(self._toggle_theme)
        layout.addWidget(self._btn_theme)

        # 最小化按钮
        self._btn_min = QPushButton('—')
        self._btn_min.setObjectName('TitleBtn')
        self._btn_min.setFixedSize(28, 28)
        self._btn_min.clicked.connect(self._minimize_to_tray)
        layout.addWidget(self._btn_min)

        # 最大化按钮
        self._btn_max = QPushButton('□')
        self._btn_max.setObjectName('TitleBtn')
        self._btn_max.setFixedSize(28, 28)
        self._btn_max.clicked.connect(self._toggle_maximize)
        layout.addWidget(self._btn_max)

        # 关闭按钮
        self._btn_close = QPushButton('X')
        self._btn_close.setObjectName('CloseBtn')
        self._btn_close.setFixedSize(28, 28)
        self._btn_close.clicked.connect(self.close)
        layout.addWidget(self._btn_close)






        return bar

    def _setup_tray(self):
        """设置系统托盘"""
        self.tray_icon = QSystemTrayIcon(self._app_icon, self)

        tray_menu = QMenu()
        show_action = QAction('显示主窗口', self)
        show_action.triggered.connect(self._show_from_tray)
        tray_menu.addAction(show_action)

        tray_menu.addSeparator()

        quit_action = QAction('退出', self)
        quit_action.triggered.connect(self._quit_app)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _connect_signals(self):
        """连接全局信号"""
        signal_bus.show_notification.connect(self._show_tray_notification)
        signal_bus.play_video.connect(self._play_video)
        # 标签页切换时更新侧边栏
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

    def _show_tray_notification(self, title: str, message: str):
        """显示托盘通知"""
        if self.tray_icon.isVisible():
            self.tray_icon.showMessage(title, message,
                                       QSystemTrayIcon.MessageIcon.Information, 3000)

    def _play_video(self, file_path: str):
        """切换到播放器页面并播放视频"""
        self.tab_widget.setCurrentWidget(self.player_tab)
        self.player_tab.play_file(file_path)

    def _minimize_to_tray(self):
        """最小化到系统托盘"""
        self.hide()
        self.tray_icon.showMessage(config.APP_NAME, '程序已最小化到系统托盘',
                                   QSystemTrayIcon.MessageIcon.Information, 1500)

    def _show_from_tray(self):
        """从托盘恢复窗口"""
        self.show()
        self.activateWindow()
        self.raise_()

    def _toggle_maximize(self):
        if self._is_maximized:
            self._is_maximized = False
            self._btn_max.setText('□')
            self.setGeometry(self._normal_geo)
        else:
            self._normal_geo = self.geometry()
            self._is_maximized = True
            self._btn_max.setText('▣')
            screen = QApplication.primaryScreen()
            if screen:
                self.setGeometry(screen.availableGeometry())



    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_from_tray()

    def _quit_app(self):
        """退出应用"""
        self._save_geometry()
        self.download_manager.save_all_tasks()
        self.player_tab.cleanup()       # 保存播放进度等
        self._shutdown_magnet_session()
        self.tray_icon.hide()
        QApplication.quit()

    def _open_settings(self):
        """打开设置对话框"""
        from ui.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self)
        dlg.exec()

    def _toggle_theme(self):
        """切换深色/浅色主题"""
        current = get_current_theme()
        new_theme = 'light' if current == 'dark' else 'dark'
        set_current_theme(new_theme)
        app = QApplication.instance()
        # 禁用更新以减少闪烁
        self.setUpdatesEnabled(False)
        app.setStyleSheet(get_stylesheet(new_theme))
        self._btn_theme.setText('☀' if new_theme == 'dark' else '🌙')
        self._app_icon = self._create_app_icon()
        self.setWindowIcon(self._app_icon)
        self.tray_icon.setIcon(self._app_icon)
        # 清除图标缓存（主题变了颜色也变了）
        if hasattr(self, '_icon_cache'):
            self._icon_cache.clear()
        # 清除历史记录图标缓存
        import ui.history_tab as _ht
        if hasattr(_ht, '_icon_cache'):
            _ht._icon_cache.clear()
        # 只重绘侧边栏图标（它们需要手动更新颜色）
        icons = ['download', 'play', 'history']
        for i, btn in self._sidebar_icons.items():
            is_active = btn.property('active') or False
            btn.setIcon(self._make_sidebar_icon(icons[i], active=is_active))
        self.setUpdatesEnabled(True)
        # 一次性强制刷新
        self.repaint()
        self.history_tab.refresh()

    # === 窗口拖动与缩放 ===
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            edge = self._get_resize_edge(pos)
            if edge:
                self._resizing = True
                self._resize_edge = edge
                self._drag_pos = event.globalPosition().toPoint()
            elif pos.y() <= config.TITLE_BAR_HEIGHT:
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()

        if self._resizing and self._drag_pos:
            self._do_resize(event.globalPosition().toPoint())
            return

        if self._drag_pos and not self._resizing and pos.y() <= config.TITLE_BAR_HEIGHT:
            if self._is_maximized:
                self._is_maximized = False
                self._btn_max.setText('□')
                self.setGeometry(self._normal_geo)
                # Recalculate drag after restore
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            return

        # 更新鼠标光标
        edge = self._get_resize_edge(pos)
        if edge in ('left', 'right'):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif edge in ('top', 'bottom'):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        elif edge in ('top-left', 'bottom-right'):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif edge in ('top-right', 'bottom-left'):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        self._resizing = False
        self._resize_edge = None
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseDoubleClickEvent(self, event):
        if event.position().toPoint().y() <= config.TITLE_BAR_HEIGHT:
            self._toggle_maximize()

    def _get_resize_edge(self, pos) -> str:
        """检测鼠标所在的缩放边缘"""
        m = self._resize_margin
        w, h = self.width(), self.height()
        x, y = pos.x(), pos.y()

        on_left = x <= m
        on_right = x >= w - m
        on_top = y <= m
        on_bottom = y >= h - m

        if on_top and on_left: return 'top-left'
        if on_top and on_right: return 'top-right'
        if on_bottom and on_left: return 'bottom-left'
        if on_bottom and on_right: return 'bottom-right'
        if on_left: return 'left'
        if on_right: return 'right'
        if on_top: return 'top'
        if on_bottom: return 'bottom'
        return ''

    def _do_resize(self, global_pos):
        """执行窗口缩放"""
        delta = global_pos - self._drag_pos
        self._drag_pos = global_pos
        geo = self.geometry()
        edge = self._resize_edge

        if 'right' in edge:
            geo.setRight(geo.right() + delta.x())
        if 'bottom' in edge:
            geo.setBottom(geo.bottom() + delta.y())
        if 'left' in edge:
            geo.setLeft(geo.left() + delta.x())
        if 'top' in edge:
            geo.setTop(geo.top() + delta.y())

        if geo.width() >= self.minimumWidth() and geo.height() >= self.minimumHeight():
            self.setGeometry(geo)

    def closeEvent(self, event):
        """关闭窗口时保存任务并退出"""
        self._save_geometry()
        self.download_manager.save_all_tasks()
        self._shutdown_magnet_session()
        self.player_tab.cleanup()
        self.tray_icon.hide()
        event.accept()

    def _save_geometry(self):
        """保存窗口位置和大小到设置（仅保存非最大化状态）"""
        if self.isMaximized():
            return  # 最大化时不保存几何信息，避免下次启动异常
        geo = self.geometry()
        set_setting('window_geometry', {
            'x': geo.x(), 'y': geo.y(),
            'w': geo.width(), 'h': geo.height(),
        })

    def _restore_geometry(self):
        """恢复上次关闭时的窗口位置和大小"""
        geo_data = get_setting('window_geometry', None)
        if geo_data:
            w, h = geo_data.get('w', 0), geo_data.get('h', 0)
            x, y = geo_data.get('x', 0), geo_data.get('y', 0)
            screen = QApplication.primaryScreen()
            if screen and w > 0 and h > 0:
                sg = screen.availableGeometry()
                # 钳制到屏幕范围内
                w = min(w, sg.width())
                h = min(h, sg.height())
                x = max(sg.x(), min(x, sg.x() + sg.width() - 200))
                y = max(sg.y(), min(y, sg.y() + sg.height() - 200))
                self.resize(w, h)
                self.move(x, y)
                return
        # 无保存数据时，默认大小居中
        self.resize(config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        screen = QApplication.primaryScreen()
        if screen:
            sg = screen.availableGeometry()
            self.move(sg.x() + (sg.width() - config.WINDOW_WIDTH) // 2,
                      sg.y() + (sg.height() - config.WINDOW_HEIGHT) // 2)

    def _shutdown_magnet_session(self):
        """安全关闭 libtorrent 会话"""
        try:
            from core.magnet_session_manager import MagnetSessionManager, is_libtorrent_available
            if is_libtorrent_available():
                MagnetSessionManager.get_instance().shutdown()
        except Exception:
            import traceback
            traceback.print_exc()
