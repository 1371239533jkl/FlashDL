# -*- coding: utf-8 -*-
"""MpvPlayer — 基于 mpv 子进程 + TCP JSON IPC 的播放器封装层

通过 QProcess 启动 mpv.exe（已安装），使用 --wid 嵌入 PyQt6 QWidget 渲染。
采用 TCP JSON IPC 协议通信，QTimer 50ms 轮询同步状态并发射信号。不需要 libmpv.dll。

接口与 VideoPlayer / python-mpv 版完全兼容，可直接替换 import。
"""

import json
import socket
import time

from PyQt6.QtCore import QObject, QProcess, QTimer, pyqtSignal


class MpvPlayer(QObject):
    """基于 mpv 子进程 + TCP IPC 的播放器封装

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

        # 分配空闲端口
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.bind(("127.0.0.1", 0))
        self._port = self._sock.getsockname()[1]
        self._sock.close()

        # 启动 mpv 子进程
        wid = int(container.winId())
        self._process = QProcess(self)
        self._process.setProgram("mpv")
        self._process.setArguments([
            f"--wid={wid}",
            f"--input-ipc-server=127.0.0.1:{self._port}",
            "--keep-open=yes",
            "--osc=no",
            "--input-default-bindings",
            "--input-vo-keyboard=yes",
            "--ytdl=no",
            "--sub-auto=no",
            "--idle=yes",
        ])
        self._process.start()
        self._process.waitForStarted(3000)

        # 连接 IPC socket（重试等待 mpv 启动）
        self._ipc_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        for _ in range(30):
            try:
                self._ipc_sock.connect(("127.0.0.1", self._port))
                break
            except ConnectionRefusedError:
                time.sleep(0.1)
        else:
            raise RuntimeError("mpv IPC server did not start")
        self._ipc_sock.settimeout(0.05)

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
            self._ipc_sock.sendall(msg.encode())
            data = b""
            while True:
                try:
                    chunk = self._ipc_sock.recv(4096)
                    if not chunk:
                        break
                    data += chunk
                    if b"\n" in data:
                        break
                except socket.timeout:
                    break
            if data:
                return json.loads(data.decode().strip())
        except Exception:
            pass
        return None

    def _send_cmd_no_wait(self, command: list):
        """发送 JSON IPC 命令，不等响应"""
        try:
            msg = json.dumps({"command": command}) + "\n"
            self._ipc_sock.sendall(msg.encode())
        except Exception:
            pass

    def _get_property(self, name: str):
        """获取 mpv 属性值"""
        resp = self._send_cmd(["get_property", name])
        if resp and resp.get("error") == "success":
            return resp.get("data")
        return None

    # ── 批量轮询（一次连接发送多条命令，顺序读取响应）──────

    def _poll_state(self):
        """轮询 mpv 属性，检测变化时发射信号"""
        # 收集所有属性值
        pos = self._get_property("time-pos")
        dur = self._get_property("duration")
        paused = self._get_property("pause")
        eof = self._get_property("eof-reached")
        volume_val = self._get_property("volume")
        speed_val = self._get_property("speed")
        sub_delay_val = self._get_property("sub-delay")

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

    # ── 播放控制 ──────────────────────────────────────────────

    def load(self, file_path: str):
        """加载视频文件并播放"""
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
        """播放"""
        if self._current_file:
            self._send_cmd_no_wait(["set_property", "pause", False])
            self._paused = False
            if self._playback_state != self.PLAYING:
                self._playback_state = self.PLAYING
                self.playback_state_changed.emit(self.PLAYING)

    def pause(self):
        """暂停"""
        self._send_cmd_no_wait(["set_property", "pause", True])
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
        self._send_cmd_no_wait(["stop"])
        self._paused = True
        self._eof = False
        self._loaded = False
        if self._playback_state != self.STOPPED:
            self._playback_state = self.STOPPED
            self.playback_state_changed.emit(self.STOPPED)

    def seek(self, position_ms: int):
        """跳转到指定位置(毫秒)"""
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
            self._ipc_sock.close()
        except Exception:
            pass
        if self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.terminate()
            self._process.waitForFinished(3000)
            if self._process.state() != QProcess.ProcessState.NotRunning:
                self._process.kill()
        self._playback_state = self.STOPPED
