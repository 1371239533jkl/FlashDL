# -*- coding: utf-8 -*-
"""
极简多线程视频下载播放器 - 应用入口

功能:
  - 多线程高速下载(HTTP Range分片)
  - 断点续传
  - 本地视频播放
  - 极简黑白风界面
  - 系统托盘

启动方式:
  python main.py
"""

import sys
import os

# 确保当前目录在路径中(支持从任意位置启动)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    # 高DPI支持
    os.environ['QT_ENABLE_HIGHDPI_SCALING'] = '1'

    # 重要：libtorrent session 必须在 PyQt6 导入之前初始化
    # 否则 PyQt6 和 libtorrent 的原生库会冲突导致段错误 (Windows)
    from core.magnet_session_manager import MagnetSessionManager, is_libtorrent_available
    if is_libtorrent_available():
        try:
            MagnetSessionManager.get_instance().initialize()
        except Exception as e:
            print(f'[警告] libtorrent 会话初始化失败: {e}')

    # 延迟导入 PyQt6（必须在 libtorrent 初始化之后）
    from PyQt6.QtWidgets import QApplication
    import config
    from core.download_manager import DownloadManager
    from ui.main_window import MainWindow
    from ui.styles import get_stylesheet

    app = QApplication(sys.argv)
    app.setApplicationName(config.APP_NAME)
    app.setQuitOnLastWindowClosed(False)  # 关闭窗口不退出(支持托盘)

    # 应用全局样式
    app.setStyleSheet(get_stylesheet())

    # 初始化下载管理器
    download_manager = DownloadManager()

    # 创建主窗口
    window = MainWindow(download_manager)

    # 加载未完成的下载任务
    download_manager.load_unfinished_tasks()

    # 异常退出时（任务管理器杀进程/系统关机）保存任务状态
    def _emergency_save():
        download_manager.save_all_tasks()
        from core.magnet_session_manager import MagnetSessionManager, is_libtorrent_available
        if is_libtorrent_available():
            try:
                MagnetSessionManager.get_instance().shutdown()
            except Exception:
                pass
    app.aboutToQuit.connect(_emergency_save)

    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
