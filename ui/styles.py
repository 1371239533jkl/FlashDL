# -*- coding: utf-8 -*-
"""黑白主题样式 - 支持深色/浅色切换"""

from utils.settings import get as get_setting, set_value as set_setting

# 从持久化设置加载主题
_current_theme = get_setting('theme', 'dark')


def get_current_theme() -> str:
    return _current_theme


def set_current_theme(theme: str):
    global _current_theme
    _current_theme = theme
    set_setting('theme', theme)  # 持久化保存


def get_stylesheet(theme: str = None) -> str:
    """返回全局QSS样式表"""
    if theme is None:
        theme = _current_theme
    if theme == 'light':
        return _get_light_stylesheet()
    return _get_dark_stylesheet()


def _get_dark_stylesheet() -> str:
    return """
    /* === 全局 === */
    * {
        font-family: "Segoe UI Symbol", "Microsoft YaHei", "Segoe UI", sans-serif;
        font-size: 13px;
        color: #E0E0E0;
    }

    QWidget {
        background-color: #1E1E1E;
    }

    /* === 自定义标题栏 === */
    #TitleBar {
        background-color: #181818;
        border-bottom: 1px solid #2E2E2E;
    }
    #TitleLabel {
        color: #CCCCCC;
        font-size: 14px;
        font-weight: bold;
        padding-left: 10px;
    }
    #TitleBtn {
        background: transparent;
        border: none;
        color: #999999;
        font-size: 16px;
        padding: 6px 14px;
        min-width: 40px;
    }
    #TitleBtn:hover {
        background-color: #2E2E2E;
        color: #FFFFFF;
    }
    #CloseBtn:hover {
        background-color: #C42B1C;
        color: #FFFFFF;
    }

    /* === 标签栏 === */
    QTabWidget::pane {
        border: none;
        background-color: #1E1E1E;
    }
    QTabBar::tab {
        background-color: #1E1E1E;
        color: #888888;
        padding: 10px 28px;
        border: none;
        border-bottom: 2px solid transparent;
        font-size: 14px;
    }
    QTabBar::tab:selected {
        color: #FFFFFF;
        border-bottom: 2px solid #FFFFFF;
    }
    QTabBar::tab:hover {
        color: #CCCCCC;
        background-color: #252525;
    }

    /* === 按钮 === */
    QPushButton {
        background-color: #2E2E2E;
        color: #E0E0E0;
        border: 1px solid #3E3E3E;
        border-radius: 4px;
        padding: 6px 16px;
        min-height: 24px;
    }
    QPushButton:hover {
        background-color: #3E3E3E;
        color: #FFFFFF;
    }
    QPushButton:pressed {
        background-color: #505050;
    }
    QPushButton:disabled {
        background-color: #252525;
        color: #555555;
        border-color: #2E2E2E;
    }
    #PrimaryBtn {
        background-color: #FFFFFF;
        color: #1E1E1E;
        border: none;
        font-weight: bold;
    }
    #PrimaryBtn:hover {
        background-color: #E0E0E0;
    }
    #PrimaryBtn:pressed {
        background-color: #CCCCCC;
    }
    #DangerBtn:hover {
        background-color: #C42B1C;
        color: #FFFFFF;
        border-color: #C42B1C;
    }

    /* === 输入框 === */
    QLineEdit {
        background-color: #2A2A2A;
        color: #E0E0E0;
        border: 1px solid #3E3E3E;
        border-radius: 4px;
        padding: 6px 10px;
        selection-background-color: #505050;
    }
    QLineEdit:focus {
        border-color: #888888;
    }

    /* === 下拉框 === */
    QComboBox {
        background-color: #2A2A2A;
        color: #E0E0E0;
        border: 1px solid #3E3E3E;
        border-radius: 4px;
        padding: 5px 10px;
        min-width: 60px;
    }
    QComboBox::drop-down {
        border: none;
        width: 20px;
    }
    QComboBox QAbstractItemView {
        background-color: #2A2A2A;
        color: #E0E0E0;
        border: 1px solid #3E3E3E;
        selection-background-color: #3E3E3E;
    }

    /* === 进度条 === */
    QProgressBar {
        background-color: #2A2A2A;
        border: none;
        border-radius: 3px;
        height: 6px;
        text-align: center;
    }
    QProgressBar::chunk {
        background-color: #2196F3;
        border-radius: 3px;
    }

    /* === 滑块 === */
    QSlider::groove:horizontal {
        height: 4px;
        background: #3E3E3E;
        border-radius: 2px;
    }
    QSlider::handle:horizontal {
        background: #FFFFFF;
        width: 12px;
        height: 12px;
        margin: -4px 0;
        border-radius: 6px;
    }
    QSlider::sub-page:horizontal {
        background: #2196F3;
        border-radius: 2px;
    }
    QSlider::handle:horizontal:hover {
        background: #2196F3;
    }

    /* === 滚动条 === */
    QScrollArea {
        border: none;
    }
    QScrollBar:vertical {
        background: transparent;
        width: 8px;
        margin: 0;
    }
    QScrollBar::handle:vertical {
        background: #3E3E3E;
        border-radius: 4px;
        min-height: 30px;
    }
    QScrollBar::handle:vertical:hover {
        background: #555555;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: none;
        height: 0;
    }

    /* === 列表 === */
    QListWidget {
        background-color: #1E1E1E;
        border: 1px solid #2E2E2E;
        border-radius: 4px;
        outline: none;
    }
    QListWidget::item {
        padding: 8px;
        border-bottom: 1px solid #2A2A2A;
    }
    QListWidget::item:selected {
        background-color: #2E2E2E;
    }
    QListWidget::item:hover {
        background-color: #252525;
    }

    /* === 标签文本 === */
    QLabel {
        color: #E0E0E0;
        background: transparent;
    }
    #SecondaryLabel {
        color: #888888;
        font-size: 12px;
    }
    #LargeLabel {
        font-size: 18px;
        font-weight: bold;
        color: #FFFFFF;
    }

    /* === 工具提示 === */
    QToolTip {
        background-color: #2A2A2A;
        color: #E0E0E0;
        border: 1px solid #3E3E3E;
        padding: 4px 8px;
    }

    /* === 菜单 === */
    QMenu {
        background-color: #2A2A2A;
        border: 1px solid #3E3E3E;
        padding: 4px 0;
    }
    QMenu::item {
        padding: 6px 30px;
    }
    QMenu::item:selected {
        background-color: #3E3E3E;
    }

    /* === 播放器控制条 === */
    #PlayerControls {
        background-color: #181818;
        padding: 4px 12px;
    }

    /* === 下载任务卡片 === */
    #TaskCard {
        background-color: #252525;
        border: 1px solid #2E2E2E;
        border-radius: 6px;
        padding: 12px;
    }
    #TaskCard:hover {
        border-color: #3E3E3E;
    }
    """


def _get_light_stylesheet() -> str:
    return """
    /* === 全局 === */
    * {
        font-family: "Segoe UI Symbol", "Microsoft YaHei", "Segoe UI", sans-serif;
        font-size: 13px;
        color: #1E1E1E;
    }

    QWidget {
        background-color: #F5F5F5;
    }

    /* === 自定义标题栏 === */
    #TitleBar {
        background-color: #EAEAEA;
        border-bottom: 1px solid #D0D0D0;
    }
    #TitleLabel {
        color: #1E1E1E;
        font-size: 14px;
        font-weight: bold;
        padding-left: 10px;
    }
    #TitleBtn {
        background: transparent;
        border: none;
        color: #666666;
        font-size: 16px;
        padding: 6px 14px;
        min-width: 40px;
    }
    #TitleBtn:hover {
        background-color: #D0D0D0;
        color: #1E1E1E;
    }
    #CloseBtn:hover {
        background-color: #C42B1C;
        color: #FFFFFF;
    }

    /* === 标签栏 === */
    QTabWidget::pane {
        border: none;
        background-color: #F5F5F5;
    }
    QTabBar::tab {
        background-color: #F5F5F5;
        color: #888888;
        padding: 10px 28px;
        border: none;
        border-bottom: 2px solid transparent;
        font-size: 14px;
    }
    QTabBar::tab:selected {
        color: #1E1E1E;
        border-bottom: 2px solid #1E1E1E;
    }
    QTabBar::tab:hover {
        color: #444444;
        background-color: #E8E8E8;
    }

    /* === 按钮 === */
    QPushButton {
        background-color: #E0E0E0;
        color: #1E1E1E;
        border: 1px solid #C0C0C0;
        border-radius: 4px;
        padding: 6px 16px;
        min-height: 24px;
    }
    QPushButton:hover {
        background-color: #D0D0D0;
        color: #000000;
    }
    QPushButton:pressed {
        background-color: #B0B0B0;
    }
    QPushButton:disabled {
        background-color: #E8E8E8;
        color: #AAAAAA;
        border-color: #D0D0D0;
    }
    #PrimaryBtn {
        background-color: #1E1E1E;
        color: #FFFFFF;
        border: none;
        font-weight: bold;
    }
    #PrimaryBtn:hover {
        background-color: #333333;
    }
    #PrimaryBtn:pressed {
        background-color: #444444;
    }
    #DangerBtn:hover {
        background-color: #C42B1C;
        color: #FFFFFF;
        border-color: #C42B1C;
    }

    /* === 输入框 === */
    QLineEdit {
        background-color: #FFFFFF;
        color: #1E1E1E;
        border: 1px solid #C0C0C0;
        border-radius: 4px;
        padding: 6px 10px;
        selection-background-color: #B0D0FF;
    }
    QLineEdit:focus {
        border-color: #666666;
    }

    /* === 下拉框 === */
    QComboBox {
        background-color: #FFFFFF;
        color: #1E1E1E;
        border: 1px solid #C0C0C0;
        border-radius: 4px;
        padding: 5px 10px;
        min-width: 60px;
    }
    QComboBox::drop-down {
        border: none;
        width: 24px;
    }
    QComboBox::down-arrow {
        width: 12px;
    }
    QComboBox QAbstractItemView {
        background-color: #FFFFFF;
        color: #1E1E1E;
        border: 1px solid #C0C0C0;
        selection-background-color: #D0D0D0;
    }

    /* === 进度条 === */
    QProgressBar {
        background-color: #D8D8D8;
        border: none;
        border-radius: 3px;
        height: 6px;
        text-align: center;
    }
    QProgressBar::chunk {
        background-color: #1E1E1E;
        border-radius: 3px;
    }

    /* === 滑块 === */
    QSlider::groove:horizontal {
        height: 4px;
        background: #C0C0C0;
        border-radius: 2px;
    }
    QSlider::handle:horizontal {
        background: #1E1E1E;
        width: 12px;
        height: 12px;
        margin: -4px 0;
        border-radius: 6px;
    }
    QSlider::sub-page:horizontal {
        background: #2196F3;
        border-radius: 2px;
    }
    QSlider::handle:horizontal:hover {
        background: #2196F3;
    }

    /* === 滚动条 === */
    QScrollArea {
        border: none;
    }
    QScrollBar:vertical {
        background: transparent;
        width: 8px;
        margin: 0;
    }
    QScrollBar::handle:vertical {
        background: #C0C0C0;
        border-radius: 4px;
        min-height: 30px;
    }
    QScrollBar::handle:vertical:hover {
        background: #999999;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: none;
        height: 0;
    }

    /* === 列表 === */
    QListWidget {
        background-color: #FFFFFF;
        border: 1px solid #D0D0D0;
        border-radius: 4px;
        outline: none;
    }
    QListWidget::item {
        padding: 8px;
        border-bottom: 1px solid #E8E8E8;
    }
    QListWidget::item:selected {
        background-color: #E0E0E0;
    }
    QListWidget::item:hover {
        background-color: #F0F0F0;
    }

    /* === 标签文本 === */
    QLabel {
        color: #1E1E1E;
        background: transparent;
    }
    #SecondaryLabel {
        color: #666666;
        font-size: 12px;
    }
    #LargeLabel {
        font-size: 18px;
        font-weight: bold;
        color: #1E1E1E;
    }

    /* === 工具提示 === */
    QToolTip {
        background-color: #FFFFFF;
        color: #1E1E1E;
        border: 1px solid #C0C0C0;
        padding: 4px 8px;
    }

    /* === 菜单 === */
    QMenu {
        background-color: #FFFFFF;
        border: 1px solid #C0C0C0;
        padding: 4px 0;
    }
    QMenu::item {
        padding: 6px 30px;
    }
    QMenu::item:selected {
        background-color: #E0E0E0;
    }

    /* === 播放器控制条 === */
    #PlayerControls {
        background-color: #EAEAEA;
        padding: 4px 12px;
    }

    /* === 下载任务卡片 === */
    #TaskCard {
        background-color: #FFFFFF;
        border: 1px solid #D0D0D0;
        border-radius: 6px;
        padding: 12px;
    }
    #TaskCard:hover {
        border-color: #B0B0B0;
    }
    """
