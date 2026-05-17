# -*- coding: utf-8 -*-
"""libtorrent 全局会话管理器 - 单例模式管理BT下载会话"""

import os
import sys

import config

# libtorrent 延迟导入（避免打包后 DLL 加载顺序问题）
lt = None
LIBTORRENT_AVAILABLE = None  # None 表示尚未检测


def _ensure_libtorrent_loaded():
    """确保 libtorrent 已加载（仅在需要时加载）"""
    global lt, LIBTORRENT_AVAILABLE
    if LIBTORRENT_AVAILABLE is not None:
        return
    try:
        import libtorrent as _lt
        lt = _lt
        LIBTORRENT_AVAILABLE = True
    except ImportError:
        lt = None
        LIBTORRENT_AVAILABLE = False


def is_libtorrent_available() -> bool:
    """检测 libtorrent 是否可用"""
    _ensure_libtorrent_loaded()
    return LIBTORRENT_AVAILABLE


class MagnetSessionManager:
    """libtorrent 会话管理器(单例)，所有磁力下载任务共享同一个session"""

    _instance = None

    @classmethod
    def get_instance(cls) -> 'MagnetSessionManager':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        if MagnetSessionManager._instance is not None:
            raise RuntimeError('请使用 MagnetSessionManager.get_instance()')
        self.session = None
        self._initialized = False

    @property
    def initialized(self) -> bool:
        return self._initialized

    def initialize(self):
        """初始化 libtorrent session"""
        if self._initialized or not LIBTORRENT_AVAILABLE:
            return

        self.session = lt.session()

        # 加速设置
        settings = {
            'listen_interfaces': f'0.0.0.0:{config.BT_LISTEN_PORT}',
            'enable_dht': True,
            'enable_lsd': True,
            'enable_upnp': True,
            'enable_natpmp': True,
            # 连接数
            'connections_limit': config.BT_MAX_CONNECTIONS,
            # 带宽限制（初始低上传，下载完成后在 task 侧调高）
            'download_rate_limit': config.BT_DOWNLOAD_RATE_LIMIT,
            'upload_rate_limit': config.BT_UPLOAD_RATE_LIMIT,
            'announce_to_all_tiers': True,
            'announce_to_all_trackers': True,
        }
        self.session.apply_settings(settings)

        # 启用扩展协议（逐一带 try 兼容旧版 libtorrent）
        for ext in [lt.create_ut_metadata_plugin, lt.create_ut_pex_plugin, lt.create_smart_ban_plugin]:
            try:
                self.session.add_extension(ext)
            except Exception:
                pass

        # 加载 DHT 状态(加速元数据解析)
        self._load_dht_state()

        # 添加 DHT 引导节点
        self.session.add_dht_router('router.bittorrent.com', 6881)
        self.session.add_dht_router('router.utorrent.com', 6881)
        self.session.add_dht_router('dht.transmissionbt.com', 6881)
        self.session.add_dht_router('dht.libtorrent.org', 25401)
        self.session.add_dht_router('router.bitcomet.com', 6881)
        self.session.add_dht_router('dht.aelitis.com', 6881)

        self._initialized = True

    def shutdown(self):
        """关闭 session，释放所有资源"""
        if not self._initialized or self.session is None:
            return
        self._save_dht_state()
        # 移除所有 torrent 释放端口和连接
        try:
            handles = self.session.get_torrents()
            for h in handles:
                self.session.remove_torrent(h)
        except Exception as e:
            print(f'[警告] 移除 torrent 时出错: {e}', file=sys.stderr)
        self.session = None
        self._initialized = False

    def add_magnet(self, magnet_uri: str, save_path: str):
        """添加磁力链接，返回 torrent_handle"""
        if not self._initialized:
            self.initialize()

        params = lt.parse_magnet_uri(magnet_uri)
        params.save_path = save_path
        # 添加公共 tracker 提高连接成功率（2026年最新活跃tracker）
        public_trackers = [
            # UDP (速度快，优先)
            'udp://tracker.opentrackr.org:1337/announce',
            'udp://open.stealth.si:80/announce',
            'udp://tracker.torrent.eu.org:451/announce',
            'udp://tracker.moeking.me:6969/announce',
            'udp://tracker.theoks.net:6969/announce',
            'udp://tracker.bittor.pw:1337/announce',
            'udp://explodie.org:6969/announce',
            'udp://open.demonii.com:1337/announce',
            'udp://tracker.qu.ax:6969/announce',
            'udp://tracker.srv00.com:6969/announce',
            'udp://tracker.opentorrent.top:6969/announce',
            'udp://tracker.0x.tf:6969/announce',
            # HTTPS (可靠性高)
            'https://tracker.tamersunion.org:443/announce',
            'https://tracker.gbitt.info:443/announce',
            'https://tracker.zhuqiy.com:443/announce',
            'https://tracker.moeking.me:443/announce',
            'https://tracker.bt4g.com:443/announce',
            'https://tr.nyacat.pw:443/announce',
            # HTTP (备用)
            'http://tracker.opentrackr.org:1337/announce',
            'http://tracker.bt4g.com:2095/announce',
            'http://tracker.renfei.net:8080/announce',
            'http://tracker.dler.org:6969/announce',
            'http://tracker.files.fm:6969/announce',
        ]
        for tr in public_trackers:
            params.trackers.append(tr)
        handle = self.session.add_torrent(params)
        return handle

    def add_torrent_from_resume(self, resume_data: bytes, save_path: str):
        """从 resume_data 恢复 torrent，返回 torrent_handle"""
        if not self._initialized:
            self.initialize()

        params = lt.read_resume_data(resume_data)
        params.save_path = save_path
        handle = self.session.add_torrent(params)
        return handle

    def remove_torrent(self, handle, delete_files: bool = False):
        """移除 torrent"""
        if self.session is None:
            return
        try:
            option = lt.options_t.delete_files if delete_files else 0
            self.session.remove_torrent(handle, option)
        except Exception as e:
            print(f'[警告] 移除 torrent 失败: {e}', file=sys.stderr)

    def get_resume_data(self, handle) -> bytes:
        """获取 torrent 的 resume_data（超时200ms，仅暂停时调用）"""
        if not handle.is_valid():
            return b''
        handle.save_resume_data(lt.save_resume_flags_t.flush_disk_cache)
        import time
        deadline = time.time() + 0.2  # 最多等200ms，超时直接返回
        while time.time() < deadline:
            alerts = self.session.pop_alerts()
            for alert in alerts:
                if isinstance(alert, lt.save_resume_data_alert):
                    return lt.write_resume_data_buf(alert.params)
                if isinstance(alert, lt.save_resume_data_failed_alert):
                    return b''
            time.sleep(0.02)  # 20ms 轮询间隔
        return b''

    def _save_dht_state(self):
        """保存 DHT 路由表状态到文件"""
        if self.session is None:
            return
        try:
            state = self.session.save_state(lt.save_state_flags_t.save_dht_state)
            state_bytes = lt.bencode(state)
            os.makedirs(os.path.dirname(config.BT_DHT_STATE_FILE), exist_ok=True)
            with open(config.BT_DHT_STATE_FILE, 'wb') as f:
                f.write(state_bytes)
        except Exception as e:
            print(f'[警告] DHT 状态保存失败: {e}', file=sys.stderr)

    def _load_dht_state(self):
        """从文件恢复 DHT 路由表状态"""
        if self.session is None:
            return
        if not os.path.exists(config.BT_DHT_STATE_FILE):
            return
        try:
            with open(config.BT_DHT_STATE_FILE, 'rb') as f:
                state_bytes = f.read()
            state = lt.bdecode(state_bytes)
            self.session.load_state(state)
        except Exception as e:
            print(f'[警告] DHT 状态加载失败: {e}', file=sys.stderr)
