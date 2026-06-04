# -*- coding: utf-8 -*-
"""MpvPlayer — 基于 mpv 子进程 + Named Pipe JSON IPC 的播放器封装层

通过 QProcess 启动 mpv.exe，使用 --wid 嵌入 PyQt6 QWidget 渲染。
采用 Windows Named Pipe 进行 JSON IPC 通信，50ms 轮询同步状态。
不需要 libmpv.dll，只需要系统已安装 mpv（通过 winget 等）。

初始化是异步的：__init__ 立即返回，pipe 连接通过 QTimer 重试，
连接成功后自动开始轮询。在连接成功前的命令会被静默丢弃。
"""

import json
import os
import random
import string

import win32file
import win32pipe
import pywintypes

from PyQt6.QtCore import QObject, QProcess, QTimer, pyqtSignal


_RETRY_INTERVAL = 50       # ms —— pipe 连接重试间隔
_RETRY_MAX = 60            # 最多重试 ~3 秒


def _random_suffix(length=8):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


class MpvPlayer(QObject):
    """基于 mpv 子进程 + Named Pipe IPC 的播放器封装

    初始化是异步的，Pipe 连接成功后自动启动轮询。

    Args:
        container: QWidget，mpv 通过 --wid 嵌入渲染
        parent: 父 QObject
    """

    STOPPED = 0
    PLAYING = 1
    PAUSED = 2
    LOADED = 3
    END_OF_MEDIA = 4

    position_changed = pyqtSignal(int)
    duration_changed = pyqtSignal(int)
    playback_state_changed = pyqtSignal(int)
    media_status_changed = pyqtSignal(int)

    def __init__(self, container, parent=None):
        super().__init__(parent)
        self._container = container
        self._current_file = ""
        self._pipe_handle = None
        self._connected = False
        self._retry_count = 0

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

        # 唯一的 pipe 名
        pipe_name = f"mpv-{os.getpid()}-{_random_suffix()}"
        self._pipe_path = rf"\\.\pipe\{pipe_name}"

        # 启动 mpv 子进程
        wid = int(container.winId())
        self._process = QProcess(self)
        self._process.setProgram("mpv")
        self._process.setArguments([
            f"--wid={wid}",
            f"--input-ipc-server={self._pipe_path}",
            "--keep-open=yes",
            "--osc=no",
            "--input-default-bindings",
            "--input-vo-keyboard=yes",
            "--ytdl=no",
            "--sub-auto=no",
            "--idle=yes",
        ])
        self._process.start()

        # 轮询定时器（pipe 连接成功后才 start）
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(50)
        self._poll_timer.timeout.connect(self._poll_state)

        # 异步连接重试定时器
        self._connect_timer = QTimer(self)
        self._connect_timer.setInterval(_RETRY_INTERVAL)
        self._connect_timer.timeout.connect(self._try_connect)
        self._connect_timer.start()

    def _try_connect(self):
        """定时尝试连接 named pipe（非阻塞）"""
        if self._connected:
            self._connect_timer.stop()
            return

        self._retry_count += 1
        try:
            self._pipe_handle = win32file.CreateFile(
                self._pipe_path,
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0, None,
                win32file.OPEN_EXISTING,
                0, None,
            )
            self._connected = True
            self._connect_timer.stop()
            # 初始音量
            self._send_raw(["set_property", "volume", 70])
            # 启动轮询
            self._poll_timer.start()
        except pywintypes.error as e:
            if self._retry_count >= _RETRY_MAX:
                self._connect_timer.stop()
                print(f"[MpvPlayer] 无法连接 mpv pipe（已重试 {self._retry_count} 次）: {e}")

    # ── IPC 底层 ──────────────────────────────────────────────

    def _send_raw(self, command: list):
        """发送 JSON IPC 命令（仅写入，不读响应）"""
        if not self._connected or self._pipe_handle is None:
            return
        try:
            msg = json.dumps({"command": command}) + "\n"
            win32file.WriteFile(self._pipe_handle, msg.encode())
        except Exception:
            pass

    def _read_line(self) -> str | None:
        """从 pipe 读取一行 JSON 响应（非阻塞）"""
        if not self._connected:
            return None
        try:
            hr, data, _, _ = win32pipe.PeekNamedPipe(self._pipe_handle, 0)
            if data and len(data) > 0:
                hr, raw = win32file.ReadFile(self._pipe_handle, 4096)
                if raw:
                    return raw.decode().strip()
        except Exception:
            pass
        return None

    # ── 状态轮询 ──────────────────────────────────────────────

    def _poll_state(self):
        """轮询 mpv 属性，检测变化时发射信号"""
        if not self._connected:
            return

        # 批量发送 7 个 get_property 请求
        props = [
            "time-pos", "duration", "pause", "eof-reached",
            "volume", "speed", "sub-delay",
        ]
        try:
            for name in props:
                msg = json.dumps({"command": ["get_property", name]}) + "\n"
                win32file.WriteFile(self._pipe_handle, msg.encode())
        except Exception:
            return

        # 批量读取 7 个响应
        responses = []
        deadline = QTimer.singleShot  # just a marker, we use a different approach
        for _ in range(len(props)):
            resp = None
            for __ in range(20):  # 最多等 20ms
                line = self._read_line()
                if line:
                    try:
                        resp = json.loads(line)
                    except json.JSONDecodeError:
                        pass
                    break
            responses.append(resp)

        # 解析
        pos       = self._get_data(responses, 0)
        dur       = self._get_data(responses, 1)
        paused    = self._get_data(responses, 2)
        eof       = self._get_data(responses, 3)
        vol_val   = self._get_data(responses, 4)
        spd_val   = self._get_data(responses, 5)
        sub_val   = self._get_data(responses, 6)

        self._handle_pos(pos)
        self._handle_dur(dur)
        self._handle_pause(paused, eof)
        self._handle_vol(vol_val)
        self._handle_speed(spd_val)
        self._handle_sub(sub_val)

    def _get_data(self, responses, idx):
        if idx < len(responses) and responses[idx]:
            return responses[idx].get("data")
        return None

    def _handle_pos(self, pos):
        if pos is not None:
            try:
                pos_ms = int(float(pos) * 1000)
                if abs(pos_ms - self._position) > 80:
                    self._position = pos_ms
                    self.position_changed.emit(pos_ms)
            except (ValueError, TypeError):
                pass

    def _handle_dur(self, dur):
        if dur is not None:
            try:
                dur_ms = int(float(dur) * 1000)
                if dur_ms != self._duration:
                    self._duration = dur_ms
                    self.duration_changed.emit(dur_ms)
                if dur_ms > 0 and not self._loaded:
                    self._loaded = True
                    self.media_status_changed.emit(self.LOADED)
            except (ValueError, TypeError):
                pass

    def _handle_pause(self, paused, eof):
        if paused is not None:
            pb = bool(paused)
            if pb != self._paused:
                self._paused = pb
                if not pb and self._eof:
                    self._eof = False
                new_state = self.PAUSED if pb else self.PLAYING
                if new_state != self._playback_state:
                    self._playback_state = new_state
                    self.playback_state_changed.emit(new_state)
        if self._loaded and eof is not None and bool(eof) and not self._eof:
            self._eof = True
            self.media_status_changed.emit(self.END_OF_MEDIA)

    def _handle_vol(self, val):
        if val is not None:
            try:
                v = int(val)
                if v != self._volume:
                    self._volume = v
            except (ValueError, TypeError):
                pass

    def _handle_speed(self, val):
        if val is not None:
            try:
                sp = float(val)
                if sp != self._speed:
                    self._speed = sp
            except (ValueError, TypeError):
                pass

    def _handle_sub(self, val):
        if val is not None:
            try:
                sd = float(val)
                if sd != self._sub_delay:
                    self._sub_delay = sd
            except (ValueError, TypeError):
                pass

    # ── 播放控制 ──────────────────────────────────────────────

    def load(self, file_path: str):
        if not file_path:
            return
        self._current_file = file_path
        self._loaded = False
        self._eof = False
        self._position = 0
        self._duration = 0
        normalized = file_path.replace("\\", "/")
        self._send_raw(["loadfile", normalized])
        self._send_raw(["set_property", "pause", False])
        self._paused = False
        self._playback_state = self.PLAYING
        self.playback_state_changed.emit(self.PLAYING)

    def play(self):
        if self._current_file:
            self._send_raw(["set_property", "pause", False])
            self._paused = False
            if self._playback_state != self.PLAYING:
                self._playback_state = self.PLAYING
                self.playback_state_changed.emit(self.PLAYING)

    def pause(self):
        self._send_raw(["set_property", "pause", True])
        self._paused = True
        if self._playback_state != self.PAUSED:
            self._playback_state = self.PAUSED
            self.playback_state_changed.emit(self.PAUSED)

    def toggle_play(self):
        if self._paused or self._eof:
            self.play()
        else:
            self.pause()

    def stop(self):
        self._send_raw(["stop"])
        self._paused = True
        self._eof = False
        self._loaded = False
        if self._playback_state != self.STOPPED:
            self._playback_state = self.STOPPED
            self.playback_state_changed.emit(self.STOPPED)

    def seek(self, position_ms: int):
        sec = max(0.0, position_ms / 1000.0)
        self._send_raw(["seek", sec, "absolute"])

    # ── 属性 ──────────────────────────────────────────────────

    @property
    def is_playing(self) -> bool:
        return not self._paused and not self._eof and self._current_file != ""

    @property
    def duration(self) -> int:
        return self._duration

    @property
    def position(self) -> int:
        return self._position

    @property
    def current_file(self) -> str:
        return self._current_file

    # ── 音量 ──────────────────────────────────────────────────

    def set_volume(self, volume: int):
        v = max(0, min(100, volume))
        self._send_raw(["set_property", "volume", v])
        self._volume = v

    def get_volume(self) -> int:
        return self._volume

    def volume(self) -> int:
        return self._volume

    # ── 倍速 ──────────────────────────────────────────────────

    def set_rate(self, rate: float):
        self._send_raw(["set_property", "speed", rate])
        self._speed = rate

    @property
    def playback_rate(self) -> float:
        return self._speed

    def set_playback_rate(self, rate: float):
        self.set_rate(rate)

    def get_playback_rate(self) -> float:
        return self._speed

    # ── 字幕（mpv 原生 libass 渲染）───────────────────────────

    def add_subtitle(self, file_path: str):
        self._send_raw(["sub-add", file_path.replace("\\", "/")])

    def set_subtitle_delay(self, ms: int):
        self._send_raw(["set_property", "sub-delay", ms / 1000.0])

    def get_subtitle_delay(self) -> int:
        return int(self._sub_delay * 1000)

    # ── 清理 ──────────────────────────────────────────────────

    def cleanup(self):
        self._connect_timer.stop()
        self._poll_timer.stop()
        try:
            if self._pipe_handle is not None:
                win32file.CloseHandle(self._pipe_handle)
        except Exception:
            pass
        if self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.terminate()
            self._process.waitForFinished(3000)
            if self._process.state() != QProcess.ProcessState.NotRunning:
                self._process.kill()
        self._playback_state = self.STOPPED
