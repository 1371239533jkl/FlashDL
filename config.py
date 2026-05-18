# -*- coding: utf-8 -*-
"""全局配置模块"""

import os
from pathlib import Path

# 应用信息
APP_NAME = "BoltDL - 视频下载 & 播放工具"
APP_VERSION = "1.0.0"

# 下载配置
DEFAULT_THREAD_COUNT = 4          # 默认下载线程数
MAX_THREAD_COUNT = 16             # 单任务最大线程数
MAX_CONCURRENT_TASKS = 3          # 同时下载任务数
CHUNK_BUFFER_SIZE = 65536         # 下载缓冲区大小(64KB)，原8KB太慢
SPEED_SAMPLE_INTERVAL = 1.0       # 速度采样间隔(秒)
SPEED_WINDOW_SIZE = 5             # 速度滑动窗口大小(秒)
STATE_SAVE_INTERVAL = 1048576     # 状态保存间隔(每1MB)
CONNECT_TIMEOUT = 10              # 连接超时(秒)
READ_TIMEOUT = 30                 # 读取超时(秒)

# 下载重试配置
MAX_RETRIES = 3                   # 下载分块失败最大重试次数
RETRY_DELAY = 2.0                 # 重试间隔(秒)

# 下载速度限制 (0=无限制, 单位: bytes/s)
DOWNLOAD_SPEED_LIMIT = 0          # 全局HTTP下载速度限制

# 路径配置
DEFAULT_DOWNLOAD_DIR = str(Path.home() / "Downloads")
TEMP_DIR = str(Path(__file__).parent / "temp" / "downloads")
DB_PATH = str(Path(__file__).parent / "data" / "history.db")

# UI配置
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 700
MIN_WINDOW_WIDTH = 800
MIN_WINDOW_HEIGHT = 600
TITLE_BAR_HEIGHT = 38
UI_UPDATE_INTERVAL = 33           # UI刷新间隔(毫秒, ~30fps)

# 支持的视频格式
VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}

# 播放器配置
PLAYBACK_RATES = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
DEFAULT_VOLUME = 70

# 字幕配置
SUBTITLE_FONT_SIZE = 16                # 字幕字体大小
SUBTITLE_AUTO_LOAD = True              # 是否自动加载同名字幕
SUBTITLE_EXTENSIONS = {'.srt', '.ass', '.ssa', '.vtt'}  # 支持的字幕格式

# BT/磁力链接配置
BT_LISTEN_PORT = 6881                # 监听端口
BT_MAX_CONNECTIONS = 400             # 全局最大连接数（原200，加速用）
BT_UPLOAD_RATE_LIMIT = 1024 * 100    # 上传限速 100 KB/s
BT_DOWNLOAD_RATE_LIMIT = 0           # 下载限速, 0=无限制
BT_METADATA_TIMEOUT = 300            # 元数据解析超时(秒)
BT_POLL_INTERVAL = 500               # BT状态轮询间隔(毫秒)
BT_DHT_STATE_FILE = str(Path(__file__).parent / "data" / "dht_state.dat")
MAGNET_TEMP_DIR = str(Path(__file__).parent / "temp" / "magnets")

# 确保必要目录存在
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
os.makedirs(MAGNET_TEMP_DIR, exist_ok=True)
