# -*- coding: utf-8 -*-
"""HLS/m3u8 VOD 下载任务。"""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from PyQt6.QtCore import QThread, QTimer, pyqtSignal

import config
from core.base_task import BaseDownloadTask
from utils.format_utils import ensure_long_path


class _HLSWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, task):
        super().__init__()
        self._task = task
        self._paused = False
        self._stopped = False

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def stop(self):
        self._stopped = True

    def run(self):
        try:
            for segment in self._task.segments:
                if self._stopped:
                    return
                if segment['completed']:
                    continue
                while self._paused and not self._stopped:
                    self.msleep(100)
                response = requests.get(segment['url'], headers=self._task.headers, stream=True,
                                        timeout=(config.CONNECT_TIMEOUT, config.READ_TIMEOUT),
                                        proxies=config.get_requests_proxy(),
                                        verify=config.should_verify_cert(segment['url']))
                response.raise_for_status()
                with open(segment['path'], 'wb') as output:
                    for block in response.iter_content(config.CHUNK_BUFFER_SIZE):
                        if self._stopped:
                            return
                        while self._paused and not self._stopped:
                            self.msleep(100)
                        if block:
                            output.write(block)
                            self.progress.emit(len(block))
                segment['completed'] = True
                self._task._save_state()
            self.finished.emit()
        except Exception as exc:
            self.failed.emit(str(exc))


class HLSDownloadTask(BaseDownloadTask):
    """下载未加密、TS 分片的 HLS 点播，并由 FFmpeg 无重新编码封装为 MP4。"""

    progress_updated = pyqtSignal(str, dict)
    status_changed = pyqtSignal(str, str)
    completed = pyqtSignal(str, str)
    failed = pyqtSignal(str, str)

    def __init__(self, url, save_dir, file_name='', thread_count=1, task_id=None, headers=None):
        super().__init__(url, ensure_long_path(save_dir), file_name, task_id)
        self.thread_count = 1
        self.headers = headers or {}
        self.segments = []
        self.is_prepared = False
        self._worker = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_progress)
        self._state_dir = ensure_long_path(os.path.join(config.TEMP_DIR, self.task_id))
        self._segment_dir = ensure_long_path(os.path.join(self._state_dir, 'segments'))

    def prepare(self):
        try:
            playlist = self._fetch_playlist(self.url)
            if '#EXT-X-STREAM-INF' in playlist:
                self.url = self._select_variant(playlist)
                playlist = self._fetch_playlist(self.url)
            if '#EXT-X-KEY' in playlist or '#EXT-X-MAP' in playlist:
                raise ValueError('暂不支持加密或 fMP4 格式的 HLS 播放列表')
            if '#EXT-X-ENDLIST' not in playlist:
                raise ValueError('暂不支持直播中的动态 HLS 播放列表')
            if not shutil.which('ffmpeg'):
                raise ValueError('未检测到 FFmpeg，无法将 HLS 分片合并为 MP4')

            urls = [urljoin(self.url, line.strip()) for line in playlist.splitlines()
                    if line.strip() and not line.strip().startswith('#')]
            if not urls:
                raise ValueError('播放列表中未找到媒体分片')
            if not self.file_name:
                self.file_name = f'{Path(urlparse(self.url).path).stem or "hls_video"}.mp4'
            elif not self.file_name.lower().endswith('.mp4'):
                self.file_name = f'{self.file_name}.mp4'
            os.makedirs(self.save_dir, exist_ok=True)
            self._make_unique_save_path()
            os.makedirs(self._segment_dir, exist_ok=True)
            self.segments = [{'url': url, 'path': os.path.join(self._segment_dir, f'{index:06d}.ts'), 'completed': False}
                             for index, url in enumerate(urls)]
            self.total_size = -1
            self.downloaded_size = 0
            self.is_prepared = True
            self._save_state()
            return True
        except Exception as exc:
            self.error_message = str(exc)
            self._set_status(self.FAILED)
            return False

    def start(self):
        if not self.is_prepared or self.status in (self.COMPLETED, self.MERGING):
            return
        self._set_status(self.DOWNLOADING)
        self._last_sample_size = self.downloaded_size
        self._last_sample_time = time.time()
        self._worker = _HLSWorker(self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._merge_segments)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()
        self._timer.start(config.UI_UPDATE_INTERVAL)

    def pause(self):
        if self.status == self.DOWNLOADING and self._worker:
            self._worker.pause()
            self._timer.stop()
            self._set_status(self.PAUSED)
            self._save_state()

    def resume(self):
        if self.status != self.PAUSED:
            return
        if self._worker and self._worker.isRunning():
            self._worker.resume()
            self._set_status(self.DOWNLOADING)
            self._timer.start(config.UI_UPDATE_INTERVAL)
        else:
            self.start()

    def cancel(self):
        self._timer.stop()
        if self._worker:
            self._worker.stop()
            self._worker.wait(1000)
        self._cleanup_state_dir(self._state_dir)
        self._set_status(self.FAILED)

    def retry(self):
        if self.status != self.FAILED:
            return False
        self.error_message = ''
        self.downloaded_size = sum(os.path.getsize(item['path']) for item in self.segments
                                   if item.get('completed') and os.path.exists(item['path']))
        self._set_status(self.WAITING)
        self._save_state()
        return True

    def _fetch_playlist(self, url):
        response = requests.get(url, headers=self.headers,
                                timeout=(config.CONNECT_TIMEOUT, config.READ_TIMEOUT),
                                proxies=config.get_requests_proxy(), verify=config.should_verify_cert(url))
        response.raise_for_status()
        return response.text

    def _select_variant(self, playlist):
        lines = [line.strip() for line in playlist.splitlines()]
        variants = []
        for index, line in enumerate(lines):
            if line.startswith('#EXT-X-STREAM-INF') and index + 1 < len(lines):
                try:
                    bandwidth = int(next(field.split('=', 1)[1] for field in line.split(',')
                                         if field.startswith('BANDWIDTH=')))
                except (StopIteration, ValueError):
                    bandwidth = 0
                if lines[index + 1] and not lines[index + 1].startswith('#'):
                    variants.append((bandwidth, urljoin(self.url, lines[index + 1])))
        if not variants:
            raise ValueError('主播放列表中未找到可用清晰度')
        return max(variants, key=lambda item: item[0])[1]

    def _make_unique_save_path(self):
        original_name = self.file_name
        base, ext = os.path.splitext(original_name)
        suffix = 1
        while os.path.exists(self.save_path):
            self.file_name = f'{base}({suffix}){ext}'
            suffix += 1

    def _on_progress(self, byte_count):
        self.downloaded_size += byte_count

    def _update_progress(self):
        self._emit_progress(self._sample_speed(), segment_count=len(self.segments))

    def _merge_segments(self):
        if self.status != self.DOWNLOADING:
            return
        self._timer.stop()
        self._set_status(self.MERGING)
        merged_path = os.path.join(self._state_dir, 'merged.ts')
        try:
            with open(merged_path, 'wb') as output:
                for segment in self.segments:
                    with open(segment['path'], 'rb') as source:
                        shutil.copyfileobj(source, output)
            result = subprocess.run(['ffmpeg', '-y', '-i', merged_path, '-c', 'copy', self.save_path],
                                    capture_output=True, text=True,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or 'FFmpeg 合并失败')
            self._cleanup_state_dir(self._state_dir)
            self._set_status(self.COMPLETED)
            self.completed.emit(self.task_id, self.save_path)
        except Exception as exc:
            self.error_message = str(exc)
            self._save_state()
            self._set_status(self.FAILED)
            self.failed.emit(self.task_id, self.error_message)

    def _on_failed(self, error):
        if self.status != self.PAUSED:
            self._timer.stop()
            self.error_message = error
            self._save_state()
            self._set_status(self.FAILED)
            self.failed.emit(self.task_id, error)

    def _save_state(self):
        self._atomic_json_write({'task_type': 'hls', 'task_id': self.task_id, 'url': self.url,
                                 'file_name': self.file_name, 'save_dir': self.save_dir,
                                 'downloaded_size': self.downloaded_size, 'total_size': self.total_size,
                                 'status': self.status, 'created_time': self.created_time,
                                 'headers': self.headers, 'segments': self.segments}, self._state_dir)

    @classmethod
    def load_from_state(cls, task_dir):
        try:
            with open(os.path.join(task_dir, 'task.json'), encoding='utf-8') as source:
                state = json.load(source)
            task = cls(state['url'], state['save_dir'], state['file_name'], task_id=state['task_id'],
                       headers=state.get('headers', {}))
            task.segments = state.get('segments', [])
            task.total_size = state.get('total_size', -1)
            task.downloaded_size = sum(os.path.getsize(item['path']) for item in task.segments
                                       if item.get('completed') and os.path.exists(item['path']))
            task.created_time = state.get('created_time', '')
            task.status = task.PAUSED
            task.is_prepared = True
            return task
        except Exception:
            return None
