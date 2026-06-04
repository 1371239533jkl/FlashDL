# -*- coding: utf-8 -*-
"""MpvPlayer — 基于 mpv 子进程 + Named Pipe JSON IPC 的播放器封装层

通过 QProcess 启动 mpv.exe，使用 --wid 嵌入 PyQt6 QWidget 渲染。
采用 Windows Named Pipe 进行 JSON IPC 通信，50ms 轮询同步状态。
不需要 libmpv.dll，只需要系统已安装 mpv（通过 winget 等）。

接口与 VideoPlayer / python-mpv 版完全兼容，可直接替换 import。
"""

import json
import os
import random
import string

import win32file
import win32pipe
import pywintypes

from PyQt6.QtCore import QObject, QProcess, QThread, QTimer, pyqtSignal


def _random_suffix(length=8):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


class MpvPlayer(QObject):
    """基于 mpv 子进程 + Named Pipe IPC 的播放器封装

    Args:
        container: QWidget，mpv 通过 --wid 嵌入渲染
        parent: 父 QObject
    """

    # 状态常量
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
        self._current_file = ""

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

        # 唯一的 pipe 名（避免多实例冲突）
        pipe_name = f"mpv-{os.getpid()}-{_random_suffix()}"
        self._pipe_path = rf"\\.\pipe\{pipe_name}"

        # 启动 mpv 子进程
        wid = int(container.winId())
        self._process = QProcess(self)
        self._process.setProgram("mpv")
        # 注意：--input-ipc-server 接受转义后的路径，但 mpv 会移除一层反斜杠
        # 所以这里传 \\\\.\\pipe\\name（4个反斜杠）
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
        if not self._process.waitForStarted(5000):
            raise RuntimeError("mpv 进程启动失败")

        # 连接到 named pipe（等待 mpv 创建 pipe 服务端）
        self._pipe_handle = None
        for _ in range(50):
            try:
                self._pipe_handle = win32file.CreateFile(
                    self._pipe_path,
                    win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                    0,  # 不共享
                    None,
                    win32file.OPEN_EXISTING,
                    0,
                    None,
                )
                break
            except pywintypes.error as e:
                if e.winerror == 2:  # 文件未找到（pipe 还没创建好）
                    pass  # 继续重试
                else:
                    raise
            QThread.msleep(100)  # 使用 QThread 避免阻塞 Qt
        else:
            raise RuntimeError(f"无法连接到 mpv IPC pipe: {self._pipe_path}")

        # 初始音量
        self._send_cmd_no_wait(["set_property", "volume", 70])

        # 观察者模式：每 50ms 轮询所有关心属性
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(50)
        self._poll_timer.timeout.connect(self._poll_state)
        self._poll_timer.start()

    # ── IPC 通信 ───────────────────────────────────────────────

    def _send_cmd(self, command: list) -> dict | None:
        """发送 JSON IPC 命令并读取响应"""
        try:
            msg = json.dumps({"command": command}) + "\n"
            win32file.WriteFile(self._pipe_handle, msg.encode())
            # 等待并读取响应
            for _ in range(10):
                try:
                    # Peek 检查是否有数据
                    hr, data, _, _ = win32pipe.PeekNamedPipe(self._pipe_handle, 0)
                    if data and len(data) > 0:
                        break
                except pywintypes.error:
                    pass
                QThread.msleep(5)
            # 读取数据
            hr, raw = win32file.ReadFile(self._pipe_handle, 4096)
            if raw and len(raw) > 0:
                return json.loads(raw.decode().strip())
        except Exception:
            pass
        return None

    def _send_cmd_no_wait(self, command: list):
        """发送 JSON IPC 命令，不等响应"""
        try:
            msg = json.dumps({"command": command}) + "\n"
            win32file.WriteFile(self._pipe_handle, msg.encode())
        except Exception:
            pass

    def _get_property(self, name: str):
        """获取 mpv 属性值"""
        resp = self._send_cmd(["get_property", name])
        if resp and resp.get("error") == "success":
            return resp.get("data")
        return None

    # ── 状态轮询 ──────────────────────────────────────────────

    def _poll_state(self):
        """轮询 mpv 属性，检测变化时发射信号"""
        # 批量发送请求
        try:
            commands = [
                ["get_property", "time-pos"],
                ["get_property", "duration"],
                ["get_property", "pause"],
                ["get_property", "eof-reached"],
                ["get_property", "volume"],
                ["get_property", "speed"],
                ["get_property", "sub-delay"],
            ]
            for cmd in commands:
                msg = json.dumps({"command": cmd}) + "\n"
                win32file.WriteFile(self._pipe_handle, msg.encode())

            # 读取响应（按顺序）
            responses = []
            for _ in range(len(commands)):
                for __ in range(5):
                    try:
                        hr, peek_data, _, _ = win32pipe.PeekNamedPipe(self._pipe_handle, 0)
                        if peek_data and len(peek_data) > 0:
                            break
                    except pywintypes.error:
                        pass
                    QThread.msleep(1)
                try:
                    hr, raw = win32file.ReadFile(self._pipe_handle, 4096)
                    if raw:
                        resp = json.loads(raw.decode().strip())
                        responses.append(resp)
                except Exception:
                    responses.append(None)
        except Exception:
            return

        # 解析响应
        if len(responses) >= 7:
            pos = self._safe_data(responses, 0)
            dur = self._safe_data(responses, 1)
            paused = self._safe_data(responses, 2)
            eof = self._safe_data(responses, 3)
            volume_val = self._safe_data(responses, 4)
            speed_val = self._safe_data(responses, 5)
            sub_delay_val = self._safe_data(responses, 6)

            # ── 位置 ──
            if pos is not None:
                try:
                    pos_ms = int(float(pos) * 1000)
                    if abs(pos_ms - self._position) > 80:
                        self._position = pos_ms
                        self.position_changed.emit(pos_ms)
                except (ValueError, TypeError):
                    pass

            # ── 时长 + 媒体加载 ──
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

            # ── 暂停 / 播放状态 ──
            if paused is not None:
                paused_bool = bool(paused)
                if paused_bool != self._paused:
                    self._paused = paused_bool
                    if not paused_bool and self._eof:
                        self._eof = False
                    new_state = self.PAUSED if paused_bool else self.PLAYING
                    if new_state != self._playback_state:
                        self._playback_state = new_state
                        self.playback_state_changed.emit(new_state)

            # ── EOF ──
            if self._loaded and eof is not None:
                eof_bool = bool(eof)
                if eof_bool and not self._eof:
                    self._eof = True
                    self.media_status_changed.emit(self.END_OF_MEDIA)

            # ── 音量 ──
            if volume_val is not None:
                try:
                    vol = int(volume_val)
                    if vol != self._volume:
                        self._volume = vol
                except (ValueError, TypeError):
                    pass

            # ── 倍速 ──
            if speed_val is not None:
                try:
                    spd = float(speed_val)
                    if spd != self._speed:
                        self._speed = spd
                except (ValueError, TypeError):
                    pass

            # ── 字幕延迟 ──
            if sub_delay_val is not None:
                try:
                    sd = float(sub_delay_val)
                    if sd != self._sub_delay:
                        self._sub_delay = sd
                except (ValueError, TypeError):
                    pass

    def _safe_data(self, responses, idx):
        if idx < len(responses) and responses[idx]:
            return responses[idx].get("data")
        return None

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
        self._send_cmd_no_wait(["loadfile", normalized])
        self._send_cmd_no_wait(["set_property", "pause", False])
        self._paused = False
        self._playback_state = self.PLAYING
        self.playback_state_changed.emit(self.PLAYING)

    def play(self):
        if self._current_file:
            self._send_cmd_no_wait(["set_property", "pause", False])
            self._paused = False
            if self._playback_state != self.PLAYING:
                self._playback_state = self.PLAYING
                self.playback_state_changed.emit(self.PLAYING)

    def pause(self):
        self._send_cmd_no_wait(["set_property", "pause", True])
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
        self._send_cmd_no_wait(["stop"])
        self._paused = True
        self._eof = False
        self._loaded = False
        if self._playback_state != self.STOPPED:
            self._playback_state = self.STOPPED
            self.playback_state_changed.emit(self.STOPPED)

    def seek(self, position_ms: int):
        sec = max(0.0, position_ms / 1000.0)
        self._send_cmd_no_wait(["seek", sec, "absolute"])

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
        self._send_cmd_no_wait(["set_property", "volume", v])
        self._volume = v

    def get_volume(self) -> int:
        return self._volume

    def volume(self) -> int:
        return self._volume

    # ── 倍速 ──────────────────────────────────────────────────

    def set_rate(self, rate: float):
        self._send_cmd_no_wait(["set_property", "speed", rate])
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
        normalized = file_path.replace("\\", "/")
        self._send_cmd_no_wait(["sub-add", normalized])

    def set_subtitle_delay(self, ms: int):
        self._send_cmd_no_wait(["set_property", "sub-delay", ms / 1000.0])

    def get_subtitle_delay(self) -> int:
        return int(self._sub_delay * 1000)

    # ── 清理 ──────────────────────────────────────────────────

    def cleanup(self):
        self._poll_timer.stop()
        try:
            win32file.CloseHandle(self._pipe_handle)
        except Exception:
            pass
        if self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.terminate()
            self._process.waitForFinished(3000)
            if self._process.state() != QProcess.ProcessState.NotRunning:
                self._process.kill()
        self._playback_state = self.STOPPED
