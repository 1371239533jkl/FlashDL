# FlashDL 项目记忆

## 项目概述
FlashDL — Python/PyQt6 视频下载器，支持 HTTP/磁力下载 + mpv 播放器。

## 技术约定

### UI 主题系统
- 主题切换通过 `QApplication.setStyleSheet()` + `design tokens` 实现
- **禁止**在 widget 上使用 `setStyleSheet()` 设置内联样式，应使用 `setObjectName()` + 全局 QSS 规则
- 主题切换后必须调用 `QApplication.processEvents()` + 顶层 `widget.repaint()` 强制立即重绘
- 依赖 `get_tokens()` 的绘制（如图标）需在主题切换后重建
- `QGraphicsDropShadowEffect` 会造成严重渲染延迟，避免使用

### 关键文件
- `ui/styles.py` — Design Tokens + QSS 生成
- `ui/main_window.py` — 主窗口、主题切换 `_toggle_theme()`
- `ui/player_tab.py` — 视频播放器（mpv 嵌入）
- `ui/download_tab.py` — 下载任务管理
- `ui/history_tab.py` — 历史记录（图标在创建时取色，主题切换需 refresh）
