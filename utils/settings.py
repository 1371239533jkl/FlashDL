# -*- coding: utf-8 -*-
"""设置持久化管理 - 保存用户偏好设置到 JSON 文件"""

import json
import os
import sys
from pathlib import Path

_SETTINGS_FILE = str(Path(__file__).parent.parent / "data" / "settings.json")

# 默认设置
_DEFAULT_SETTINGS = {
    # 主题
    'theme': 'dark',
    # 下载
    'download_dir': '',
    'thread_count': 4,
}

_cache = None  # 缓存已加载的设置


def _load() -> dict:
    """从文件加载设置"""
    global _cache
    if _cache is not None:
        return _cache
    try:
        if os.path.exists(_SETTINGS_FILE):
            with open(_SETTINGS_FILE, 'r', encoding='utf-8') as f:
                _cache = json.load(f)
        else:
            _cache = {}
    except Exception:
        _cache = {}
        print(f'[错误] 设置文件加载失败: {_SETTINGS_FILE}', file=sys.stderr)
    return _cache


def _save(data: dict):
    """保存设置到文件"""
    global _cache
    _cache = data
    try:
        os.makedirs(os.path.dirname(_SETTINGS_FILE), exist_ok=True)
        with open(_SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        print(f'[错误] 设置文件保存失败: {_SETTINGS_FILE}', file=sys.stderr)


def get(key: str, default=None):
    """获取设置值，不存在时返回默认值"""
    data = _load()
    if key in data:
        return data[key]
    return _DEFAULT_SETTINGS.get(key, default)


def set_value(key: str, value):
    """设置并保存"""
    data = _load()
    data[key] = value
    _save(data)
