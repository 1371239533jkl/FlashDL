# -*- coding: utf-8 -*-
"""主窗口 - 无边框窗口、标签页管理、系统托盘"""

from PyQt6.QtCore import Qt, QPoint, QSize, QRect, QPropertyAnimation
from PyQt6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor, QFont, QPolygon
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTabWidget, QSystemTrayIcon, QMenu, QApplication,
    QGraphicsOpacityEffect
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

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
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
        """构建界面"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 自定义标题栏
        self._title_bar = self._create_title_bar()
        main_layout.addWidget(self._title_bar)

        # 标签页
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)
        # 禁用键盘方向键切换标签页（会与全屏播放快捷键冲突）
        _orig = self.tab_widget.keyPressEvent
        def _filtered(event):
            if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
                event.ignore()
            else:
                _orig(event)
        self.tab_widget.keyPressEvent = _filtered
        main_layout.addWidget(self.tab_widget)

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

        # 主题切换过渡遮罩
        self._theme_overlay = QWidget(central)
        self._theme_overlay.hide()
        self._theme_overlay_effect = QGraphicsOpacityEffect(self._theme_overlay)
        self._theme_overlay.setGraphicsEffect(self._theme_overlay_effect)
        self._theme_overlay_effect.setOpacity(0.0)
        self._theme_overlay_anim = None

    def _create_title_bar(self) -> QWidget:
        """创建自定义标题栏"""
        bar = QWidget()
        bar.setObjectName('TitleBar')
        bar.setFixedHeight(config.TITLE_BAR_HEIGHT)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(0)

        title = QLabel(config.APP_NAME)
        title.setObjectName('TitleLabel')
        layout.addWidget(title)
        layout.addStretch()

        # 主题切换按钮 (太阳/月亮 Emoji)
        self._btn_theme = QPushButton('☀')
        self._btn_theme.setObjectName('TitleBtn')
        self._btn_theme.setFixedSize(46, config.TITLE_BAR_HEIGHT)
        self._btn_theme.setToolTip('切换浅色/深色主题')
        self._btn_theme.clicked.connect(self._toggle_theme)
        layout.addWidget(self._btn_theme)

        # 设置按钮
        self._btn_settings = QPushButton('⚙')
        self._btn_settings.setObjectName('TitleBtn')
        self._btn_settings.setFixedSize(46, config.TITLE_BAR_HEIGHT)
        self._btn_settings.setToolTip('设置')
        self._btn_settings.clicked.connect(self._open_settings)
        layout.addWidget(self._btn_settings)

        # 最小化按钮
        btn_min = QPushButton('—')
        btn_min.setObjectName('TitleBtn')
        btn_min.setFixedSize(46, config.TITLE_BAR_HEIGHT)
        btn_min.clicked.connect(self._minimize_to_tray)
        layout.addWidget(btn_min)

        # 最大化按钮
        self._btn_max = QPushButton('□')
        self._btn_max.setObjectName('TitleBtn')
        self._btn_max.setFixedSize(46, config.TITLE_BAR_HEIGHT)
        self._btn_max.clicked.connect(self._toggle_maximize)
        layout.addWidget(self._btn_max)

        # 关闭按钮
        btn_close = QPushButton('✕')
        btn_close.setObjectName('CloseBtn')
        btn_close.setFixedSize(46, config.TITLE_BAR_HEIGHT)
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close)

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
        if self.isMaximized():
            self.showNormal()
            self._btn_max.setText('□')
        else:
            self.showMaximized()
            self._btn_max.setText('▣')

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
        """切换深色/浅色主题（带淡入淡出过渡）"""
        # 停止正在进行的动画
        if self._theme_overlay_anim is not None:
            self._theme_overlay_anim.stop()
            self._theme_overlay_anim = None
        t = get_tokens()
        # 设置遮罩为当前主题背景色，完全显示
        self._theme_overlay.setStyleSheet(f'background-color: {t.bg_primary};')
        self._theme_overlay.setGeometry(self.centralWidget().rect())
        self._theme_overlay.raise_()
        self._theme_overlay.show()
        self._theme_overlay_effect.setOpacity(1.0)
        # 淡出遮罩 → 露出新主题
        self._apply_theme()
        self._fade_out_overlay()

    def _apply_theme(self):
        """应用主题切换（不含过渡）"""
        current = get_current_theme()
        new_theme = 'light' if current == 'dark' else 'dark'
        set_current_theme(new_theme)
        app = QApplication.instance()
        app.setStyleSheet(get_stylesheet(new_theme))
        app.processEvents()
        self._btn_theme.setText('☀' if new_theme == 'dark' else '🌙')
        self._app_icon = self._create_app_icon()
        self.setWindowIcon(self._app_icon)
        self.tray_icon.setIcon(self._app_icon)
        self.player_tab.video_widget.setStyleSheet('background-color: #000000; border-radius: 6px;')
        self.repaint()
        self.history_tab.refresh()

    def _fade_out_overlay(self):
        """淡出主题过渡遮罩（200ms）"""
        self._theme_overlay_anim = QPropertyAnimation(self._theme_overlay_effect, b'opacity')
        self._theme_overlay_anim.setDuration(200)
        self._theme_overlay_anim.setStartValue(1.0)
        self._theme_overlay_anim.setEndValue(0.0)
        self._theme_overlay_anim.finished.connect(self._on_overlay_fade_finished)
        self._theme_overlay_anim.start()

    def _on_overlay_fade_finished(self):
        """过渡动画结束后清理"""
        self._theme_overlay.hide()
        self._theme_overlay_anim = None

    def resizeEvent(self, event):
        """窗口大小变化时同步遮罩尺寸"""
        super().resizeEvent(event)
        if hasattr(self, '_theme_overlay'):
            self._theme_overlay.setGeometry(self.centralWidget().rect())

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
            if self.isMaximized():
                self.showNormal()
                self._btn_max.setText('□')
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
        """保存窗口位置和大小到设置"""
        geo = self.geometry()
        set_setting('window_geometry', {
            'x': geo.x(), 'y': geo.y(),
            'w': geo.width(), 'h': geo.height(),
            'maximized': self.isMaximized()
        })

    def _restore_geometry(self):
        """从设置恢复窗口位置和大小"""
        geo_data = get_setting('window_geometry', None)
        if geo_data:
            self.resize(geo_data.get('w', config.WINDOW_WIDTH),
                        geo_data.get('h', config.WINDOW_HEIGHT))
            self.move(geo_data.get('x', 0), geo_data.get('y', 0))
            if geo_data.get('maximized', False):
                self.showMaximized()
                # 延迟更新按钮文字（此时 _btn_max 可能尚未创建）
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, lambda: self._btn_max.setText('▣') if hasattr(self, '_btn_max') else None)
        else:
            self.resize(config.WINDOW_WIDTH, config.WINDOW_HEIGHT)

    def _shutdown_magnet_session(self):
        """安全关闭 libtorrent 会话"""
        try:
            from core.magnet_session_manager import MagnetSessionManager, is_libtorrent_available
            if is_libtorrent_available():
                MagnetSessionManager.get_instance().shutdown()
        except Exception:
            pass
