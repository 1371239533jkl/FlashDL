# -*- coding: utf-8 -*-
"""视频播放器核心 - 封装QMediaPlayer"""

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget

import config


class VideoPlayer:
    """视频播放器封装"""

    def __init__(self, video_widget: QVideoWidget):
        self.video_widget = video_widget

        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(video_widget)

        self.audio_output.setVolume(config.DEFAULT_VOLUME / 100)
        self._current_file = ''

    @property
    def is_playing(self) -> bool:
        return self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    @property
    def duration(self) -> int:
        """视频总时长(毫秒)"""
        return self.player.duration()

    @property
    def position(self) -> int:
        """当前播放位置(毫秒)"""
        return self.player.position()

    @property
    def current_file(self) -> str:
        return self._current_file

    def load(self, file_path: str):
        """加载视频文件"""
        self._current_file = file_path
        self.player.setSource(QUrl.fromLocalFile(file_path))

    def play(self):
        self.player.play()

    def pause(self):
        self.player.pause()

    def toggle_play(self):
        if self.is_playing:
            self.pause()
        else:
            self.play()

    def stop(self):
        self.player.stop()

    def seek(self, position_ms: int):
        self.player.setPosition(position_ms)

    def set_volume(self, level: int):
        """设置音量 0-100"""
        self.audio_output.setVolume(max(0, min(100, level)) / 100)

    def get_volume(self) -> int:
        return int(self.audio_output.volume() * 100)

    def set_playback_rate(self, rate: float):
        self.player.setPlaybackRate(rate)

    def get_playback_rate(self) -> float:
        return self.player.playbackRate()

    def cleanup(self):
        self.player.stop()
        self.player.setSource(QUrl())
