# -*- coding: utf-8 -*-
"""FlashDL 设计系统 — 暗黑专业媒体风 Design Tokens + 双主题 QSS 生成"""

from dataclasses import dataclass
from utils.settings import get as get_setting, set_value as set_setting
import config

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
    bg_primary: str       # 根背景
    bg_surface: str        # 卡片/面板背景
    bg_elevated: str       # 标题栏/工具栏
    bg_input: str          # 输入框背景
    bg_hover: str          # 悬停态
    # 边框
    border_subtle: str     # 极淡边框（分隔线）
    border_default: str    # 默认边框
    border_hover: str      # 悬停边框
    # 文字
    text_primary: str      # 主文字
    text_secondary: str    # 次要文字
    text_muted: str        # 弱化文字
    # 强调色 (琥珀/媒体专业橙)
    accent: str
    accent_hover: str
    accent_dim: str        # 暗色变体
    accent_glow: str       # rgba 外发光
    # 语义色
    success: str
    error: str
    warning: str


# 深色主题 Token — 暗黑专业媒体风
DARK = DesignTokens(
    bg_primary='#0D0D0D',
    bg_surface='#141414',
    bg_elevated='#1A1A1A',
    bg_input='#1E1E1E',
    bg_hover='#222222',
    border_subtle='#1C1C1C',
    border_default='#2A2A2A',
    border_hover='#3A3A3A',
    text_primary='#E4E4E4',
    text_secondary='#8A8A8A',
    text_muted='#555555',
    accent='#D4783B',
    accent_hover='#E08A4E',
    accent_dim='#B8662E',
    accent_glow='rgba(212, 120, 59, 0.15)',
    success='#4CAF50',
    error='#E05555',
    warning='#E0A040',
)

# 浅色主题 Token
LIGHT = DesignTokens(
    bg_primary='#F5F5F5',
    bg_surface='#FFFFFF',
    bg_elevated='#EEEEEE',
    bg_input='#FFFFFF',
    bg_hover='#E8E8E8',
    border_subtle='#E5E5E5',
    border_default='#D5D5D5',
    border_hover='#BBBBBB',
    text_primary='#1A1A1A',
    text_secondary='#666666',
    text_muted='#999999',
    accent='#C4682B',
    accent_hover='#D4783B',
    accent_dim='#A8551E',
    accent_glow='rgba(196, 104, 43, 0.12)',
    success='#43A047',
    error='#D33F3F',
    warning='#D49020',
)


def get_tokens(theme: str = None) -> DesignTokens:
    """获取当前主题的设计 Token"""
    if theme is None:
        theme = _current_theme
    return DARK if theme == 'dark' else LIGHT


_stylesheet_cache: dict = {}

def get_stylesheet(theme: str = None) -> str:
    """返回全局 QSS 样式表（带缓存避免主题切换时重复构建）"""
    if theme is None:
        theme = _current_theme
    if theme not in _stylesheet_cache:
        _stylesheet_cache[theme] = _build_stylesheet(theme)
    return _stylesheet_cache[theme]


def _build_stylesheet(theme: str) -> str:
    t = get_tokens(theme)
    is_dark = theme == 'dark'

    # 主按钮文字色：琥珀色背景上用近黑色
    accent_text = '#1A0F05' if is_dark else '#FFFFFF'

    return f"""
    /* ═══ FlashDL 设计系统 — 暗黑专业媒体风 {"深色" if is_dark else "浅色"}主题 ═══ */

    * {{
        font-family: "Segoe UI Symbol", "Microsoft YaHei", "Segoe UI", sans-serif;
        font-size: 13px;
        color: {t.text_primary};
    }}

    QWidget {{
        background-color: {t.bg_primary};
    }}

    /* ── 侧边栏 ── */
    #Sidebar {{
        background-color: {t.bg_primary};
        border-right: 1px solid {t.border_subtle};
        min-width: {config.SIDEBAR_WIDTH}px;
        max-width: {config.SIDEBAR_WIDTH}px;
    }}
    #SidebarIcon {{
        background: transparent;
        border: none;
        border-radius: 6px;
        color: {t.text_muted};
        font-size: 16px;
        min-width: 36px;
        min-height: 36px;
        max-width: 36px;
        max-height: 36px;
        padding: 0px;
    }}
    #SidebarIcon:hover {{
        background-color: {t.bg_hover};
        color: {t.text_secondary};
    }}
    #SidebarIcon[active="true"] {{
        background-color: {t.accent_dim};
        color: {t.accent};
    }}

    /* ── 标题栏 (无边框窗口) ── */
    #TitleBar {{
        background-color: {t.bg_primary};
        border-bottom: 1px solid {t.border_subtle};
    }}
    #TitleLabel {{
        color: {t.text_primary};
        font-size: 14px;
        font-weight: 600;
        padding-left: 20px;
        background: transparent;
        letter-spacing: 0.3px;
    }}
    #TitleVersion {{
        color: {t.text_muted};
        font-size: 11px;
        background: transparent;
        margin-left: 4px;
    }}
    #TitleBtn {{
        background: transparent;
        border: none;
        color: {t.text_muted};
        font-size: 14px;
        min-width: 28px;
        min-height: 28px;
        max-width: 28px;
        max-height: 28px;
        border-radius: 4px;
        padding: 0px;
    }}
    #TitleBtn:hover {{
        background-color: {t.bg_hover};
        color: {t.text_secondary};
    }}
    #CloseBtn {{
        background: transparent;
        border: none;
        color: {t.text_muted};
        font-size: 13px;
        min-width: 28px;
        min-height: 28px;
        max-height: 28px;
        border-radius: 4px;
        padding: 0px;
    }}
    #CloseBtn:hover {{
        background-color: {t.error}33;
        color: {t.error};
    }}

    /* ── 标签栏 ── */
    #TabBar {{
        background-color: {t.bg_primary};
        border-bottom: 1px solid {t.border_subtle};
        padding: 0 20px;
    }}
    #TabBtn {{
        background: transparent;
        border: none;
        border-bottom: 2px solid transparent;
        border-radius: 0px;
        color: {t.text_muted};
        font-size: 12px;
        font-weight: 500;
        padding: 8px 16px;
        min-height: {config.TAB_BAR_HEIGHT}px;
        letter-spacing: 0.2px;
    }}
    #TabBtn:hover {{
        color: {t.text_secondary};
        background: transparent;
    }}
    #TabBtn[active="true"] {{
        color: {t.text_primary};
        border-bottom-color: {t.accent};
    }}
    #TabBadge {{
        background-color: {t.accent_dim};
        color: {t.accent};
        font-size: 10px;
        font-weight: 600;
        border-radius: 10px;
        padding: 1px 6px;
    }}

    QTabWidget::pane {{
        border: none;
        background-color: {t.bg_primary};
    }}
    QTabBar {{
        background-color: {t.bg_primary};
        border-bottom: 1px solid {t.border_subtle};
    }}
    QTabBar::tab {{
        background-color: transparent;
        color: {t.text_muted};
        padding: 9px 20px;
        border: none;
        border-bottom: 2px solid transparent;
        font-size: 12px;
        font-weight: 500;
        margin-right: 0px;
        letter-spacing: 0.2px;
    }}
    QTabBar::tab:selected {{
        color: {t.text_primary};
        border-bottom: 2px solid {t.accent};
    }}
    QTabBar::tab:hover:!selected {{
        color: {t.text_secondary};
    }}

    /* ── 按钮基础 ── */
    QPushButton {{
        background-color: {t.bg_elevated};
        color: {t.text_primary};
        border: 1px solid {t.border_default};
        border-radius: 6px;
        padding: 6px 14px;
        min-height: 28px;
        font-weight: 500;
    }}
    QPushButton:hover {{
        background-color: {t.bg_hover};
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

    /* ── 主按钮 (Primary / Accent) ── */
    #PrimaryBtn {{
        background-color: {t.accent};
        color: {accent_text};
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

    /* ── 幽灵按钮 (Ghost) ── */
    #GhostBtn {{
        background: transparent;
        color: {t.text_secondary};
        border: 1px solid {t.border_default};
        font-weight: 400;
    }}
    #GhostBtn:hover {{
        background: {t.bg_hover};
        color: {t.text_primary};
        border-color: {t.border_hover};
    }}

    /* ── 危险按钮 ── */
    #DangerBtn {{
        background: transparent;
        color: {t.text_secondary};
        border: 1px solid transparent;
    }}
    #DangerBtn:hover {{
        background-color: rgba(224, 85, 85, 0.15);
        color: {t.error};
        border-color: {t.error}44;
    }}

    /* ── 小尺寸按钮 ── */
    #SmallBtn {{
        padding: 4px 10px;
        min-height: 24px;
        font-size: 11px;
        border-radius: 4px;
    }}

    /* ── 成功按钮 ── */
    #SuccessBtn {{
        background-color: {t.success};
        color: {accent_text};
        border: none;
        font-weight: 600;
    }}
    #SuccessBtn:hover {{
        filter: brightness(1.1);
    }}

    /* ── 轮廓按钮 ── */
    #OutlineBtn {{
        background: transparent;
        color: {t.accent};
        border: 1px solid {t.accent};
        font-weight: 500;
    }}
    #OutlineBtn:hover {{
        background-color: rgba(212, 120, 59, 0.10);
        border-color: {t.accent_hover};
    }}

    /* ── 输入框 ── */
    QLineEdit, QPlainTextEdit, QSpinBox {{
        background-color: {t.bg_input};
        color: {t.text_primary};
        border: 1px solid {t.border_default};
        border-radius: 6px;
        padding: 5px 10px;
        selection-background-color: {t.accent}66;
    }}
    QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus {{
        border-color: {t.accent};
    }}
    QSpinBox::up-button, QSpinBox::down-button {{
        subcontrol-origin: border;
        width: 18px;
        border: none;
        background: transparent;
    }}
    QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
        background: {t.bg_elevated};
    }}
    QSpinBox::up-arrow {{
        image: none;
        width: 8px; height: 8px;
    }}
    QSpinBox::down-arrow {{
        image: none;
        width: 8px; height: 8px;
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
    QComboBox:hover {{
        border-color: {t.border_hover};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 22px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {t.bg_elevated};
        color: {t.text_primary};
        border: 1px solid {t.border_default};
        border-radius: 6px;
        selection-background-color: {t.accent}66;
        outline: none;
        padding: 4px;
    }}
    QComboBox QAbstractItemView::item {{
        padding: 3px 8px;
        border-radius: 4px;
        min-height: 18px;
    }}
    QComboBox QAbstractItemView::item:selected {{
        background-color: {t.accent}66;
    }}

    /* ── 进度条 ── */
    QProgressBar {{
        background-color: {t.bg_input};
        border: none;
        border-radius: 2px;
        height: 4px;
        text-align: center;
        font-size: 1px;
        color: transparent;
    }}
    QProgressBar::chunk {{
        background-color: {t.accent};
        border-radius: 2px;
    }}

    /* ── 滑块 ── */
    QSlider::groove:horizontal {{
        height: 3px;
        background: {t.border_default};
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background: {t.accent};
        width: 12px;
        height: 12px;
        margin: -5px 0;
        border-radius: 6px;
    }}
    QSlider::sub-page:horizontal {{
        background: {t.accent};
        border-radius: 2px;
    }}
    QSlider::handle:horizontal:hover {{
        background: {t.accent_hover};
        width: 14px;
        height: 14px;
        margin: -6px 0;
        border-radius: 7px;
    }}

    /* ── 滚动条 ── */
    QScrollArea {{
        border: none;
        background: transparent;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 5px;
        margin: 2px 0;
    }}
    QScrollBar::handle:vertical {{
        background: {t.border_hover};
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
        height: 5px;
        margin: 0 2px;
    }}
    QScrollBar::handle:horizontal {{
        background: {t.border_hover};
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
        background-color: transparent;
        border: none;
        border-radius: 6px;
        outline: none;
        padding: 4px;
    }}
    QListWidget::item {{
        padding: 6px 10px;
        border-radius: 4px;
        border: none;
        min-height: 20px;
    }}
    QListWidget::item:selected {{
        background-color: {t.accent}66;
        color: {t.accent};
    }}
    QListWidget::item:hover:!selected {{
        background-color: {t.bg_hover};
    }}

    /* ── 分割器 ── */
    QSplitter::handle {{
        background-color: {t.border_subtle};
        width: 1px;
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
        font-weight: 600;
        font-size: 13px;
        background: transparent;
    }}
    #EmptyLabel {{
        color: {t.text_muted};
        font-size: 14px;
        padding: 40px;
        background: transparent;
    }}
    #PlaylistHeader {{
        font-weight: 600;
        font-size: 12px;
        color: {t.text_secondary};
        letter-spacing: 0.5px;
        text-transform: uppercase;
        background: transparent;
        padding: 8px 12px;
    }}
    #PlaylistPanel {{
        background-color: {t.bg_primary};
        border-left: 1px solid {t.border_subtle};
    }}

    /* ── 播放器控制按钮（小尺寸） ── */
    #PlayerCtrlBtn {{
        font-size: 15px;
        padding: 2px;
        background: transparent;
        border: none;
        border-radius: 4px;
        color: {t.text_secondary};
        min-width: 30px;
        min-height: 30px;
    }}
    #PlayerCtrlBtn:hover {{
        background-color: {t.bg_hover};
        color: {t.text_primary};
    }}
    #PlayPauseBtn {{
        font-size: 16px;
        background: {t.bg_hover};
        border-radius: 6px;
        min-width: 34px;
        min-height: 34px;
        color: {t.text_primary};
    }}
    #PlayPauseBtn:hover {{
        background-color: {t.bg_input};
    }}

    /* ── 工具提示 ── */
    QToolTip {{
        background-color: {t.bg_elevated};
        color: {t.text_primary};
        border: 1px solid {t.border_hover};
        border-radius: 6px;
        padding: 5px 9px;
        font-size: 11px;
    }}

    /* ── 右键菜单 ── */
    QMenu {{
        background-color: {t.bg_elevated};
        border: 1px solid {t.border_default};
        border-radius: 8px;
        padding: 6px;
    }}
    QMenu::item {{
        padding: 4px 24px 4px 10px;
        border-radius: 4px;
        min-height: 20px;
    }}
    QMenu::item:selected {{
        background-color: {t.accent}66;
    }}
    QMenu::separator {{
        height: 1px;
        background: {t.border_default};
        margin: 4px 8px;
    }}

    /* ── 播放器控制条 ── */
    #PlayerControls {{
        background-color: {t.bg_primary};
        border-top: 1px solid {t.border_subtle};
        padding: 14px 20px;
    }}

    /* ── 下载页面 - URL 输入区域 ── */
    #UrlInputArea {{
        background: transparent;
    }}
    #UrlInputArea QPushButton {{
        min-height: 20px;
        max-height: 24px;
        padding: 2px 10px;
    }}
    #UrlInputLabel {{
        color: {t.text_muted};
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        background: transparent;
    }}

    /* ── 下载工具栏 ── */
    #DownloadToolbar {{
        background-color: {t.bg_elevated};
        border: 1px solid {t.border_subtle};
        border-radius: 6px;
        padding: 8px 12px;
    }}
    #ToolbarLabel {{
        color: {t.text_muted};
        font-size: 11px;
        font-weight: 500;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        background: transparent;
    }}
    #ToolbarPath {{
        color: {t.text_secondary};
        font-size: 11px;
        background: transparent;
    }}
    #ToolbarDivider {{
        background-color: {t.border_default};
        min-width: 1px;
        max-width: 1px;
        min-height: 16px;
        max-height: 16px;
    }}

    /* ── 下载状态栏 ── */
    #DownloadStatusBar {{
        background-color: {t.bg_elevated};
        border: 1px solid {t.border_subtle};
        border-radius: 6px;
        padding: 8px 14px;
    }}
    #StatusDot {{
        background-color: {t.accent};
        border-radius: 3px;
        min-width: 6px;
        max-width: 6px;
        min-height: 6px;
        max-height: 6px;
    }}
    #StatusDot[idle="true"] {{
        background-color: {t.text_muted};
    }}

    /* ── 列表空状态 ── */
    #EmptyStateIcon {{
        font-size: 42px;
        color: {t.text_muted};
        background: transparent;
        margin-bottom: 4px;
    }}
    #EmptyStateText {{
        font-size: 15px;
        font-weight: 600;
        color: {t.text_secondary};
        background: transparent;
    }}
    

    /* ── 倍速标签 ── */
    #SpeedBadge {{
        color: {t.accent};
        background-color: {t.accent_dim};
        font-size: 10px;
        font-weight: 500;
        border-radius: 4px;
        padding: 2px 6px;
    }}

    /* ── 下载任务卡片 ── */
    #TaskCard {{
        background-color: {t.bg_elevated};
        border: 1px solid {t.border_subtle};
        border-radius: 6px;
        padding: 14px 16px;
    }}
    #TaskCard:hover {{
        border-color: {t.border_default};
    }}
    #TaskCardCompleted {{
        background-color: {t.bg_elevated};
        border: 1px solid {t.border_subtle};
        border-radius: 6px;
        padding: 14px 16px;
    }}
    #TaskCardCompleted:hover {{
        border-color: {t.border_default};
    }}
    #TaskName {{
        font-size: 13px;
        font-weight: 600;
        color: {t.text_primary};
        background: transparent;
    }}
    #TaskSize {{
        font-size: 11px;
        color: {t.text_muted};
        background: transparent;
    }}
    #StatLabel {{
        font-size: 10px;
        color: {t.text_muted};
        letter-spacing: 0.5px;
        text-transform: uppercase;
        background: transparent;
    }}
    #StatValue {{
        font-size: 12px;
        color: {t.text_secondary};
        background: transparent;
    }}

    /* ── 历史条目 ── */
    #HistoryCard {{
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 6px;
        padding: 10px 14px;
    }}
    #HistoryCard:hover {{
        background-color: {t.bg_elevated};
        border-color: {t.border_subtle};
    }}

    /* ── 过滤器药丸按钮 ── */
    #FilterChip {{
        background-color: transparent;
        color: {t.text_muted};
        border: 1px solid {t.border_default};
        border-radius: 14px;
        padding: 5px 12px;
        font-size: 11px;
        font-weight: 500;
    }}
    #FilterChip:checked {{
        background-color: {t.accent_dim};
        color: {t.accent};
        border-color: {t.accent_dim};
    }}
    #FilterChip:hover:!checked {{
        color: {t.text_secondary};
        border-color: {t.border_hover};
    }}

    /* ── 历史操作按钮（透明、无边框） ── */
    #HistoryActionBtn {{
        background: transparent;
        border: none;
        color: {t.text_muted};
        min-width: 28px;
        min-height: 28px;
        max-width: 28px;
        max-height: 28px;
        border-radius: 4px;
        padding: 0px;
    }}
    #HistoryActionBtn:hover {{
        background-color: {t.bg_hover};
        color: {t.text_secondary};
    }}

    /* ── 历史状态圆点 ── */
    #HistoryStatusSuccess {{
        background-color: {t.success}22;
        color: {t.success};
        border-radius: 10px;
        font-size: 10px;
        min-width: 20px;
        min-height: 20px;
        max-width: 20px;
        max-height: 20px;
    }}
    #HistoryStatusError {{
        background-color: {t.error}22;
        color: {t.error};
        border-radius: 10px;
        font-size: 10px;
        min-width: 20px;
        min-height: 20px;
        max-width: 20px;
        max-height: 20px;
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

    /* ── 空状态 ── */
    #EmptyState {{
        color: {t.text_muted};
        font-size: 13px;
        background: transparent;
    }}
    #EmptyStateHint {{
        color: {t.text_muted};
        font-size: 11px;
        background: transparent;
    }}

    /* ── 播放器视频区域 ── */
    #VideoWidget {{
        background-color: #000000;
        border-radius: 6px;
    }}

    /* ── 播放器占位 ── */
    #PlayerPlaceholder {{
        color: {t.text_muted};
        font-size: 12px;
        background: transparent;
    }}

    /* ── 播放器信息覆盖层 ── */
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

    /* ── 单行数值标签（等宽字体，用于速度/大小/百分比） ── */
    #MonoLabel {{
        font-family: "Cascadia Code", "Consolas", "JetBrains Mono", monospace;
        font-size: 12px;
        color: {t.text_secondary};
        background: transparent;
    }}
    #MonoAccent {{
        font-family: "Cascadia Code", "Consolas", "JetBrains Mono", monospace;
        font-size: 12px;
        color: {t.accent};
        background: transparent;
    }}

    /* ── 分隔线 ── */
    #Divider {{
        background-color: {t.border_subtle};
        min-height: 1px;
        max-height: 1px;
    }}
    """
