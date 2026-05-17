# -*- coding: utf-8 -*-
"""下载工作线程 - 执行单个分块的HTTP Range下载"""

import time
import threading
import requests
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal

import config

# 关闭不安全连接警告（CDN证书不匹配时）
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class DownloadWorker(QThread):
    """单个分块下载工作线程（支持自动重试）"""

    # 信号: chunk_id, 本次新增字节数
    chunk_progress = pyqtSignal(int, int)
    # 信号: chunk_id
    chunk_completed = pyqtSignal(int)
    # 信号: chunk_id, 错误信息
    chunk_error = pyqtSignal(int, str)

    def __init__(self, chunk_id: int, url: str, temp_file: str,
                 start_byte: int, end_byte: int, downloaded_bytes: int = 0,
                 headers: dict = None):
        super().__init__()
        self.chunk_id = chunk_id
        self.url = url
        self.temp_file = temp_file
        self.start_byte = start_byte
        self.end_byte = end_byte
        self.downloaded_bytes = downloaded_bytes
        self._custom_headers = headers or {}
        self._paused = False
        # 使用 Event 保证线程间可见性
        self._stopped = threading.Event()

    def _check_stopped(self) -> bool:
        """检查是否已停止（线程安全）"""
        return self._stopped.is_set()

    def _wait_pause(self):
        """等待暂停解除，返回 True 如果已停止"""
        while self._paused and not self._stopped.is_set():
            time.sleep(0.05)
        return self._stopped.is_set()

    def run(self):
        """执行分块下载（带自动重试）"""
        current_pos = self.start_byte + self.downloaded_bytes

        # 检查已有临时文件的实际大小
        temp_path = Path(self.temp_file)
        if temp_path.exists():
            actual_size = temp_path.stat().st_size
            if actual_size != self.downloaded_bytes:
                self.downloaded_bytes = actual_size
                current_pos = self.start_byte + actual_size

        # 此分块已完成（仅当 end_byte 已知时检查）
        if self.end_byte >= 0 and current_pos > self.end_byte:
            self.chunk_completed.emit(self.chunk_id)
            return

        last_error = ''
        for attempt in range(1, config.MAX_RETRIES + 2):  # 初始尝试 + MAX_RETRIES 次重试
            if self._check_stopped():
                return

            # 暂停等待
            if self._wait_pause():
                return

            # 重试前等待（首次不等待）
            if attempt > 1:
                for _ in range(int(config.RETRY_DELAY * 10)):
                    if self._check_stopped() or self._paused:
                        break
                    time.sleep(0.1)
                if self._check_stopped():
                    return
                if self._wait_pause():
                    return

            # 重试时重新计算起始位置（基于已下载量）
            retry_pos = self.start_byte + self.downloaded_bytes

            headers = {
                'User-Agent': self._custom_headers.get('User-Agent',
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'),
                'Range': f'bytes={retry_pos}-{self.end_byte}'
            }
            # 合并其他自定义请求头
            for k, v in self._custom_headers.items():
                if k.lower() not in ('user-agent', 'range'):
                    headers[k] = v

            try:
                resp = requests.get(
                    self.url, headers=headers, stream=True,
                    timeout=(config.CONNECT_TIMEOUT, config.READ_TIMEOUT),
                    verify=False  # 兼容CDN证书不匹配的域名（如腾讯视频CDN）
                )
                if resp.status_code not in (200, 206):
                    # 4xx 错误不重试（除了429）
                    if 400 <= resp.status_code < 500 and resp.status_code != 429:
                        self.chunk_error.emit(self.chunk_id, f'HTTP {resp.status_code}')
                        return
                    # 5xx / 429 等错误可以重试
                    last_error = f'HTTP {resp.status_code}'
                    if attempt <= config.MAX_RETRIES:
                        continue
                    self.chunk_error.emit(self.chunk_id, last_error)
                    return

                mode = 'ab' if self.downloaded_bytes > 0 else 'wb'
                # 限速计时：记录本分块开始下载的时间戳
                chunk_start_time = time.time()
                chunk_downloaded_at_start = self.downloaded_bytes
                with open(self.temp_file, mode) as f:
                    for data in resp.iter_content(chunk_size=config.CHUNK_BUFFER_SIZE):
                        if self._check_stopped():
                            return
                        if self._wait_pause():
                            return

                        f.write(data)
                        self.downloaded_bytes += len(data)
                        self.chunk_progress.emit(self.chunk_id, len(data))

                        # 速度限制：如果配置了全局限速，控制每个分块的速率
                        if config.DOWNLOAD_SPEED_LIMIT > 0:
                            chunk_bytes = self.downloaded_bytes - chunk_downloaded_at_start
                            elapsed = time.time() - chunk_start_time
                            expected_time = chunk_bytes / config.DOWNLOAD_SPEED_LIMIT
                            if elapsed < expected_time:
                                sleep_time = expected_time - elapsed
                                while sleep_time > 0 and not self._check_stopped():
                                    chunk = min(sleep_time, 0.1)
                                    time.sleep(chunk)
                                    sleep_time -= chunk

                self.chunk_completed.emit(self.chunk_id)
                return  # 成功

            except requests.Timeout:
                last_error = '下载超时'
            except requests.ConnectionError:
                last_error = '网络连接断开'
            except IOError as e:
                self.chunk_error.emit(self.chunk_id, f'文件写入失败: {e}')
                return
            except Exception as e:
                last_error = str(e)

            # 还有重试机会时继续循环
            if attempt <= config.MAX_RETRIES:
                continue

        # 所有重试都失败了
        self.chunk_error.emit(self.chunk_id, last_error)

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def stop(self):
        self._stopped.set()
        self._paused = False
