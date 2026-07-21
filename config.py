# -*- coding: utf-8 -*-
"""全局配置模块"""

import os
from pathlib import Path

# 应用信息
APP_NAME = "FlashDL - 视频下载 & 播放工具"
APP_VERSION = "2.2"
URL_HISTORY_MAX = 20  # URL 输入历史最大条数

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
# ponytail: 运行时使用 get_speed_limit() / set_speed_limit()，不要直接修改此变量
DOWNLOAD_SPEED_LIMIT = 0


class _SpeedLimit:
    """线程安全的全局限速值封装"""
    import threading
    _lock = threading.Lock()
    _value = 0

    @classmethod
    def get(cls) -> int:
        with cls._lock:
            return cls._value

    @classmethod
    def set(cls, value: int):
        with cls._lock:
            cls._value = value


def get_speed_limit() -> int:
    """获取当前全局 HTTP 下载限速（bytes/s），0=无限制"""
    return _SpeedLimit.get()


def set_speed_limit(value: int):
    """设置全局 HTTP 下载限速（bytes/s），0=无限制"""
    _SpeedLimit.set(value)


# 启动时从环境变量同步一次初始值（兼容旧的直接读取）
if DOWNLOAD_SPEED_LIMIT:
    _SpeedLimit.set(DOWNLOAD_SPEED_LIMIT)

# 路径配置
DEFAULT_DOWNLOAD_DIR = str(Path.home() / "Downloads")
TEMP_DIR = str(Path(__file__).parent / "temp" / "downloads")
DB_PATH = str(Path(__file__).parent / "data" / "history.db")

# UI配置
WINDOW_WIDTH = 1160
WINDOW_HEIGHT = 740
MIN_WINDOW_WIDTH = 900
MIN_WINDOW_HEIGHT = 600
TITLE_BAR_HEIGHT = 44
SIDEBAR_WIDTH = 48
TAB_BAR_HEIGHT = 36
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

# 代理配置
PROXY_ENABLED = False               # 是否启用代理
PROXY_TYPE = 'http'                 # http / socks5
PROXY_HOST = '127.0.0.1'            # 代理地址
PROXY_PORT = 1080                   # 代理端口
PROXY_USERNAME = ''                 # 代理用户名（可选）
PROXY_PASSWORD = ''                 # 代理密码（可选）

# SSL 配置
# 默认开启 TLS 证书验证；仅在明确关闭（如环境变量 FLASHDL_SSL_VERIFY=false）时才跳过。
# 如有域名需要跳过证书校验，请加入 SSL_INSECURE_DOMAINS 白名单。
SSL_VERIFY = os.environ.get('FLASHDL_SSL_VERIFY', 'true').lower() != 'false'
SSL_INSECURE_DOMAINS = set()


def should_verify_cert(url: str) -> bool:
    """根据 URL 决定是否验证 TLS 证书（默认开启，仅白名单域名跳过）"""
    if SSL_VERIFY:
        return True
    from urllib.parse import urlparse
    try:
        domain = urlparse(url).hostname or ''
        return domain not in SSL_INSECURE_DOMAINS
    except Exception:
        return True


def get_requests_proxy() -> dict | None:
    """返回 requests 库用的 proxies 字典，未启用时返回 None"""
    if not PROXY_ENABLED:
        return None
    scheme = 'socks5' if PROXY_TYPE == 'socks5' else 'http'
    if PROXY_USERNAME and PROXY_PASSWORD:
        url = f'{scheme}://{PROXY_USERNAME}:{PROXY_PASSWORD}@{PROXY_HOST}:{PROXY_PORT}'
    else:
        url = f'{scheme}://{PROXY_HOST}:{PROXY_PORT}'
    return {'http': url, 'https': url}


def get_lt_proxy() -> tuple:
    """返回 libtorrent 代理设置 (type, host, port, user, pass)，未启用时返回 (0,'',0,'','')"""
    if not PROXY_ENABLED:
        return (0, '', 0, '', '')
    type_map = {'http': 4, 'socks5': 2}
    if PROXY_USERNAME and PROXY_PASSWORD:
        lt_type = type_map.get(PROXY_TYPE, 4) + 1  # 带认证 +1
    else:
        lt_type = type_map.get(PROXY_TYPE, 4)
    return (lt_type, PROXY_HOST, PROXY_PORT, PROXY_USERNAME, PROXY_PASSWORD)


# 确保必要目录存在
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
os.makedirs(MAGNET_TEMP_DIR, exist_ok=True)
