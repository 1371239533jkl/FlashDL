"""
mpv_player.py — 基于 mpv 子进程 + Lua 桥接的视频播放器封装

架构：
  1. 首次需播放时启动 mpv（空闲模式 + Lua 桥接脚本）
  2. Python 通过写入 temp/mpv_cmd.json 发送命令（Lua 每 500ms 读取执行）
  3. Lua 每 80ms 将播放状态写入 temp/mpv_state.json
  4. Python QTimer 每 100ms 读取状态并发射 Qt 信号

接口兼容旧 VideoPlayer（position_changed / duration_changed / playback_state_changed / media_status_changed）
"""

import json
import os
import shutil

from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QProcess

import config


class MpvPlayer(QObject):
    """mpv 播放器封装 — 子进程 + JSON 文件桥接"""

    # ── 状态常量（与 QMediaPlayer 对齐） ──
    STOPPED = 0
    PLAYING = 1
    PAUSED = 2
    END_OF_MEDIA = 7
    LOADED = 4

    # ── 信号 ──
    position_changed = pyqtSignal(int)
    duration_changed = pyqtSignal(int)
    playback_state_changed = pyqtSignal(int)
    media_status_changed = pyqtSignal(int)

    def __init__(self, video_widget):
        super().__init__()
        self._widget = video_widget           # QFrame (WA_NativeWindow)
        self._proc: QProcess | None = None    # 单一 mpv 进程
        self._running = False                 # mpv 是否已启动成功
        self._hwnd = 0

        # ── 本地Cache ──
        self._duration = 0
        self._position = 0
        self._volume = 70
        self._speed = 1.0
        self._sub_delay = 0.0
        self._current_file = ''
        self._paused = False
        self._eof = False

        # ── 桥接文件路径 ──
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._temp_dir = os.path.join(base, 'temp')
        os.makedirs(self._temp_dir, exist_ok=True)
        self._state_file = os.path.join(self._temp_dir, 'mpv_state.json')
        self._cmd_file   = os.path.join(self._temp_dir, 'mpv_cmd.json')
        self._lua_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mpv_bridge.lua')

        # 检查 Lua 脚本是否存在
        if not os.path.exists(self._lua_script):
            raise FileNotFoundError(f"mpv_bridge.lua not found at {self._lua_script}")

        # ── 轮询定时器 ──
        self._poll = QTimer(self)
        self._poll.setInterval(100)
        self._poll.timeout.connect(self._tick)

        # ── 找 mpv ──
        self._mpv = self._find_mpv()

        # ── 初始化桥接文件 ──
        self._init_files()

    # ══════════════════════════════════════════
    #  内部
    # ══════════════════════════════════════════

    def _find_mpv(self):
        for p in [
            r"C:\Program Files\MPV Player\mpv.exe",
            r"C:\Program Files\MPV Player\mpv.com",
        ]:
            if os.path.exists(p):
                return p
        # fallback: 从 PATH 找
        found = shutil.which("mpv") or shutil.which("mpv.exe") or shutil.which("mpv.com")
        if found:
            return found
        return "mpv.exe"

    def _init_files(self):
        """初始化状态文件和命令文件"""
        empty = {"pos":0,"dur":0,"pause":True,"speed":1,"vol":70,
                 "file":"","path":"","sub_delay":0,"eof":False}
        with open(self._state_file, 'w') as f:
            json.dump(empty, f)
        open(self._cmd_file, 'w').close()

    def _hwnd_valid(self):
        h = int(self._widget.winId()) if self._widget else 0
        return h > 0

    def _start_mpv(self):
        """启动 mpv 进程（空闲模式，等待 load 命令）"""
        if self._running:
            return

        hwnd = int(self._widget.winId())
        if not hwnd:
            return

        env = os.environ.copy()
        env.pop("DISPLAY", None)

        args = [
            f"--wid={hwnd}",
            "--idle=yes",
            "--keep-open=yes",
            f"--script={self._lua_script}",
            f"--script-opts=state-file={self._state_file},cmd-file={self._cmd_file}",
            "--no-terminal",
            "--quiet",
            "--osc=no",
            "--osd-level=0",
            # 字幕默认配置
            "--sub-auto=fuzzy",
            "--sub-font-size=18",
            "--sub-font=Microsoft YaHei",
            "--sub-border-size=2.5",
            "--sub-color=#FFFFFF",
            "--sub-border-color=#000000",
            "--sub-margin-y=40",
            "--sub-use-margins=yes",
            "--sub-ass-override=strip",
            # 硬件加速
            "--hwdec=auto",
            "--vo=gpu",
        ]

        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.finished.connect(self._on_mpv_exit)

        proc.start(self._mpv, args)
        started = proc.waitForStarted(3000)

        if not started:
            proc.kill()
            return

        self._proc = proc
        self._running = True
        self._poll.start()

    def _stop_mpv(self):
        """停止 mpv 进程"""
        self._running = False
        self._poll.stop()
        if self._proc:
            try:
                self._write_cmd(["quit"])
                self._proc.waitForFinished(2000)
            except Exception:
                pass
            if self._proc.state() != QProcess.ProcessState.NotRunning:
                self._proc.kill()
            self._proc = None

    def _write_cmd(self, command):
        """向命令文件追加一行 JSON"""
        try:
            with open(self._cmd_file, 'a', encoding='utf-8') as f:
                if isinstance(command, list):
                    f.write(json.dumps({"command": command}, ensure_ascii=False) + '\n')
                elif isinstance(command, str):
                    f.write(json.dumps({"command": command}, ensure_ascii=False) + '\n')
                elif isinstance(command, dict):
                    f.write(json.dumps(command, ensure_ascii=False) + '\n')
        except OSError:
            pass

    def _read_state(self):
        """读取 mpv 写入的状态"""
        try:
            with open(self._state_file, 'r', encoding='utf-8') as f:
                return json.loads(f.read())
        except (OSError, json.JSONDecodeError):
            return None

    def _tick(self):
        """100ms 轮询：读状态 → 发射信号"""
        if not self._running:
            return
        s = self._read_state()
        if not s:
            return

        # 位置
        pos = int(s.get('pos', 0) * 1000)
        if pos != self._position:
            self._position = pos
            self.position_changed.emit(pos)

        # 时长
        dur = int(s.get('dur', 0) * 1000)
        if dur > 0 and dur != self._duration:
            self._duration = dur
            self.duration_changed.emit(dur)

        # 暂停/播放状态
        paused = s.get('pause', True)
        new_state = self.PAUSED if paused else self.PLAYING
        if new_state != self._playback_state:
            self._playback_state = new_state
            self._paused = paused
            self.playback_state_changed.emit(new_state)

        # 文件变化
        fname = s.get('file', '')
        if fname and fname != os.path.basename(self._current_file):
            self._current_file = s.get('path', fname)

        # EOF
        eof = s.get('eof', False)
        if eof and not self._eof:
            self._eof = True
            self.media_status_changed.emit(self.END_OF_MEDIA)
        elif not eof:
            self._eof = False

    def _on_mpv_exit(self, exit_code):
        self._running = False
        self._poll.stop()
        self._playback_state = self.STOPPED
        self.playback_state_changed.emit(self.STOPPED)

    # ══════════════════════════════════════════
    #  公开接口（与旧 VideoPlayer 兼容）
    # ══════════════════════════════════════════

    def load(self, file_path: str):
        """加载并播放视频文件"""
        self._current_file = file_path
        self._eof = False

        # 确保 mpv 进程在跑
        if not self._running:
            self._start_mpv()
            if not self._running:
                # mpv 启动失败，延迟重试
                QTimer.singleShot(300, lambda: self.load(file_path))
                return

        # 发送 loadfile 命令
        self._write_cmd(["loadfile", file_path, "replace"])
        # 稍后发射 LOADED 信号
        QTimer.singleShot(600, lambda: self.media_status_changed.emit(self.LOADED))

    def play(self):
        self._write_cmd(["set_property", "pause", False])
        self._paused = False

    def pause(self):
        self._write_cmd(["set_property", "pause", True])
        self._paused = True

    def toggle_play(self):
        if self._paused:
            self.play()
            return True
        else:
            self.pause()
            return False

    def stop(self):
        self._stop_mpv()
        self._current_file = ''

    def seek(self, ms: int):
        self._write_cmd(["seek", ms / 1000, "absolute"])

    def seek_relative(self, delta_ms: int):
        self._write_cmd(["seek", delta_ms / 1000, "relative"])

    # --- 音量 ---
    def set_volume(self, v: int):
        self._volume = max(0, min(100, v))
        self._write_cmd(["set_property", "volume", self._volume])

    def get_volume(self):
        return self._volume

    def set_muted(self, m: bool):
        self._write_cmd(["set_property", "mute", "yes" if m else "no"])

    # --- 倍速 ---
    def set_playback_rate(self, rate: float):
        self._speed = rate
        self._write_cmd(["set_property", "speed", rate])

    def get_playback_rate(self):
        return self._speed

    # --- 字幕 ---
    def set_subtitle_file(self, path: str):
        self._write_cmd(["sub-add", path, "select"])

    def get_subtitle_delay(self):
        return self._sub_delay

    def set_subtitle_delay(self, ms: float):
        self._sub_delay = ms
        self._write_cmd(["set_property", "sub-delay", ms / 1000])

    def cycle_subtitle(self):
        self._write_cmd(["cycle", "sub"])

    # --- 属性 ---
    @property
    def is_playing(self):
        return self._playback_state == self.PLAYING

    @property
    def position(self):
        return self._position

    @property
    def duration(self):
        return self._duration

    @property
    def current_file(self):
        return self._current_file

    # --- 生命周期 ---
    def cleanup(self):
        self._stop_mpv()
        for f in [self._state_file, self._cmd_file]:
            try:
                os.remove(f)
            except OSError:
                pass
