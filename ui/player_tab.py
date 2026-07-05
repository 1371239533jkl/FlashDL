# -*- coding: utf-8 -*-
"""视频播放器标签页 - 视频显示区域、播放控制条、播放列表"""

import os
from PyQt6.QtCore import Qt, QTimer, QEvent, QPoint
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QComboBox, QFileDialog, QListWidget, QListWidgetItem,
    QSplitter, QFrame, QMenu, QWidgetAction
)
import config
from player.mpv_player import MpvPlayer
from player.playlist_manager import PlaylistManager
from utils.format_utils import format_time_ms
from utils.settings import get as get_setting, set_value as set_setting
from ui.styles import get_tokens


class PlayerTab(QWidget):
    """视频播放器标签页"""

    def __init__(self):
        super().__init__()
        self._is_seeking = False
        self._is_fullscreen = False
        self._controls_visible = True
        self._mouse_hide_timer = QTimer()
        self._mouse_hide_timer.setSingleShot(True)
        self._mouse_hide_timer.timeout.connect(self._auto_hide_controls)
        # 单击Timer（复用，避免每次点击都创建新Timer导致内存泄漏）
        self._click_timer = QTimer()
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self._toggle_play)
        self.playlist = PlaylistManager()
        self.playlist.load()
        self._setup_ui()
        self._connect_signals()
        # 恢复播放列表后在 UI 中显示
        self._refresh_playlist_ui()
        # 安装事件过滤器
        self.video_widget.installEventFilter(self)
        # 快捷键速查覆盖层
        self._shortcut_overlay = _ShortcutOverlay(self)
        # 视频信息覆盖层
        self._video_info_overlay = _VideoInfoOverlay(self)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)


        # 左侧: 视频区域 + 控制条
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        # 视频显示区域
        self.video_widget = QWidget()
        self.video_widget.setMinimumHeight(300)
        self.video_widget.setStyleSheet('background-color: #000000;')
        self.video_widget.setMouseTracking(True)
        self.video_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        left_layout.addWidget(self.video_widget, 1)

        # 全屏覆盖控制条（独立透明窗口）
        self.fullscreen_controls = _FullscreenControlsOverlay(self)

        # 播放器实例
        self.player = MpvPlayer(self.video_widget)

        # 控制条
        controls = self._create_controls()
        self._controls_frame = controls
        left_layout.addWidget(controls)

        splitter.addWidget(left_panel)

        # 右侧: 播放列表
        right_panel = self._create_playlist_panel()
        self._playlist_panel = right_panel
        self._splitter = splitter
        splitter.addWidget(right_panel)

        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([920, 240])

        layout.addWidget(splitter)

    def _create_controls(self) -> QWidget:
        """创建播放控制条（PotPlayer风格两行布局）"""
        controls = QFrame()
        controls.setObjectName('PlayerControls')
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(20, 10, 20, 14)
        controls_layout.setSpacing(10)

        # ======== 第一行：进度条 + 时间 ========
        seek_row = QHBoxLayout()
        seek_row.setSpacing(8)
        self.time_current = QLabel('00:00')
        self.time_current.setObjectName('MonoLabel')
        self.time_current.setFixedWidth(40)
        seek_row.addWidget(self.time_current)

        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 0)
        self.seek_slider.sliderPressed.connect(self._on_seek_start)
        self.seek_slider.sliderReleased.connect(self._on_seek_end)
        self.seek_slider.sliderMoved.connect(self._on_seek_moved)
        seek_row.addWidget(self.seek_slider)

        self.time_total = QLabel('00:00')
        self.time_total.setObjectName('MonoLabel')
        self.time_total.setFixedWidth(40)
        self.time_total.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        seek_row.addWidget(self.time_total)
        controls_layout.addLayout(seek_row)

        # ======== 第二行：控制按钮 + 功能按钮 ========
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)

        # 播放控制按钮（居中靠左）
        self.btn_prev = QPushButton('⏮')
        self.btn_prev.setFixedSize(38, 34)
        self.btn_prev.setObjectName('PlayerCtrlBtn')
        self.btn_prev.setToolTip('上一个')
        self.btn_prev.clicked.connect(self._play_previous)
        btn_row.addWidget(self.btn_prev)

        btn_backward = QPushButton('⏪')
        btn_backward.setFixedSize(38, 34)
        btn_backward.setObjectName('PlayerCtrlBtn')
        btn_backward.setToolTip('快退 10 秒')
        btn_backward.clicked.connect(lambda: self._skip(-10000))
        btn_row.addWidget(btn_backward)

        self.btn_play = QPushButton('▶')
        self.btn_play.setFixedSize(36, 36)
        self.btn_play.setObjectName('PlayPauseBtn')
        self.btn_play.setStyleSheet('font-size: 14px;')
        self.btn_play.clicked.connect(self._toggle_play)
        btn_row.addWidget(self.btn_play)

        btn_forward = QPushButton('⏩')
        btn_forward.setFixedSize(38, 34)
        btn_forward.setObjectName('PlayerCtrlBtn')
        btn_forward.setToolTip('快进 10 秒')
        btn_forward.clicked.connect(lambda: self._skip(10000))
        btn_row.addWidget(btn_forward)

        self.btn_next = QPushButton('⏭')
        self.btn_next.setFixedSize(38, 34)
        self.btn_next.setObjectName('PlayerCtrlBtn')
        self.btn_next.setToolTip('下一个')
        self.btn_next.clicked.connect(self._play_next)
        btn_row.addWidget(self.btn_next)

        btn_row.addStretch(1)

        # ======== 右侧功能按钮 ========
        # 音量（点击切换静音）
        self.btn_volume = QLabel('🔊')
        self.btn_volume.setObjectName('SecondaryLabel')
        self.btn_volume.setFixedWidth(28)
        self.btn_volume.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_volume.setToolTip('点击静音')
        self.btn_volume.mousePressEvent = lambda e: self._toggle_mute()
        btn_row.addWidget(self.btn_volume)
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(config.DEFAULT_VOLUME)
        self.volume_slider.setFixedWidth(80)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        btn_row.addWidget(self.volume_slider)
        self._update_volume_icon(config.DEFAULT_VOLUME)

        btn_row.addSpacing(8)

        # 倍速（显示 1.0x）
        self.speed_combo = QComboBox()
        self.speed_combo.setObjectName('SpeedBadge')
        for rate in config.PLAYBACK_RATES:
            self.speed_combo.addItem(f'{rate}x', rate)
        self.speed_combo.setCurrentText('1.0x')
        self.speed_combo.setFixedWidth(60)
        self.speed_combo.currentIndexChanged.connect(self._on_speed_changed)
        btn_row.addWidget(self.speed_combo)

        btn_row.addSpacing(4)

        # 字幕（点击弹出菜单）
        self.btn_subtitle = QPushButton('字幕')
        self.btn_subtitle.setFixedSize(40, 26)
        self.btn_subtitle.setObjectName('PlayerCtrlBtn')
        self.btn_subtitle.setToolTip('加载字幕文件')
        self.btn_subtitle.clicked.connect(self._on_subtitle_menu)
        btn_row.addWidget(self.btn_subtitle)

        # 字幕偏移状态
        self.sub_delay_label = QLabel()
        self.sub_delay_label.setObjectName('MonoLabel')
        self.sub_delay_label.setFixedWidth(36)
        self.sub_delay_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_row.addWidget(self.sub_delay_label)

        btn_row.addSpacing(6)

        # 截图按钮
        btn_screenshot = QPushButton('📷')
        btn_screenshot.setFixedSize(30, 30)
        btn_screenshot.setObjectName('PlayerCtrlBtn')
        btn_screenshot.setToolTip('截图 (S)')
        btn_screenshot.clicked.connect(self._take_screenshot)
        btn_row.addWidget(btn_screenshot)

        # 宽高比按钮
        self.btn_aspect = QPushButton('原始')
        self.btn_aspect.setFixedSize(40, 26)
        self.btn_aspect.setObjectName('PlayerCtrlBtn')
        self.btn_aspect.setToolTip('宽高比 (A)')
        self.btn_aspect.clicked.connect(self._cycle_aspect_ratio)
        btn_row.addWidget(self.btn_aspect)

        # 视频菜单按钮
        self.btn_video = QPushButton('视频')
        self.btn_video.setFixedSize(40, 26)
        self.btn_video.setObjectName('PlayerCtrlBtn')
        self.btn_video.setToolTip('视频轨道 / 画面调整')
        self.btn_video.clicked.connect(self._on_video_menu)
        btn_row.addWidget(self.btn_video)

        # 章节按钮
        self.btn_chapter = QPushButton('章节')
        self.btn_chapter.setFixedSize(40, 26)
        self.btn_chapter.setObjectName('PlayerCtrlBtn')
        self.btn_chapter.setToolTip('章节导航')
        self.btn_chapter.clicked.connect(self._on_chapter_menu)
        btn_row.addWidget(self.btn_chapter)

        # 全屏（画出来的图标按钮）
        btn_fullscreen = QPushButton()
        btn_fullscreen.setFixedSize(38, 34)
        btn_fullscreen.setToolTip('全屏')
        btn_fullscreen.setIcon(self._make_fullscreen_icon())
        btn_fullscreen.setIconSize(btn_fullscreen.size() * 0.6)
        btn_fullscreen.clicked.connect(self._toggle_fullscreen)
        btn_row.addWidget(btn_fullscreen)

        controls_layout.addLayout(btn_row)
        return controls

    def _create_playlist_panel(self) -> QWidget:
        """创建播放列表面板"""
        panel = QWidget()
        panel.setObjectName('PlaylistPanel')

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 头部
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 12, 14, 12)
        label = QLabel('播放列表')
        label.setObjectName('PlaylistHeader')
        header_layout.addWidget(label)
        header_layout.addStretch()
        layout.addWidget(header)

        self.playlist_widget = QListWidget()
        self.playlist_widget.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.playlist_widget.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.playlist_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.playlist_widget.itemDoubleClicked.connect(self._on_playlist_item_clicked)
        self.playlist_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.playlist_widget.customContextMenuRequested.connect(self._on_playlist_context_menu)
        self.playlist_widget.model().layoutChanged.connect(self._on_playlist_reordered)
        layout.addWidget(self.playlist_widget, 1)

        # 底部按钮
        btn_row = QWidget()
        btn_row_layout = QHBoxLayout(btn_row)
        btn_row_layout.setContentsMargins(12, 8, 12, 10)
        btn_row_layout.setSpacing(6)

        btn_add = QPushButton('+ 添加')
        btn_add.setObjectName('SmallBtn')
        btn_add.clicked.connect(self._add_files_to_playlist)
        btn_row_layout.addWidget(btn_add)

        btn_clear = QPushButton('清空')
        btn_clear.setObjectName('SmallBtn')
        btn_clear.clicked.connect(self._clear_playlist)
        btn_row_layout.addWidget(btn_clear)
        layout.addWidget(btn_row)

        return panel

    def _connect_signals(self):
        self.player.position_changed.connect(self._on_position_changed)
        self.player.duration_changed.connect(self._on_duration_changed)
        self.player.playback_state_changed.connect(self._on_state_changed)
        self.player.media_status_changed.connect(self._on_media_status_changed)

    # === 播放控制 ===
    def play_file(self, file_path: str):
        """播放指定文件"""
        if not os.path.exists(file_path):
            return
        # 保存当前播放进度
        self._save_playback_progress()
        # 添加到播放列表
        self.playlist.add_file(file_path)
        idx = self.playlist.items.index(file_path)
        self.playlist.set_current(idx)
        self._refresh_playlist_ui()
        self.player.load(file_path)
        self.player.play()
        # 自动检测同名字幕
        self._auto_load_subtitle(file_path)
        # 恢复播放进度
        self._restore_playback_progress(file_path)

    def _toggle_play(self):
        if self.player.current_file:
            self.player.toggle_play()
        elif self.playlist.current_file:
            self.player.load(self.playlist.current_file)
            self.player.play()

    def _skip(self, ms: int):
        pos = self.player.position + ms
        pos = max(0, min(pos, self.player.duration))
        self.player.seek(pos)

    def _play_next(self):
        self._save_playback_progress()
        path = self.playlist.next()
        if path:
            self._refresh_playlist_ui()
            self.player.load(path)
            self.player.play()
            self._auto_load_subtitle(path)
            self._restore_playback_progress(path)

    def _play_previous(self):
        self._save_playback_progress()
        path = self.playlist.previous()
        if path:
            self._refresh_playlist_ui()
            self.player.load(path)
            self.player.play()
            self._auto_load_subtitle(path)
            self._restore_playback_progress(path)

    def _on_volume_changed(self, value):
        self.player.set_volume(value)
        self._update_volume_icon(value)

    def _toggle_mute(self):
        """切换静音"""
        if self.volume_slider.value() == 0:
            last = getattr(self, '_last_volume', 70)
            self.volume_slider.setValue(last if last > 0 else 70)
        else:
            self._last_volume = self.volume_slider.value()
            self.volume_slider.setValue(0)

    def _update_volume_icon(self, value: int):
        """更新音量图标文字"""
        if value == 0:
            self.btn_volume.setText('🔇')
            self.btn_volume.setToolTip('取消静音')
        else:
            self.btn_volume.setText('🔊')
            self.btn_volume.setToolTip('点击静音')

    def _on_speed_changed(self, index):
        rate = self.speed_combo.itemData(index)
        if rate:
            self.player.set_playback_rate(rate)

    def _toggle_fullscreen(self):
        if self._is_fullscreen:
            self._exit_fullscreen()
        else:
            self._enter_fullscreen()

    def _enter_fullscreen(self):
        self._is_fullscreen = True
        self._controls_frame.hide()
        self._playlist_panel.hide()
        # 隐藏主窗口的标题栏和标签栏
        main_win = self.video_widget.window()
        if hasattr(main_win, '_title_bar'):
            main_win._title_bar.hide()
        if hasattr(main_win, 'tab_widget'):
            main_win.tab_widget.tabBar().hide()
        main_win.installEventFilter(self)
        main_win.showFullScreen()
        self.video_widget.setFocus()
        self.fullscreen_controls.attach(self.video_widget)
        # 控制条初始隐藏，鼠标移动时 _show_fullscreen_controls 才显示

    def _exit_fullscreen(self):
        self._is_fullscreen = False
        # 先隐藏全屏控制条和鼠标定时器（必须在 showNormal 之前）
        self._mouse_hide_timer.stop()
        self.fullscreen_controls.detach()
        self.video_widget.window().showNormal()
        # 移除事件过滤器
        main_win = self.video_widget.window()
        main_win.removeEventFilter(self)
        if hasattr(main_win, '_title_bar'):
            main_win._title_bar.show()
        if hasattr(main_win, 'tab_widget'):
            main_win.tab_widget.tabBar().show()
        self._controls_frame.show()
        self._playlist_panel.show()
        self.video_widget.setCursor(Qt.CursorShape.ArrowCursor)

    def _auto_hide_controls(self):
        """全屏时自动隐藏控制条和鼠标"""
        if self._is_fullscreen and self.player.is_playing:
            self.fullscreen_controls.hide()
            self.video_widget.setCursor(Qt.CursorShape.BlankCursor)

    def _show_fullscreen_controls(self):
        """显示全屏控制条并重置自动隐藏计时器"""
        self.video_widget.setCursor(Qt.CursorShape.ArrowCursor)
        self.fullscreen_controls.show()
        self._mouse_hide_timer.start(3000)

    def _on_video_double_click(self, event):
        self._toggle_fullscreen()

    def eventFilter(self, obj, event):
        """拦截全屏状态下的键盘和鼠标事件"""
        main_win = self.video_widget.window()

        # 主窗口事件（全屏时拦截）
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
            return super().eventFilter(obj, event)

        # video_widget 事件
        if obj is not self.video_widget:
            return super().eventFilter(obj, event)

        etype = event.type()

        # 键盘事件
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
                return True

        # 鼠标双击 → 切换全屏（必须在单击之前处理）
        if etype == QEvent.Type.MouseButtonDblClick:
            self._click_timer.stop()
            self._on_video_double_click(event)
            return True

        # 单击暂停/播放（延迟执行，等待是否双击）
        if etype == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            # 复用_init中创建的_click_timer，只需重启即可
            self._click_timer.start(300)
            return True

        # 鼠标移动 → 全屏时显示控制条
        if etype == QEvent.Type.MouseMove and self._is_fullscreen:
            self._show_fullscreen_controls()
            return False

        return super().eventFilter(obj, event)

    # === 进度条 ===
    def _on_seek_start(self):
        self._is_seeking = True

    def _on_seek_end(self):
        self._is_seeking = False
        self.player.seek(self.seek_slider.value())
        self._save_playback_progress()

    def _on_seek_moved(self, value):
        self.time_current.setText(format_time_ms(value))

    def _on_position_changed(self, position):
        if not self._is_seeking:
            self.seek_slider.setValue(position)
            self.time_current.setText(format_time_ms(position))

    def _on_duration_changed(self, duration):
        self.seek_slider.setRange(0, duration)
        self.time_total.setText(format_time_ms(duration))

    def _on_state_changed(self, state):
        if state == MpvPlayer.PLAYING:
            self.btn_play.setText('⏸')
        elif state == MpvPlayer.PAUSED:
            self.btn_play.setText('▶')
            # 暂停时保存进度
            self._save_playback_progress()
        else:  # StoppedState
            self.btn_play.setText('▶')

    def _on_media_status_changed(self, status):
        if status == MpvPlayer.END_OF_MEDIA:
            # 自动播放下一个
            if self.playlist.has_next():
                self._play_next()
        elif status == MpvPlayer.LOADED:
            # 视频加载完毕，延迟100ms后恢复播放进度（给Qt时间处理完内部状态）
            path = self.player.current_file
            if path:
                QTimer.singleShot(100, lambda p=path: self._restore_playback_progress(p))

    # === 播放列表UI ===
    def _add_files_to_playlist(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, '选择视频文件', '',
            '视频文件 (*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.m4v);;所有文件 (*)'
        )
        if files:
            self.playlist.add_files(files)
            self._refresh_playlist_ui()

    def _clear_playlist(self):
        self.playlist.clear()
        self.playlist_widget.clear()
        self.player.stop()

    def _on_playlist_item_clicked(self, item: QListWidgetItem):
        row = self.playlist_widget.row(item)
        path = self.playlist.set_current(row)
        if path:
            self._refresh_playlist_ui()
            self.player.load(path)
            self.player.play()
            self._auto_load_subtitle(path)

    def _on_playlist_context_menu(self, pos):
        """播放列表右键菜单"""
        item = self.playlist_widget.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        remove_action = menu.addAction('删除')
        clear_action = menu.addAction('清空列表')
        action = menu.exec(self.playlist_widget.mapToGlobal(pos))
        if action == remove_action:
            row = self.playlist_widget.row(item)
            self.playlist.remove_file(row)
            self._refresh_playlist_ui()
            if row == self.playlist.current_index:
                self.player.stop()
        elif action == clear_action:
            self._clear_playlist()

    def _on_playlist_reordered(self):
        """拖拽排序后同步 PlaylistManager 的内部列表"""
        new_items = []
        for i in range(self.playlist_widget.count()):
            path = self.playlist_widget.item(i).data(Qt.ItemDataRole.UserRole)
            if path:
                new_items.append(path)

        if len(new_items) != len(self.playlist._items):
            return  # 数据不完整，跳过

        current_path = self.playlist.current_file
        self.playlist._items.clear()
        self.playlist._items.extend(new_items)
        if current_path in new_items:
            self.playlist._current_index = new_items.index(current_path)

    def _refresh_playlist_ui(self):
        self.playlist.save()
        self.playlist_widget.clear()
        for i, path in enumerate(self.playlist.items):
            name = os.path.basename(path)
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, path)
            if i == self.playlist.current_index:
                item.setText(f'▶ {name}')
            self.playlist_widget.addItem(item)

    @staticmethod
    def _make_fullscreen_icon() -> 'QIcon':
        """绘制全屏图标（一个矩形四角带小勾，不受字体影响）"""
        from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor
        size = 20
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor('#CCCCCC'), 2)
        p.setPen(pen)
        # 画四角短线（模拟全屏图标）
        m = 3  # margin
        s = 5  # short line length
        # 左上角
        p.drawLine(m, m, m + s, m)
        p.drawLine(m, m, m, m + s)
        # 右上角
        p.drawLine(size - m - s, m, size - m, m)
        p.drawLine(size - m, m, size - m, m + s)
        # 左下角
        p.drawLine(m, size - m - s, m, size - m)
        p.drawLine(m, size - m, m + s, size - m)
        # 右下角
        p.drawLine(size - m - s, size - m, size - m, size - m)
        p.drawLine(size - m, size - m - s, size - m, size - m)
        p.end()
        from PyQt6.QtGui import QIcon
        return QIcon(pix)

    def cleanup(self):
        self._save_playback_progress()
        self.fullscreen_controls.detach()
        self.player.cleanup()

    # === 播放进度记忆 ===

    def _save_playback_progress(self):
        """保存当前视频的播放进度"""
        path = self.player.current_file
        if not path or self.player.duration <= 0:
            return
        # 归一化路径（统一路径分隔符）
        path = os.path.normpath(path)
        progress_data = get_setting('playback_progress', {})
        pos = self.player.position
        # 只保存有意义的进度（超过10秒且不是末尾）
        if pos > 10000 and pos < self.player.duration - 5000:
            progress_data[path] = pos
        elif path in progress_data:
            # 视频已播完或接近末尾，清除进度记录
            del progress_data[path]
        set_setting('playback_progress', progress_data)

    def _restore_playback_progress(self, file_path: str):
        """恢复视频播放进度"""
        progress_data = get_setting('playback_progress', {})
        saved_pos = progress_data.get(os.path.normpath(file_path), 0)
        if saved_pos > 0:
            self.player.seek(saved_pos)

    # === 字幕（mpv 原生 libass 渲染）===

    def _on_subtitle_menu(self):
        """字幕按钮菜单（内嵌字幕轨 + 外挂字幕 + 音轨 + 延迟）"""
        menu = QMenu(self)
        menu.setStyleSheet('font-size: 12px; padding: 4px;')

        has_any = False

        # ── 内嵌字幕轨道 ──
        sub_tracks = self.player.get_subtitle_tracks()
        if sub_tracks:
            has_any = True
            menu.addAction('内嵌字幕').setEnabled(False)
            for t in sub_tracks:
                label = f'字幕 {t["id"]}'
                if t.get('lang'):
                    label += f' [{t["lang"]}]'
                if t.get('title'):
                    label += f' {t["title"]}'
                if t.get('selected'):
                    label = f'✓ {label}'
                menu.addAction(label, lambda tid=t['id']: self.player.set_subtitle_track(tid))

        # ── 同目录外挂字幕 ──
        external_subs = self._scan_external_subtitles()
        if external_subs:
            if has_any:
                menu.addSeparator()
            has_any = True
            menu.addAction('外挂字幕').setEnabled(False)
            for name, path in external_subs:
                menu.addAction(name, lambda p=path: self._load_subtitle(p))

        if has_any:
            menu.addSeparator()

        # ── 手动添加字幕 ──
        menu.addAction('添加字幕文件...', self._open_subtitle_dialog)

        # ── 音轨切换 ──
        tracks = self.player.get_audio_tracks()
        if tracks:
            menu.addSeparator()
            menu.addAction('切换音轨').setEnabled(False)
            for t in tracks:
                label = f'音轨 {t["id"]}'
                if t.get('lang'):
                    label += f' [{t["lang"]}]'
                if t.get('title'):
                    label += f' {t["title"]}'
                menu.addAction(label, lambda tid=t['id']: self.player.set_audio_track(tid))

        # ── 字幕延迟 ──
        delay_ms = self.player.get_subtitle_delay()
        menu.addSeparator()
        if delay_ms != 0:
            off_text = f'字幕延迟: {delay_ms/1000:+.1f}s'
        else:
            off_text = '字幕延迟: 已同步'
        menu.addAction(off_text).setEnabled(False)
        menu.addAction('提前 0.5s', lambda: self._adjust_subtitle_offset(-500))
        menu.addAction('延后 0.5s', lambda: self._adjust_subtitle_offset(500))
        if delay_ms != 0:
            menu.addAction('重置同步', lambda: self._adjust_subtitle_offset(-delay_ms))

        btn_pos = self.btn_subtitle.mapToGlobal(self.btn_subtitle.rect().bottomLeft())
        menu.exec(btn_pos - QPoint(0, menu.sizeHint().height() + self.btn_subtitle.height()))

    def _scan_external_subtitles(self) -> list:
        """扫描同目录下所有外挂字幕文件，返回 [(显示名, 路径)]"""
        video_path = self.player.current_file
        if not video_path:
            return []
        video_dir = os.path.dirname(video_path)
        video_name = os.path.splitext(os.path.basename(video_path))[0]
        results = []
        try:
            for fname in sorted(os.listdir(video_dir)):
                ext = os.path.splitext(fname)[1].lower()
                if ext not in config.SUBTITLE_EXTENSIONS:
                    continue
                full_path = os.path.join(video_dir, fname)
                if not os.path.isfile(full_path):
                    continue
                # 优先显示与视频同名的，其次显示其他
                base = os.path.splitext(fname)[0]
                if base == video_name or base.startswith(video_name):
                    results.append((f'★ {fname}', full_path))
                else:
                    results.append((fname, full_path))
        except Exception:
            pass
        return results

    def _on_video_menu(self):
        """视频菜单（视频轨道 + 亮度/对比度/饱和度/伽马）"""
        menu = QMenu(self)
        menu.setStyleSheet('font-size: 12px; padding: 4px;')

        # ── 视频轨道 ──
        v_tracks = self.player.get_video_tracks()
        if v_tracks:
            menu.addAction('视频轨道').setEnabled(False)
            for t in v_tracks:
                label = f'视频 {t["id"]}'
                if t.get('lang'):
                    label += f' [{t["lang"]}]'
                if t.get('title'):
                    label += f' {t["title"]}'
                if t.get('w') and t.get('h'):
                    label += f' ({t["w"]}x{t["h"]})'
                menu.addAction(label, lambda tid=t['id']: self.player.set_video_track(tid))
            menu.addSeparator()

        # ── 画面调整 ──
        menu.addAction('画面调整').setEnabled(False)

        # 亮度
        eq_menu = self._make_slider_action(
            menu, '亮度', self.player.brightness,
            lambda v: setattr(self.player, 'brightness', v))
        # 对比度
        self._make_slider_action(
            menu, '对比度', self.player.contrast,
            lambda v: setattr(self.player, 'contrast', v))
        # 饱和度
        self._make_slider_action(
            menu, '饱和度', self.player.saturation,
            lambda v: setattr(self.player, 'saturation', v))
        # 伽马
        self._make_slider_action(
            menu, '伽马', self.player.gamma,
            lambda v: setattr(self.player, 'gamma', v))

        menu.addSeparator()
        menu.addAction('重置全部', self.player.reset_video_params)

        btn_pos = self.btn_video.mapToGlobal(self.btn_video.rect().bottomLeft())
        menu.exec(btn_pos - QPoint(0, menu.sizeHint().height() + self.btn_video.height()))

    def _make_slider_action(self, menu: QMenu, name: str, current: int,
                            on_change) -> None:
        """在菜单中嵌入滑块控件"""
        action = QAction(name, menu)
        action.setEnabled(False)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(-100, 100)
        slider.setValue(current)
        slider.setFixedWidth(160)
        slider.setToolTip(f'{name}: {current:+d}')

        def _on_value(v):
            slider.setToolTip(f'{name}: {v:+d}')
            on_change(v)
        slider.valueChanged.connect(_on_value)

        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(16, 2, 8, 2)
        layout.setSpacing(8)
        lbl = QLabel(f'{name}')
        lbl.setFixedWidth(46)
        lbl.setObjectName('SecondaryLabel')
        layout.addWidget(lbl)

        val_label = QLabel(f'{current:+d}')
        val_label.setFixedWidth(36)
        val_label.setObjectName('SecondaryLabel')
        slider.valueChanged.connect(lambda v, ll=val_label, nm=name:
                                    ll.setText(f'{v:+d}'))
        layout.addWidget(slider)
        layout.addWidget(val_label)

        widget_action = QWidgetAction(menu)
        widget_action.setDefaultWidget(widget)
        menu.addAction(widget_action)

    def _on_chapter_menu(self):
        """章节导航菜单"""
        menu = QMenu(self)
        menu.setStyleSheet('font-size: 12px; padding: 4px;')

        chapters = self.player.get_chapters()
        current_idx = self.player.chapter

        if not chapters:
            menu.addAction('无章节信息').setEnabled(False)
        else:
            from utils.format_utils import format_time_ms
            for ch in chapters:
                label = f'{format_time_ms(ch["time_ms"])}  {ch["title"]}'
                if ch['index'] == current_idx:
                    label = f'▶ {label}'
                menu.addAction(label, lambda idx=ch['index']:
                               self.player.seek_to_chapter(idx))

        btn_pos = self.btn_chapter.mapToGlobal(self.btn_chapter.rect().bottomLeft())
        menu.exec(btn_pos - QPoint(0, menu.sizeHint().height() + self.btn_chapter.height()))

    def _open_subtitle_dialog(self):
        """手动选择字幕文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, '选择字幕文件', '',
            '字幕文件 (*.srt *.ass *.ssa *.vtt);;所有文件 (*)'
        )
        if file_path:
            self._load_subtitle(file_path)

    def _load_subtitle(self, subtitle_path: str):
        """加载字幕文件"""
        self.player.add_subtitle(subtitle_path)
        self.btn_subtitle.setText('字幕')
        self.btn_subtitle.setToolTip(f'已加载: {os.path.basename(subtitle_path)}')

    def _auto_detect_subtitle(self, video_path: str) -> str | None:
        """自动检测同目录下的同名字幕文件"""
        if not video_path:
            return None
        base = os.path.splitext(video_path)[0]
        suffixes = ['', '.zh', '.chs', '.chi', '.cn', '.sc']
        for suffix in suffixes:
            for ext in config.SUBTITLE_EXTENSIONS:
                candidate = f'{base}{suffix}{ext}'
                if os.path.isfile(candidate):
                    return candidate
        return None

    def _auto_load_subtitle(self, video_path: str):
        """自动检测并加载同名字幕"""
        self.btn_subtitle.setText('字幕')
        self.btn_subtitle.setToolTip('加载字幕文件')
        self._restore_subtitle_offset(video_path)

        if not config.SUBTITLE_AUTO_LOAD:
            return
        subtitle_path = self._auto_detect_subtitle(video_path)
        if subtitle_path:
            self._load_subtitle(subtitle_path)

    def _update_subtitle(self, position_ms: int):
        """字幕由 mpv 原生 libass 渲染，无需手动更新"""
        pass

    # === 字幕延迟调节 ===

    def _adjust_subtitle_offset(self, delta_ms: int):
        """调整字幕时间偏移量"""
        new_delay = self.player.get_subtitle_delay() + delta_ms
        self.player.set_subtitle_delay(new_delay)
        self._update_subtitle_delay_label()
        self._save_subtitle_offset()

    # === 截图 ===

    def _take_screenshot(self):
        """截取当前视频帧"""
        if not self.player.current_file:
            return
        import time as _time
        video_path = self.player.current_file
        video_dir = os.path.dirname(video_path)
        video_name = os.path.splitext(os.path.basename(video_path))[0]
        # 时间码格式：HH-MM-SS
        pos_ms = self.player.position
        h = pos_ms // 3600000
        m = (pos_ms % 3600000) // 60000
        s = (pos_ms % 60000) // 1000
        time_tag = f'{h:02d}-{m:02d}-{s:02d}'
        screenshot_dir = os.path.join(video_dir, 'screenshots')
        os.makedirs(screenshot_dir, exist_ok=True)
        save_path = os.path.join(screenshot_dir, f'{video_name}_{time_tag}.png')
        if self.player.take_screenshot(save_path):
            from utils.signal_bus import signal_bus
            signal_bus.show_notification.emit('截图已保存', os.path.basename(save_path))

    # === 宽高比 ===

    def _cycle_aspect_ratio(self):
        """循环切换宽高比"""
        label = self.player.cycle_aspect_ratio()
        self.btn_aspect.setText(label)
        from utils.signal_bus import signal_bus
        signal_bus.show_notification.emit('宽高比', label)

    # === 视频信息 ===

    def _show_video_info(self):
        """切换视频信息覆盖层"""
        ov = self._video_info_overlay
        if ov.isVisible():
            ov._close()
        else:
            ov.show_overlay()

    def _toggle_shortcut_overlay(self):
        """切换快捷键覆盖层"""
        ov = self._shortcut_overlay
        if ov.isVisible():
            ov._close()
        else:
            ov.show_overlay()

    def _update_subtitle_delay_label(self):
        """更新字幕延迟标签显示"""
        delay_ms = self.player.get_subtitle_delay()
        if delay_ms == 0:
            self.sub_delay_label.setText('同步')
        elif delay_ms > 0:
            self.sub_delay_label.setText(f'+{delay_ms/1000:.1f}s')
        else:
            self.sub_delay_label.setText(f'{delay_ms/1000:.1f}s')

    def _save_subtitle_offset(self):
        """保存当前视频的字幕偏移量"""
        path = self.player.current_file
        if not path:
            return
        path = os.path.normpath(path)
        offset_data = get_setting('subtitle_offsets', {})
        delay_ms = self.player.get_subtitle_delay()
        if delay_ms == 0:
            offset_data.pop(path, None)
        else:
            offset_data[path] = delay_ms
        set_setting('subtitle_offsets', offset_data)

    def _restore_subtitle_offset(self, file_path: str):
        """恢复视频的字幕偏移量"""
        offset_data = get_setting('subtitle_offsets', {})
        saved_delay = offset_data.get(os.path.normpath(file_path), 0)
        self.player.set_subtitle_delay(saved_delay)
        self._update_subtitle_delay_label()


class _FullscreenControlsOverlay(QWidget):
    """
    全屏时的控制条覆盖窗口。
    独立的无边框半透明 Tool 窗口，悬浮在全屏视频底部。
    mpv 直接渲染到 native window，Qt 子控件会被遮挡，
    因此必须使用独立窗口而非 video_widget 子控件。
    """

    def __init__(self, player_tab: 'PlayerTab'):
        super().__init__(None)
        self._player_tab = player_tab
        self._attached = False
        self._is_seeking = False

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._build_ui()
        self.hide()

        # 同步播放器进度
        self._sync_timer = QTimer(self)
        self._sync_timer.setInterval(200)
        self._sync_timer.timeout.connect(self._sync_from_player)

        self.hide()

    def _build_ui(self):
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
        main_layout.setSpacing(4)

        # 进度条行
        seek_row = QHBoxLayout()
        self._time_current = QLabel('00:00')
        self._time_current.setFixedWidth(50)
        seek_row.addWidget(self._time_current)

        self._seek_slider = QSlider(Qt.Orientation.Horizontal)
        self._seek_slider.setRange(0, 0)
        self._seek_slider.sliderPressed.connect(self._on_seek_start)
        self._seek_slider.sliderReleased.connect(self._on_seek_end)
        self._seek_slider.sliderMoved.connect(self._on_seek_moved)
        seek_row.addWidget(self._seek_slider)

        self._time_total = QLabel('00:00')
        self._time_total.setFixedWidth(50)
        self._time_total.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        seek_row.addWidget(self._time_total)
        main_layout.addLayout(seek_row)

        # 按钮行
        btn_row = QHBoxLayout()

        fs_style = 'font-size: 16px; font-family: "Segoe UI Symbol", "Microsoft YaHei UI", sans-serif;'
        
        btn_prev = QPushButton('⏮')
        btn_prev.setFixedSize(42, 32)
        btn_prev.setStyleSheet(fs_style)
        btn_prev.clicked.connect(self._player_tab._play_previous)
        btn_row.addWidget(btn_prev)

        btn_bw = QPushButton('⏪')
        btn_bw.setFixedSize(42, 32)
        btn_bw.setStyleSheet(fs_style)
        btn_bw.clicked.connect(lambda: self._player_tab._skip(-10000))
        btn_row.addWidget(btn_bw)

        self._btn_play = QPushButton('▶')
        self._btn_play.setFixedSize(48, 34)
        self._btn_play.setStyleSheet(fs_style)
        self._btn_play.clicked.connect(self._player_tab._toggle_play)
        btn_row.addWidget(self._btn_play)

        btn_fw = QPushButton('⏩')
        btn_fw.setFixedSize(42, 32)
        btn_fw.setStyleSheet(fs_style)
        btn_fw.clicked.connect(lambda: self._player_tab._skip(10000))
        btn_row.addWidget(btn_fw)

        btn_next = QPushButton('⏭')
        btn_next.setFixedSize(42, 32)
        btn_next.setStyleSheet(fs_style)
        btn_next.clicked.connect(self._player_tab._play_next)
        btn_row.addWidget(btn_next)

        btn_row.addSpacing(30)

        vol_label = QLabel('音量')
        btn_row.addWidget(vol_label)
        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setFixedWidth(100)
        self._volume_slider.valueChanged.connect(self._on_volume_changed)
        btn_row.addWidget(self._volume_slider)

        btn_row.addSpacing(8)

        speed_label = QLabel('倍速')
        btn_row.addWidget(speed_label)
        self._speed_combo = QComboBox()
        self._speed_combo.addItems([f'{r}x' for r in config.PLAYBACK_RATES])
        self._speed_combo.setCurrentText('1.0x')
        self._speed_combo.setFixedWidth(60)
        self._speed_combo.currentIndexChanged.connect(self._on_speed_changed)
        btn_row.addWidget(self._speed_combo)

        btn_row.addSpacing(8)

        self._btn_sub = QPushButton('字幕')
        self._btn_sub.setFixedWidth(50)
        self._btn_sub.clicked.connect(self._player_tab._on_subtitle_menu)
        btn_row.addWidget(self._btn_sub)

        btn_row.addStretch()

        btn_exit = QPushButton()
        btn_exit.setFixedSize(36, 28)
        btn_exit.setToolTip('退出全屏')
        btn_exit.setIcon(PlayerTab._make_fullscreen_icon())
        btn_exit.setIconSize(btn_exit.size() * 0.6)
        btn_exit.clicked.connect(self._player_tab._exit_fullscreen)
        btn_row.addWidget(btn_exit)

        main_layout.addLayout(btn_row)

    def attach(self, video_widget):
        """绑定到全屏的视频控件（初始隐藏，鼠标移动时显示）"""
        self._attached = True
        # 同步当前状态
        pt = self._player_tab
        self._seek_slider.setRange(0, pt.player.duration)
        self._seek_slider.setValue(pt.player.position)
        self._time_total.setText(format_time_ms(pt.player.duration))
        self._time_current.setText(format_time_ms(pt.player.position))
        self._volume_slider.setValue(pt.volume_slider.value())
        self._speed_combo.setCurrentIndex(pt.speed_combo.currentIndex())
        self._btn_play.setText('⏸' if pt.player.is_playing else '▶')
        # 定位到屏幕底部中央
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.geometry()
            self.setFixedWidth(geom.width())
            self.move(0, geom.height() - self.height())
        # 初始隐藏，鼠标移动时 _show_fullscreen_controls 会显示
        self._sync_timer.start()

    def detach(self):
        """解除绑定并隐藏"""
        self._attached = False
        self._sync_timer.stop()
        self.hide()

    def _sync_from_player(self):
        """从播放器同步进度"""
        if not self._attached or self._is_seeking:
            return
        pt = self._player_tab
        self._seek_slider.setRange(0, pt.player.duration)
        self._seek_slider.setValue(pt.player.position)
        self._time_current.setText(format_time_ms(pt.player.position))
        self._time_total.setText(format_time_ms(pt.player.duration))
        self._btn_play.setText('⏸' if pt.player.is_playing else '▶')
        # 同步音量滑块（快捷键/非全屏滑块变化时保持同步）
        vol = pt.volume_slider.value()
        if self._volume_slider.value() != vol:
            self._volume_slider.blockSignals(True)
            self._volume_slider.setValue(vol)
            self._volume_slider.blockSignals(False)

    def _on_seek_start(self):
        self._is_seeking = True

    def _on_seek_end(self):
        self._is_seeking = False
        self._player_tab.player.seek(self._seek_slider.value())

    def _on_seek_moved(self, value):
        self._time_current.setText(format_time_ms(value))

    def _on_volume_changed(self, value):
        self._player_tab.volume_slider.setValue(value)
        self._player_tab.player.set_volume(value)

    def _on_speed_changed(self, index):
        text = self._speed_combo.itemText(index)
        if text:
            try:
                rate = float(text.replace('x', ''))
                self._player_tab.player.set_playback_rate(rate)
                self._player_tab.speed_combo.setCurrentIndex(index)
            except ValueError:
                pass


class _VideoInfoOverlay(QWidget):
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
                         min(300, vr.width()), vr.height())

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        title = QLabel('视频信息')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet('color: #FFFFFF; font-size: 18px; font-weight: 700; background: transparent;')
        layout.addWidget(title)

        self._info_lines = QVBoxLayout()
        self._info_lines.setSpacing(8)
        layout.addLayout(self._info_lines)

        layout.addStretch()
        hint = QLabel('按任意键关闭')
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet('color: rgba(255,255,255,140); font-size: 12px; background: transparent;')
        layout.addWidget(hint)

    def _label_style(self) -> str:
        return 'color: rgba(255,255,255,200); font-size: 13px; background: transparent;'

    def _format_info_line(self, label: str, value) -> str:
        if value:
            return f'{label}: {value}'
        return f'{label}: --'

    def show_overlay(self):
        self._sync_position()
        self.show()
        self.setFocus()
        self._sync_timer.start()
        self._last_snapshot = None
        self._info_timer.start()
        self._refresh_info()

    def _refresh_info(self):
        info = self._player_tab.player.get_video_info()
        file_path = self._player_tab.player.current_file or ''
        # 用位置和当前文件做快照，无变化时跳过重建避免闪烁
        position = self._player_tab.player.position
        snapshot = (file_path, position,
                    info.get('resolution', ''), info.get('codec', ''),
                    info.get('fps', ''), info.get('bitrate', ''))
        if snapshot == getattr(self, '_last_snapshot', None):
            return
        self._last_snapshot = snapshot

        while self._info_lines.count():
            item = self._info_lines.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if file_path:
            import os
            label = QLabel(f'文件: {os.path.basename(file_path)}')
            label.setStyleSheet(self._label_style())
            self._info_lines.addWidget(label)

        for label, key in [('分辨率', 'resolution'), ('编码', 'codec'),
                           ('FPS', 'fps'), ('码率', 'bitrate')]:
            val = info.get(key, '')
            text = self._format_info_line(label, val)
            lbl = QLabel(text)
            lbl.setStyleSheet(self._label_style())
            self._info_lines.addWidget(lbl)

        tracks = self._player_tab.player.get_audio_tracks()
        if tracks:
            lbl = QLabel(f'音轨数: {len(tracks)}')
            lbl.setStyleSheet(self._label_style())
            self._info_lines.addWidget(lbl)

    def _close(self):
        self._sync_timer.stop()
        self._info_timer.stop()
        self.hide()
        self._player_tab.video_widget.setFocus()

    def keyPressEvent(self, event):
        self._close()

    def mousePressEvent(self, event):
        self._close()


class _ShortcutOverlay(QWidget):
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

    def _build_ui(self):
        from PyQt6.QtGui import QFont
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel('键盘快捷键')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet('color: #FFFFFF; font-size: 18px; font-weight: 700; background: transparent;')
        layout.addWidget(title)

        section_style = 'color: #FFFFFF; font-size: 14px; font-weight: bold; background: transparent;'
        key_style = 'color: rgba(255,255,255,180); font-size: 12px; background: transparent;'
        desc_style = 'color: rgba(255,255,255,220); font-size: 13px; background: transparent;'

        for section_name, items in self.SHORTCUTS:
            section = QLabel(section_name)
            section.setStyleSheet(section_style)
            layout.addWidget(section)
            for key, desc in items:
                row = QHBoxLayout()
                key_label = QLabel(f'  {key}')
                key_label.setFixedWidth(90)
                key_label.setStyleSheet(key_style)
                key_label.setFont(QFont('Consolas', 11))
                row.addWidget(key_label)
                desc_label = QLabel(desc)
                desc_label.setStyleSheet(desc_style)
                row.addWidget(desc_label)
                row.addStretch()
                layout.addLayout(row)

        hint = QLabel('按任意键关闭')
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet('color: rgba(255,255,255,100); font-size: 12px; background: transparent;')
        layout.addWidget(hint)

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
