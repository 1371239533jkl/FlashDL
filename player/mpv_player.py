# -*- coding: utf-8 -*-
"""MpvPlayer — 基于 python-mpv C API 的播放器封装层

使用 python-mpv 库直接调用 libmpv，通过 wid 嵌入 PyQt6 窗口渲染。
采用观察者模式（QTimer 50ms 轮询）同步播放状态并发射信号。

接口与 VideoPlayer 完全兼容，可直接替换 import。
已废弃旧的 mpv_bridge.lua QProcess 方案。
"""

import mpv
from PyQt6.QtCore import QObject, QTimer, pyqtSignal


class MpvPlayer(QObject):
    """基于 python-mpv 的播放器封装

    Args:
        container: QWidget，mpv 通过 wid 嵌入渲染
        parent: 父 QObject
    """

    # 状态常量（与 QMediaPlayer 一致）
    STOPPED = 0
    PLAYING = 1
    PAUSED = 2
    LOADED = 3
    END_OF_MEDIA = 4

    # 信号
    position_changed = pyqtSignal(int)
    duration_changed = pyqtSignal(int)
    playback_state_changed = pyqtSignal(int)
    media_status_changed = pyqtSignal(int)

    def __init__(self, container, parent=None):
        super().__init__(parent)
        self._container = container
        self._current_file = ''

        # 缓存状态
        self._position = 0
        self._duration = 0
        self._paused = False
        self._eof = False
        self._playback_state = self.STOPPED
        self._volume = 70
        self._speed = 1.0
        self._sub_delay = 0.0
        self._loaded = False

        # 创建 mpv 实例，嵌入到 container
        wid = int(container.winId())
        self._mpv = mpv.MPV(
            wid=str(wid),
            keep_open='yes',
            osc='no',
            input_default_bindings=True,
            input_vo_keyboard=True,
            ytdl=False,
            sub_auto=False,
        )

        # 初始化音量
        self._mpv.volume = 70

        # 观察者模式：50ms 定时轮询
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(50)
        self._poll_timer.timeout.connect(self._poll_state)
        self._poll_timer.start()

    # ── 状态轮询 ──────────────────────────────────────────────

    def _poll_state(self):
        """轮询 mpv 属性，检测变化时发射信号"""
        try:
            # ── 位置 ──
            pos = self._mpv.time_pos
            if pos is not None:
                pos_ms = int(pos * 1000)
                if abs(pos_ms - self._position) > 80:
                    self._position = pos_ms
                    self.position_changed.emit(pos_ms)

            # ── 时长 ──
            dur = self._mpv.duration
            if dur is not None:
                dur_ms = int(dur * 1000)
                if dur_ms != self._duration:
                    self._duration = dur_ms
                    self.duration_changed.emit(dur_ms)
                # 检测媒体加载完毕（duration 从无到有）
                if dur_ms > 0 and not self._loaded:
                    self._loaded = True
                    self.media_status_changed.emit(self.LOADED)

            # ── 暂停 / 播放状态 ──
            paused = self._mpv.pause
            if paused != self._paused:
                self._paused = paused
                if not paused and self._eof:
                    self._eof = False
                new_state = self.PAUSED if paused else self.PLAYING
                if new_state != self._playback_state:
                    self._playback_state = new_state
                    self.playback_state_changed.emit(new_state)

            # ── EOF ──
            if self._loaded:
                eof = self._mpv.eof_reached
                if eof and not self._eof:
                    self._eof = True
                    self.media_status_changed.emit(self.END_OF_MEDIA)

            # ── 音量 ──
            vol = self._mpv.volume
            if vol != self._volume:
                self._volume = vol

            # ── 倍速 ──
            speed = self._mpv.speed
            if speed != self._speed:
                self._speed = speed

            # ── 字幕延迟 ──
            sub_delay = self._mpv.sub_delay
            if sub_delay != self._sub_delay:
                self._sub_delay = sub_delay
        except Exception:
            pass  # mpv 属性读取偶发失败，不阻塞轮询

    # ── 播放控制 ──────────────────────────────────────────────

    def load(self, file_path: str):
        """加载视频文件并自动开始播放"""
        self._current_file = file_path
        self._loaded = False
        self._eof = False
        self._position = 0
        self._duration = 0
        normalized = file_path.replace('\\', '/')
        self._mpv.play(normalized)
        self._mpv.pause = False
        self._paused = False
        self._playback_state = self.PLAYING
        self.playback_state_changed.emit(self.PLAYING)

    def play(self):
        """播放"""
        if self._current_file:
            self._mpv.pause = False
            self._paused = False
            if self._playback_state != self.PLAYING:
                self._playback_state = self.PLAYING
                self.playback_state_changed.emit(self.PLAYING)

    def pause(self):
        """暂停"""
        self._mpv.pause = True
        self._paused = True
        if self._playback_state != self.PAUSED:
            self._playback_state = self.PAUSED
            self.playback_state_changed.emit(self.PAUSED)

    def toggle_play(self):
        """切换播放/暂停"""
        if self._paused or self._eof:
            self.play()
        else:
            self.pause()

    def stop(self):
        """停止播放"""
        self._mpv.command('stop')
        self._paused = True
        self._eof = False
        self._loaded = False
        if self._playback_state != self.STOPPED:
            self._playback_state = self.STOPPED
            self.playback_state_changed.emit(self.STOPPED)

    def seek(self, position_ms: int):
        """跳转到指定位置(毫秒)"""
        sec = max(0.0, position_ms / 1000.0)
        self._mpv.time_pos = sec

    # ── 属性 ──────────────────────────────────────────────────

    @property
    def is_playing(self) -> bool:
        """是否正在播放"""
        return not self._paused and not self._eof and self._current_file != ''

    @property
    def duration(self) -> int:
        """视频总时长(毫秒)"""
        return self._duration

    @property
    def position(self) -> int:
        """当前播放位置(毫秒)"""
        return self._position

    @property
    def current_file(self) -> str:
        """当前播放文件路径"""
        return self._current_file

    # ── 音量 ──────────────────────────────────────────────────

    def set_volume(self, volume: int):
        """设置音量 0-100"""
        v = max(0, min(100, volume))
        self._mpv.volume = v
        self._volume = v

    def get_volume(self) -> int:
        """获取当前音量(0-100)"""
        return self._volume

    def volume(self) -> int:
        """获取当前音量(0-100) — 别名"""
        return self._volume

    # ── 倍速 ──────────────────────────────────────────────────

    def set_rate(self, rate: float):
        """设置播放倍速"""
        self._mpv.speed = rate
        self._speed = rate

    @property
    def playback_rate(self) -> float:
        """当前播放倍速"""
        return self._speed

    # 别名（兼容 player_tab.py 中的旧方法名）
    def set_playback_rate(self, rate: float):
        """设置播放倍速 — 别名"""
        self.set_rate(rate)

    def get_playback_rate(self) -> float:
        """获取当前播放倍速 — 别名"""
        return self._speed

    # ── 全屏视频拉伸 ──────────────────────────────────────────

    def set_fill_screen(self, enabled: bool):
        """全屏时拉伸视频铺满画面
        
        关闭 keepaspect，mpv 将拉伸视频填满整个渲染区域。
        """
        self._mpv.keepaspect = not enabled

    # ── 字幕（mpv 原生 libass 渲染）───────────────────────────

    def add_subtitle(self, file_path: str):
        """添加字幕文件（mpv libass 原生渲染）"""
        normalized = file_path.replace('\\', '/')
        self._mpv.sub_add(normalized)

    def set_subtitle_delay(self, ms: int):
        """设置字幕延迟(毫秒)，正数=字幕延后显示"""
        self._mpv.sub_delay = ms / 1000.0

    def get_subtitle_delay(self) -> int:
        """获取当前字幕延迟(毫秒)"""
        return int(self._sub_delay * 1000)

    # ── 清理 ──────────────────────────────────────────────────

    def cleanup(self):
        """释放 mpv 资源"""
        self._poll_timer.stop()
        try:
            self._mpv.terminate()
        except Exception:
            pass  # mpv 已退出时 terminate 可能抛异常
        self._playback_state = self.STOPPED
