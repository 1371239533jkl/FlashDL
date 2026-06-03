# -*- coding: utf-8 -*-
"""视频播放器标签页 — mpv 引擎 + 内嵌全屏控制"""

import os
from PyQt6.QtCore import Qt, QTimer, QEvent, QPoint
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QComboBox, QFileDialog, QListWidget, QListWidgetItem,
    QSplitter, QFrame, QMenu
)
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QIcon

import config
from player.mpv_player import MpvPlayer
from player.playlist_manager import PlaylistManager
from utils.format_utils import format_time_ms
from utils.settings import get as get_setting, set_value as set_setting


class PlayerTab(QWidget):
    """视频播放器标签页"""

    def __init__(self):
        super().__init__()
        self._is_seeking = False
        self._is_fullscreen = False
        self._mouse_hide_timer = QTimer()
        self._mouse_hide_timer.setSingleShot(True)
        self._mouse_hide_timer.timeout.connect(self._auto_hide_controls)
        self._click_timer = QTimer()
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self._toggle_play)
        self.playlist = PlaylistManager()
        self.playlist.load()
        self._setup_ui()
        self._connect_signals()
        self._refresh_playlist_ui()
        self.video_container.installEventFilter(self)
        # 延迟连接全屏控制信号（等 player 创建好）
        QTimer.singleShot(0, self._wire_fs_controls)

    # ════════════════════════════════════════
    #  UI 构建
    # ════════════════════════════════════════

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧: 视频区域 + 控制条
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        # 视频容器（mpv 渲染到此 HWND）
        self.video_container = QFrame()
        self.video_container.setMinimumHeight(300)
        self.video_container.setStyleSheet('background-color: #000000;')
        self.video_container.setMouseTracking(True)
        self.video_container.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)
        left_layout.addWidget(self.video_container, 1)

        # 播放器实例
        self.player = MpvPlayer(self.video_container)

        # 主控制条
        left_layout.addWidget(self._create_controls())
        splitter.addWidget(left_panel)

        # 右侧播放列表
        splitter.addWidget(self._create_playlist_panel())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([750, 250])
        layout.addWidget(splitter)

        # 全屏控制条（内嵌在 video_container 里，默认隐藏）
        self._fs_overlay = self._create_fs_overlay()

    def _create_controls(self) -> QWidget:
        ctrl = QFrame()
        ctrl.setObjectName('PlayerControls')
        vl = QVBoxLayout(ctrl)
        vl.setContentsMargins(12, 6, 12, 8)
        vl.setSpacing(6)

        # 进度条行
        sr = QHBoxLayout()
        self.time_current = QLabel('00:00')
        self.time_current.setObjectName('SecondaryLabel')
        self.time_current.setFixedWidth(50)
        sr.addWidget(self.time_current)

        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 0)
        self.seek_slider.sliderPressed.connect(self._on_seek_start)
        self.seek_slider.sliderReleased.connect(self._on_seek_end)
        self.seek_slider.sliderMoved.connect(self._on_seek_moved)
        sr.addWidget(self.seek_slider)

        self.time_total = QLabel('00:00')
        self.time_total.setObjectName('SecondaryLabel')
        self.time_total.setFixedWidth(50)
        self.time_total.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        sr.addWidget(self.time_total)
        vl.addLayout(sr)

        # 按钮行
        br = QHBoxLayout()
        br.setSpacing(4)
        cs = 'font-size: 16px; padding: 2px;'

        self.btn_prev = QPushButton('⏮')
        self.btn_prev.setFixedSize(38, 34); self.btn_prev.setStyleSheet(cs)
        self.btn_prev.setToolTip('上一个'); self.btn_prev.clicked.connect(self._play_previous)
        br.addWidget(self.btn_prev)

        bw = QPushButton('⏪')
        bw.setFixedSize(38, 34); bw.setStyleSheet(cs)
        bw.setToolTip('快退 10 秒'); bw.clicked.connect(lambda: self._skip(-10000))
        br.addWidget(bw)

        self.btn_play = QPushButton('▶')
        self.btn_play.setFixedSize(46, 38); self.btn_play.setStyleSheet(cs)
        self.btn_play.setObjectName('PrimaryBtn'); self.btn_play.clicked.connect(self._toggle_play)
        br.addWidget(self.btn_play)

        fw = QPushButton('⏩')
        fw.setFixedSize(38, 34); fw.setStyleSheet(cs)
        fw.setToolTip('快进 10 秒'); fw.clicked.connect(lambda: self._skip(10000))
        br.addWidget(fw)

        self.btn_next = QPushButton('⏭')
        self.btn_next.setFixedSize(38, 34); self.btn_next.setStyleSheet(cs)
        self.btn_next.setToolTip('下一个'); self.btn_next.clicked.connect(self._play_next)
        br.addWidget(self.btn_next)

        br.addStretch(1)

        # 音量
        self.btn_volume = QLabel('🔊')
        self.btn_volume.setObjectName('SecondaryLabel')
        self.btn_volume.setFixedWidth(28)
        self.btn_volume.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_volume.setToolTip('点击静音')
        self.btn_volume.mousePressEvent = lambda e: self._toggle_mute()
        br.addWidget(self.btn_volume)
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(config.DEFAULT_VOLUME)
        self.volume_slider.setFixedWidth(80)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        br.addWidget(self.volume_slider)
        self._update_volume_icon(config.DEFAULT_VOLUME)

        br.addSpacing(8)

        # 倍速
        self.speed_combo = QComboBox()
        for rate in config.PLAYBACK_RATES:
            self.speed_combo.addItem(f'{rate}x', rate)
        self.speed_combo.setCurrentText('1.0x')
        self.speed_combo.setFixedWidth(66)
        self.speed_combo.currentIndexChanged.connect(self._on_speed_changed)
        br.addWidget(self.speed_combo)
        br.addSpacing(4)

        # 字幕
        self.btn_subtitle = QPushButton('字幕')
        self.btn_subtitle.setFixedWidth(56)
        self.btn_subtitle.setToolTip('加载字幕文件')
        self.btn_subtitle.clicked.connect(self._on_subtitle_menu)
        br.addWidget(self.btn_subtitle)
        self.sub_delay_label = QLabel()
        self.sub_delay_label.setObjectName('SecondaryLabel')
        self.sub_delay_label.setFixedWidth(42)
        self.sub_delay_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        br.addWidget(self.sub_delay_label)
        br.addSpacing(4)

        # 全屏按钮
        fs_btn = QPushButton()
        fs_btn.setFixedSize(38, 34)
        fs_btn.setToolTip('全屏')
        fs_btn.setIcon(self._make_fullscreen_icon())
        fs_btn.setIconSize(fs_btn.size() * 0.6)
        fs_btn.clicked.connect(self._toggle_fullscreen)
        br.addWidget(fs_btn)

        vl.addLayout(br)
        return ctrl

    def _create_playlist_panel(self) -> QWidget:
        panel = QWidget()
        lo = QVBoxLayout(panel)
        lo.setContentsMargins(8, 8, 8, 8)
        lo.setSpacing(6)
        hdr = QHBoxLayout()
        hdr.addWidget(QLabel('播放列表'))
        hdr.addStretch()
        lo.addLayout(hdr)
        self.playlist_widget = QListWidget()
        self.playlist_widget.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.playlist_widget.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.playlist_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.playlist_widget.itemDoubleClicked.connect(self._on_playlist_item_clicked)
        self.playlist_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.playlist_widget.customContextMenuRequested.connect(self._on_playlist_context_menu)
        self.playlist_widget.model().layoutChanged.connect(self._on_playlist_reordered)
        lo.addWidget(self.playlist_widget)
        br = QHBoxLayout()
        add = QPushButton('添加文件'); add.clicked.connect(self._add_files_to_playlist)
        br.addWidget(add)
        clr = QPushButton('清空列表'); clr.clicked.connect(self._clear_playlist)
        br.addWidget(clr)
        lo.addLayout(br)
        return panel

    # ════════════════════════════════════════
    #  内嵌全屏控制条
    # ════════════════════════════════════════

    def _create_fs_overlay(self) -> QFrame:
        """全屏时显示在 video_container 底部的半透明控制条"""
        frame = QFrame(self.video_container)
        frame.setObjectName('FSOverlay')
        frame.setFixedHeight(80)
        frame.setStyleSheet("""
            #FSOverlay {
                background-color: rgba(0, 0, 0, 210);
                border-radius: 0px;
            }
            QLabel { color: #FFFFFF; font-size: 12px; }
            QPushButton {
                color: #FFFFFF; background: transparent;
                border: 1px solid rgba(255,255,255,80);
                border-radius: 4px; font-size: 14px; padding: 2px 8px;
            }
            QPushButton:hover { background: rgba(255,255,255,40); }
            QSlider::groove:horizontal {
                height: 6px; background: rgba(255,255,255,60); border-radius: 3px;
            }
            QSlider::handle:horizontal {
                width: 14px; height: 14px; margin: -4px 0;
                background: #FFFFFF; border-radius: 7px;
            }
            QSlider::sub-page:horizontal { background: #4FC3F7; border-radius: 3px; }
        """)
        vl = QVBoxLayout(frame)
        vl.setContentsMargins(16, 8, 16, 8)
        vl.setSpacing(6)

        # 进度行
        sr = QHBoxLayout()
        self._f_time_cur = QLabel('00:00'); self._f_time_cur.setFixedWidth(50)
        sr.addWidget(self._f_time_cur)
        self._f_seek = QSlider(Qt.Orientation.Horizontal)
        self._f_seek.setRange(0, 0)
        self._f_seek.sliderPressed.connect(lambda: setattr(self, '_is_seeking', True))
        self._f_seek.sliderReleased.connect(self._fs_seek_end)
        self._f_seek.sliderMoved.connect(lambda v: self._f_time_cur.setText(format_time_ms(v)))
        sr.addWidget(self._f_seek)
        self._f_time_tot = QLabel('00:00'); self._f_time_tot.setFixedWidth(50)
        self._f_time_tot.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        sr.addWidget(self._f_time_tot)
        vl.addLayout(sr)

        # 按钮行
        br = QHBoxLayout()
        fs = 'font-size: 16px; font-family: "Segoe UI Symbol", "Microsoft YaHei UI", sans-serif;'
        btn_prev = QPushButton('⏮'); btn_prev.setFixedSize(42, 32)
        btn_prev.setStyleSheet(fs); btn_prev.clicked.connect(self._play_previous)
        br.addWidget(btn_prev)
        btn_bw = QPushButton('⏪'); btn_bw.setFixedSize(42, 32)
        btn_bw.setStyleSheet(fs); btn_bw.clicked.connect(lambda: self._skip(-10000))
        br.addWidget(btn_bw)
        self._f_btn_play = QPushButton('▶'); self._f_btn_play.setFixedSize(48, 34)
        self._f_btn_play.setStyleSheet(fs); self._f_btn_play.clicked.connect(self._toggle_play)
        br.addWidget(self._f_btn_play)
        btn_fw = QPushButton('⏩'); btn_fw.setFixedSize(42, 32)
        btn_fw.setStyleSheet(fs); btn_fw.clicked.connect(lambda: self._skip(10000))
        br.addWidget(btn_fw)
        btn_next = QPushButton('⏭'); btn_next.setFixedSize(42, 32)
        btn_next.setStyleSheet(fs); btn_next.clicked.connect(self._play_next)
        br.addWidget(btn_next)
        br.addSpacing(30)
        br.addWidget(QLabel('音量'))
        self._f_vol = QSlider(Qt.Orientation.Horizontal)
        self._f_vol.setRange(0, 100); self._f_vol.setFixedWidth(100)
        self._f_vol.valueChanged.connect(lambda v: self._on_volume_changed(v))
        br.addWidget(self._f_vol)
        br.addStretch()
        exit_btn = QPushButton()
        exit_btn.setFixedSize(36, 28); exit_btn.setToolTip('退出全屏')
        exit_btn.setIcon(self._make_fullscreen_icon())
        exit_btn.setIconSize(exit_btn.size() * 0.6)
        exit_btn.clicked.connect(self._exit_fullscreen)
        br.addWidget(exit_btn)
        vl.addLayout(br)

        frame.hide()
        return frame

    def _wire_fs_controls(self):
        """连接全屏定时器刷新（延迟到 player 创建后）"""
        self._fs_sync = QTimer(self)
        self._fs_sync.setInterval(200)
        self._fs_sync.timeout.connect(self._fs_refresh)
        self._fs_hide_timer = QTimer(self)
        self._fs_hide_timer.setSingleShot(True)
        self._fs_hide_timer.timeout.connect(self._fs_auto_hide)

    def _fs_refresh(self):
        """全屏时同步进度和状态"""
        if not self._is_fullscreen or self._is_seeking:
            return
        self._f_seek.setRange(0, self.player.duration)
        self._f_seek.setValue(self.player.position)
        self._f_time_cur.setText(format_time_ms(self.player.position))
        self._f_time_tot.setText(format_time_ms(self.player.duration))
        self._f_btn_play.setText('⏸' if self.player.is_playing else '▶')
        self._f_vol.setValue(self.volume_slider.value())

    def _fs_seek_end(self):
        self._is_seeking = False
        self.player.seek(self._f_seek.value())

    def _fs_auto_hide(self):
        if self._is_fullscreen and self.player.is_playing:
            self._fs_overlay.hide()
            self.video_container.setCursor(Qt.CursorShape.BlankCursor)

    # ════════════════════════════════════════
    #  信号
    # ════════════════════════════════════════

    def _connect_signals(self):
        self.player.position_changed.connect(self._on_position_changed)
        self.player.duration_changed.connect(self._on_duration_changed)
        self.player.playback_state_changed.connect(self._on_state_changed)
        self.player.media_status_changed.connect(self._on_media_status_changed)

    # ════════════════════════════════════════
    #  播放控制
    # ════════════════════════════════════════

    def play_file(self, path: str):
        if not os.path.exists(path):
            return
        self._save_playback_progress()
        self.playlist.add_file(path)
        idx = self.playlist.items.index(path)
        self.playlist.set_current(idx)
        self._refresh_playlist_ui()
        self.player.load(path)
        self.player.play()
        self._restore_playback_progress(path)
        self._restore_subtitle_offset(path)

    def _toggle_play(self):
        if self.player.current_file:
            self.player.toggle_play()
        elif self.playlist.current_file:
            self.player.load(self.playlist.current_file)
            self.player.play()

    def _skip(self, ms):
        pos = self.player.position + ms
        self.player.seek(max(0, min(pos, self.player.duration)))

    def _play_next(self):
        self._save_playback_progress()
        p = self.playlist.next()
        if p:
            self._refresh_playlist_ui()
            self.player.load(p); self.player.play()
            self._restore_playback_progress(p)

    def _play_previous(self):
        self._save_playback_progress()
        p = self.playlist.previous()
        if p:
            self._refresh_playlist_ui()
            self.player.load(p); self.player.play()
            self._restore_playback_progress(p)

    def _on_volume_changed(self, v):
        self.player.set_volume(v)
        self.volume_slider.blockSignals(True)
        self.volume_slider.setValue(v)
        self.volume_slider.blockSignals(False)
        self._update_volume_icon(v)

    def _toggle_mute(self):
        if self.volume_slider.value() == 0:
            lv = getattr(self, '_last_volume', 70)
            self.volume_slider.setValue(lv if lv > 0 else 70)
        else:
            self._last_volume = self.volume_slider.value()
            self.volume_slider.setValue(0)

    def _update_volume_icon(self, v):
        self.btn_volume.setText('🔇' if v == 0 else '🔊')
        self.btn_volume.setToolTip('取消静音' if v == 0 else '点击静音')

    def _on_speed_changed(self, idx):
        r = self.speed_combo.itemData(idx)
        if r:
            self.player.set_playback_rate(r)

    # ════════════════════════════════════════
    #  全屏
    # ════════════════════════════════════════

    def _toggle_fullscreen(self):
        if self._is_fullscreen:
            self._exit_fullscreen()
        else:
            self._enter_fullscreen()

    def _enter_fullscreen(self):
        self._is_fullscreen = True
        top = self.window()
        self._fs_was_max = top.isMaximized()
        top.showFullScreen()
        # 显示内嵌控制条
        self._fs_show()
        self._fs_sync.start()

    def _exit_fullscreen(self):
        self._is_fullscreen = False
        top = self.window()
        if self._fs_was_max:
            top.showMaximized()
        else:
            top.showNormal()
        self._fs_overlay.hide()
        self._fs_sync.stop()
        self.video_container.setCursor(Qt.CursorShape.ArrowCursor)

    def _auto_hide_controls(self):
        if self._is_fullscreen and self.player.is_playing:
            self._fs_overlay.hide()
            self.video_container.setCursor(Qt.CursorShape.BlankCursor)

    def _fs_show(self):
        """全屏控制条定位到 video_container 底部并显示"""
        self._fs_overlay.setFixedWidth(self.video_container.width())
        self._fs_overlay.move(0, self.video_container.height() - 80)
        self._fs_overlay.raise_()
        self._fs_overlay.show()
        self.video_container.setCursor(Qt.CursorShape.ArrowCursor)
        # 3 秒后自动隐藏
        self._fs_hide_timer.start(3000)

    # ════════════════════════════════════════
    #  事件过滤
    # ════════════════════════════════════════

    def _on_video_double_click(self, event):
        self._toggle_fullscreen()

    def eventFilter(self, obj, event):
        if obj is not self.video_container:
            return super().eventFilter(obj, event)

        etype = event.type()

        if etype == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Escape and self._is_fullscreen:
                self._exit_fullscreen(); return True
            if key == Qt.Key.Key_Space:
                self._toggle_play(); return True
            if key == Qt.Key.Key_Left:
                self._skip(-10000)
                if self._is_fullscreen: self._fs_show()
                return True
            if key == Qt.Key.Key_Right:
                self._skip(10000)
                if self._is_fullscreen: self._fs_show()
                return True
            if key == Qt.Key.Key_Up:
                self._on_volume_changed(min(100, self.volume_slider.value() + 5))
                if self._is_fullscreen: self._fs_show()
                return True
            if key == Qt.Key.Key_Down:
                self._on_volume_changed(max(0, self.volume_slider.value() - 5))
                if self._is_fullscreen: self._fs_show()
                return True
            if key in (Qt.Key.Key_F, Qt.Key.Key_F11):
                self._toggle_fullscreen(); return True

        if etype == QEvent.Type.MouseButtonDblClick:
            self._click_timer.stop()
            self._on_video_double_click(event)
            return True

        if etype == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self._click_timer.start(300)
            return True

        if etype == QEvent.Type.MouseMove and self._is_fullscreen:
            self._fs_show()

        return super().eventFilter(obj, event)

    # ════════════════════════════════════════
    #  进度 / 状态回调
    # ════════════════════════════════════════

    def _on_seek_start(self):
        self._is_seeking = True

    def _on_seek_end(self):
        self._is_seeking = False
        self.player.seek(self.seek_slider.value())
        self._save_playback_progress()

    def _on_seek_moved(self, v):
        self.time_current.setText(format_time_ms(v))

    def _on_position_changed(self, pos):
        if not self._is_seeking:
            self.seek_slider.setValue(pos)
            self.time_current.setText(format_time_ms(pos))

    def _on_duration_changed(self, dur):
        self.seek_slider.setRange(0, dur)
        self.time_total.setText(format_time_ms(dur))

    def _on_state_changed(self, state):
        if state == MpvPlayer.PLAYING:
            self.btn_play.setText('⏸')
        elif state == MpvPlayer.PAUSED:
            self.btn_play.setText('▶')
            self._save_playback_progress()
        else:
            self.btn_play.setText('▶')

    def _on_media_status_changed(self, status):
        if status == MpvPlayer.END_OF_MEDIA:
            if self.playlist.has_next():
                self._play_next()
        elif status == MpvPlayer.LOADED:
            path = self.player.current_file
            if path:
                QTimer.singleShot(100, lambda p=path: self._restore_playback_progress(p))

    # ════════════════════════════════════════
    #  播放列表
    # ════════════════════════════════════════

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

    def _on_playlist_item_clicked(self, item):
        row = self.playlist_widget.row(item)
        path = self.playlist.set_current(row)
        if path:
            self._refresh_playlist_ui()
            self.player.load(path); self.player.play()

    def _on_playlist_context_menu(self, pos):
        item = self.playlist_widget.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        rm = menu.addAction('删除')
        clr = menu.addAction('清空列表')
        action = menu.exec(self.playlist_widget.mapToGlobal(pos))
        if action == rm:
            row = self.playlist_widget.row(item)
            self.playlist.remove_file(row)
            self._refresh_playlist_ui()
            if row == self.playlist.current_index:
                self.player.stop()
        elif action == clr:
            self._clear_playlist()

    def _on_playlist_reordered(self):
        new_items = []
        for i in range(self.playlist_widget.count()):
            path = self.playlist_widget.item(i).data(Qt.ItemDataRole.UserRole)
            if path:
                new_items.append(path)
        if len(new_items) != len(self.playlist._items):
            return
        cur = self.playlist.current_file
        self.playlist._items.clear()
        self.playlist._items.extend(new_items)
        if cur in new_items:
            self.playlist._current_index = new_items.index(cur)

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
    def _make_fullscreen_icon() -> QIcon:
        size = 20
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor('#CCCCCC'), 2)
        p.setPen(pen)
        m, s = 3, 5
        p.drawLine(m, m, m + s, m); p.drawLine(m, m, m, m + s)
        p.drawLine(size - m - s, m, size - m, m); p.drawLine(size - m, m, size - m, m + s)
        p.drawLine(m, size - m - s, m, size - m); p.drawLine(m, size - m, m + s, size - m)
        p.drawLine(size - m - s, size - m, size - m, size - m); p.drawLine(size - m, size - m - s, size - m, size - m)
        p.end()
        return QIcon(pix)

    # ════════════════════════════════════════
    #  字幕
    # ════════════════════════════════════════

    def _on_subtitle_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet('font-size: 12px; padding: 4px;')
        delay = self.player.get_subtitle_delay()
        if delay == 0:
            menu.addAction('字幕已同步').setEnabled(False)
        else:
            menu.addAction(f'偏移: {delay/1000:+.1f}s').setEnabled(False)
        menu.addSeparator()
        menu.addAction('[添加字幕文件]', self._open_subtitle_dialog)
        menu.addAction('[切换字幕轨道]', self._cycle_subtitle_track)
        menu.addSeparator()
        menu.addAction('[提前 0.5s]', lambda: self._adjust_subtitle_offset(-500))
        menu.addAction('[延后 0.5s]', lambda: self._adjust_subtitle_offset(500))
        if delay != 0:
            menu.addSeparator()
            menu.addAction('[重置同步]', lambda: self._adjust_subtitle_offset(-delay))
        bp = self.btn_subtitle.mapToGlobal(self.btn_subtitle.rect().bottomLeft())
        menu.exec(bp - QPoint(0, menu.sizeHint().height() + self.btn_subtitle.height()))

    def _open_subtitle_dialog(self):
        fp, _ = QFileDialog.getOpenFileName(
            self, '选择字幕文件', '', '字幕文件 (*.srt *.ass *.ssa *.vtt);;所有文件 (*)')
        if fp:
            self.player.set_subtitle_file(fp)
            self.btn_subtitle.setToolTip(f'已加载: {os.path.basename(fp)}')

    def _cycle_subtitle_track(self):
        self.player.cycle_subtitle()

    def _adjust_subtitle_offset(self, delta_ms):
        new = self.player.get_subtitle_delay() + delta_ms
        self.player.set_subtitle_delay(new)
        self._update_subtitle_delay_label()
        self._save_subtitle_offset()

    def _update_subtitle_delay_label(self):
        o = self.player.get_subtitle_delay()
        if o == 0:       self.sub_delay_label.setText('同步')
        elif o > 0:      self.sub_delay_label.setText(f'+{o/1000:.1f}s')
        else:            self.sub_delay_label.setText(f'{o/1000:.1f}s')

    def _save_subtitle_offset(self):
        p = self.player.current_file
        if not p: return
        data = get_setting('subtitle_offsets', {})
        o = self.player.get_subtitle_delay()
        if o == 0: data.pop(os.path.normpath(p), None)
        else:      data[os.path.normpath(p)] = o
        set_setting('subtitle_offsets', data)

    def _restore_subtitle_offset(self, fp):
        data = get_setting('subtitle_offsets', {})
        saved = data.get(os.path.normpath(fp), 0)
        self.player.set_subtitle_delay(saved)
        self._update_subtitle_delay_label()

    # ════════════════════════════════════════
    #  进度记忆
    # ════════════════════════════════════════

    def _save_playback_progress(self):
        p = self.player.current_file
        if not p or self.player.duration <= 0: return
        data = get_setting('playback_progress', {})
        pos = self.player.position
        if 10000 < pos < self.player.duration - 5000:
            data[os.path.normpath(p)] = pos
        else:
            data.pop(os.path.normpath(p), None)
        set_setting('playback_progress', data)

    def _restore_playback_progress(self, fp):
        data = get_setting('playback_progress', {})
        saved = data.get(os.path.normpath(fp), 0)
        if saved > 0:
            self.player.seek(saved)

    # ════════════════════════════════════════
    #  生命周期
    # ════════════════════════════════════════

    def cleanup(self):
        self._save_playback_progress()
        self._fs_sync.stop()
        self.player.cleanup()
