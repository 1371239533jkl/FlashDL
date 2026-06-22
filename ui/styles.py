# -*- coding: utf-8 -*-
"""FlashDL 设计系统 — Design Tokens + 双主题 QSS 生成"""

from dataclasses import dataclass
from utils.settings import get as get_setting, set_value as set_setting

_current_theme = get_setting('theme', 'dark')


def get_current_theme() -> str:
    return _current_theme


def set_current_theme(theme: str):
    global _current_theme
    _current_theme = theme
    set_setting('theme', theme)


# ── Design Tokens ──────────────────────────────────────────────

@dataclass
class DesignTokens:
    """所有设计 Token 的集中定义"""
    # 背景
    bg_primary: str
    bg_surface: str
    bg_elevated: str
    bg_input: str
    # 边框
    border_default: str
    border_hover: str
    # 文字
    text_primary: str
    text_secondary: str
    text_muted: str
    # 强调色
    accent: str
    accent_hover: str
    accent_dim: str
    # 语义色
    success: str
    error: str
    warning: str


# 深色主题 Token
DARK = DesignTokens(
    bg_primary='#0A0A0F',
    bg_surface='#14141F',
    bg_elevated='#1C1C2E',
    bg_input='#16162A',
    border_default='#2A2A3C',
    border_hover='#3D3D5C',
    text_primary='#E4E4EC',
    text_secondary='#8888A0',
    text_muted='#5C5C78',
    accent='#6C5CE7',
    accent_hover='#7C6CF0',
    accent_dim='#5A4BD1',
    success='#4ADE80',
    error='#F87171',
    warning='#FBBF24',
)

# 浅色主题 Token
LIGHT = DesignTokens(
    bg_primary='#F5F5FA',
    bg_surface='#FFFFFF',
    bg_elevated='#EEEEF5',
    bg_input='#FFFFFF',
    border_default='#DCDCE8',
    border_hover='#C0C0D0',
    text_primary='#1A1A2E',
    text_secondary='#6B6B80',
    text_muted='#9A9AB0',
    accent='#5B4AE6',
    accent_hover='#6B5AF8',
    accent_dim='#4A3AD1',
    success='#22C55E',
    error='#EF4444',
    warning='#EAB308',
)


def get_tokens(theme: str = None) -> DesignTokens:
    """获取当前主题的设计 Token"""
    if theme is None:
        theme = _current_theme
    return DARK if theme == 'dark' else LIGHT


def get_stylesheet(theme: str = None) -> str:
    """返回全局 QSS 样式表"""
    if theme is None:
        theme = _current_theme
    return _build_stylesheet(theme)


def _build_stylesheet(theme: str) -> str:
    t = get_tokens(theme)
    is_dark = theme == 'dark'

    # 选中文字色（深色用白，浅色用黑）
    selected_text = '#0A0A0F' if is_dark else '#FFFFFF'

    return f"""
    /* ═══ FlashDL 设计系统 — {"深色" if is_dark else "浅色"}主题 ═══ */

    * {{
        font-family: "Segoe UI Symbol", "Microsoft YaHei", "Segoe UI", sans-serif;
        font-size: 13px;
        color: {t.text_primary};
    }}

    QWidget {{
        background-color: {t.bg_primary};
    }}

    /* ── 标题栏 ── */
    #TitleBar {{
        background-color: {t.bg_elevated};
        border-bottom: 1px solid {t.border_default};
    }}
    #TitleLabel {{
        color: {t.text_secondary};
        font-size: 14px;
        font-weight: 600;
        padding-left: 10px;
        background: transparent;
    }}
    #TitleBtn {{
        background: transparent;
        border: none;
        color: {t.text_secondary};
        font-size: 16px;
        padding: 6px 14px;
        min-width: 40px;
    }}
    #TitleBtn:hover {{
        background-color: {t.bg_surface};
        color: {t.text_primary};
    }}
    #CloseBtn:hover {{
        background-color: {t.error};
        color: #FFFFFF;
    }}

    /* ── 标签栏 ── */
    QTabWidget::pane {{
        border: none;
        background-color: {t.bg_primary};
    }}
    QTabBar::tab {{
        background-color: transparent;
        color: {t.text_muted};
        padding: 10px 28px;
        border: none;
        border-bottom: 2px solid transparent;
        font-size: 14px;
        font-weight: 500;
    }}
    QTabBar::tab:selected {{
        color: {t.accent};
        border-bottom: 2px solid {t.accent};
    }}
    QTabBar::tab:hover:!selected {{
        color: {t.text_secondary};
        background-color: {t.bg_surface};
    }}

    /* ── 按钮 ── */
    QPushButton {{
        background-color: {t.bg_surface};
        color: {t.text_primary};
        border: 1px solid {t.border_default};
        border-radius: 6px;
        padding: 5px 14px;
        min-height: 26px;
    }}
    QPushButton:hover {{
        background-color: {t.bg_elevated};
        border-color: {t.border_hover};
    }}
    QPushButton:pressed {{
        background-color: {t.bg_input};
    }}
    QPushButton:disabled {{
        background-color: {t.bg_input};
        color: {t.text_muted};
        border-color: {t.border_default};
    }}

    /* ── 主按钮 ── */
    #PrimaryBtn {{
        background-color: {t.accent};
        color: #FFFFFF;
        border: none;
        font-weight: 600;
    }}
    #PrimaryBtn:hover {{
        background-color: {t.accent_hover};
    }}
    #PrimaryBtn:pressed {{
        background-color: {t.accent_dim};
    }}
    #PrimaryBtn:disabled {{
        background-color: {t.bg_input};
        color: {t.text_muted};
    }}

    /* ── 危险/警告按钮 ── */
    #DangerBtn:hover {{
        background-color: {t.error};
        color: #FFFFFF;
        border-color: {t.error};
    }}
    #SuccessBtn {{
        background-color: {t.success};
        color: {selected_text};
        border: none;
        font-weight: 600;
    }}
    #SuccessBtn:hover {{
        filter: brightness(1.1);
    }}

    /* ── 轮廓按钮 (Outline/Accent) ── */
    #OutlineBtn {{
        background: transparent;
        color: {t.accent};
        border: 1px solid {t.accent};
        font-weight: 500;
    }}
    #OutlineBtn:hover {{
        background-color: {t.accent}18;
        border-color: {t.accent_hover};
    }}

    /* ── 输入框 ── */
    QLineEdit, QPlainTextEdit {{
        background-color: {t.bg_input};
        color: {t.text_primary};
        border: 1px solid {t.border_default};
        border-radius: 6px;
        padding: 7px 10px;
        selection-background-color: {t.accent}44;
    }}
    QLineEdit:focus, QPlainTextEdit:focus {{
        border-color: {t.accent};
    }}

    /* ── 下拉框 ── */
    QComboBox {{
        background-color: {t.bg_input};
        color: {t.text_primary};
        border: 1px solid {t.border_default};
        border-radius: 6px;
        padding: 5px 10px;
        min-width: 60px;
    }}
    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {t.bg_surface};
        color: {t.text_primary};
        border: 1px solid {t.border_default};
        border-radius: 6px;
        selection-background-color: {t.accent}33;
        outline: none;
    }}

    /* ── 进度条 ── */
    QProgressBar {{
        background-color: {t.bg_input};
        border: none;
        border-radius: 3px;
        height: 6px;
        text-align: center;
        font-size: 1px;
        color: transparent;
    }}
    QProgressBar::chunk {{
        background-color: {t.accent};
        border-radius: 3px;
    }}

    /* ── 滑块 ── */
    QSlider::groove:horizontal {{
        height: 4px;
        background: {t.border_default};
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background: {t.accent};
        width: 14px;
        height: 14px;
        margin: -5px 0;
        border-radius: 7px;
    }}
    QSlider::sub-page:horizontal {{
        background: {t.accent};
        border-radius: 2px;
    }}
    QSlider::handle:horizontal:hover {{
        background: {t.accent_hover};
    }}

    /* ── 滚动条 ── */
    QScrollArea {{
        border: none;
        background: transparent;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 6px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {t.border_default};
        border-radius: 3px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {t.text_muted};
    }}
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {{
        background: none;
        height: 0;
        width: 0;
    }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 6px;
        margin: 2px;
    }}
    QScrollBar::handle:horizontal {{
        background: {t.border_default};
        border-radius: 3px;
        min-width: 30px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {t.text_muted};
    }}
    QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal,
    QScrollBar::add-page:horizontal,
    QScrollBar::sub-page:horizontal {{
        background: none;
        width: 0;
        height: 0;
    }}

    /* ── 列表 ── */
    QListWidget {{
        background-color: {t.bg_surface};
        border: 1px solid {t.border_default};
        border-radius: 8px;
        outline: none;
        padding: 4px;
    }}
    QListWidget::item {{
        padding: 8px 10px;
        border-radius: 4px;
        border: none;
    }}
    QListWidget::item:selected {{
        background-color: {t.accent}22;
        color: {t.text_primary};
    }}
    QListWidget::item:hover:!selected {{
        background-color: {t.bg_elevated};
    }}

    /* ── 分割器 ── */
    QSplitter::handle {{
        background-color: {t.border_default};
    }}
    QSplitter::handle:hover {{
        background-color: {t.accent}44;
    }}

    /* ── 标签 ── */
    QLabel {{
        color: {t.text_primary};
        background: transparent;
    }}
    #SecondaryLabel {{
        color: {t.text_secondary};
        font-size: 12px;
    }}
    #LargeLabel {{
        font-size: 18px;
        font-weight: 700;
        color: {t.text_primary};
    }}
    #BoldLabel {{
        font-weight: bold;
        font-size: 14px;
        background: transparent;
    }}
    #EmptyLabel {{
        color: {t.text_secondary};
        font-size: 16px;
        padding: 40px;
        background: transparent;
    }}
    #PlaylistHeader {{
        font-weight: bold;
        font-size: 14px;
        background: transparent;
    }}

    /* ── 播放器控制按钮（小尺寸） ── */
    #PlayerCtrlBtn {{
        font-size: 16px;
        padding: 2px;
        background: transparent;
        border: none;
    }}
    #PlayerCtrlBtn:hover {{
        background-color: {t.bg_surface};
    }}

    /* ── 工具提示 ── */
    QToolTip {{
        background-color: {t.bg_elevated};
        color: {t.text_primary};
        border: 1px solid {t.border_default};
        border-radius: 6px;
        padding: 6px 10px;
        font-size: 12px;
    }}

    /* ── 菜单 ── */
    QMenu {{
        background-color: {t.bg_surface};
        border: 1px solid {t.border_default};
        border-radius: 8px;
        padding: 6px;
    }}
    QMenu::item {{
        padding: 6px 28px;
        border-radius: 4px;
    }}
    QMenu::item:selected {{
        background-color: {t.accent}22;
    }}
    QMenu::separator {{
        height: 1px;
        background: {t.border_default};
        margin: 4px 8px;
    }}

    /* ── 播放器控制条 ── */
    #PlayerControls {{
        background-color: {t.bg_elevated};
        border-top: 1px solid {t.border_default};
        padding: 6px 12px;
    }}

    /* ── 下载任务卡片 ── */
    #TaskCard {{
        background-color: {t.bg_surface};
        border: 1px solid {t.border_default};
        border-radius: 8px;
        padding: 14px;
    }}
    #TaskCard:hover {{
        border-color: {t.border_hover};
    }}
    #TaskCardCompleted {{
        background-color: {t.bg_surface};
        border: 2px solid {t.accent};
        border-radius: 8px;
        padding: 14px;
    }}

    /* ── 历史卡片 ── */
    #HistoryCard {{
        background-color: {t.bg_surface};
        border: 1px solid {t.border_default};
        border-radius: 8px;
        padding: 12px;
    }}
    #HistoryCard:hover {{
        border-color: {t.border_hover};
    }}

    /* ── 过滤器药丸按钮 ── */
    #FilterChip {{
        background-color: {t.bg_input};
        color: {t.text_secondary};
        border: 1px solid {t.border_default};
        border-radius: 13px;
        padding: 4px 16px;
        font-size: 12px;
        font-weight: 500;
    }}
    #FilterChip:checked {{
        background-color: {t.accent};
        color: #FFFFFF;
        border-color: {t.accent};
    }}
    #FilterChip:hover:!checked {{
        background-color: {t.bg_elevated};
        border-color: {t.border_hover};
    }}

    /* ── 状态标签 ── */
    #StatusLabel {{
        font-size: 12px;
        padding-left: 65px;
        background: transparent;
    }}
    #StatusSuccess {{
        color: {t.success};
    }}
    #StatusError {{
        color: {t.error};
    }}
    #StatusWarning {{
        color: {t.warning};
    }}
    #StatusInfo {{
        color: {t.accent};
    }}

    /* ── 播放器视频区域 ── */
    #VideoWidget {{
        background-color: #000000;
        border-radius: 6px;
    }}

    /* ── 播放器信息覆盖层（半透明毛玻璃） ── */
    #VideoInfoOverlay {{
        background: transparent;
    }}
    #VideoInfoOverlay QLabel {{
        background: transparent;
        color: #FFFFFF;
    }}
    #ShortcutOverlay {{
        background: transparent;
    }}
    #ShortcutOverlay QLabel {{
        background: transparent;
        color: #FFFFFF;
    }}
    """
