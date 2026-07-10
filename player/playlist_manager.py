# -*- coding: utf-8 -*-
"""播放列表管理 - 支持持久化"""

import json
import os
from typing import Optional

import config


class PlaylistManager:
    """管理视频播放列表，自动持久化到文件"""

    PLAYLIST_FILE = os.path.join(os.path.dirname(config.DB_PATH), 'playlist.json')

    def __init__(self):
        self._items: list[str] = []   # 文件路径列表
        self._current_index: int = -1

    @property
    def items(self) -> list[str]:
        return list(self._items)

    @property
    def current_index(self) -> int:
        return self._current_index

    @property
    def current_file(self) -> Optional[str]:
        if 0 <= self._current_index < len(self._items):
            return self._items[self._current_index]
        return None

    @property
    def count(self) -> int:
        return len(self._items)

    def add_file(self, file_path: str) -> bool:
        """添加文件到播放列表"""
        if not os.path.exists(file_path):
            return False
        if file_path not in self._items:
            self._items.append(file_path)
        return True

    def add_files(self, file_paths: list[str]):
        for f in file_paths:
            self.add_file(f)

    def remove_file(self, index: int):
        if 0 <= index < len(self._items):
            self._items.pop(index)
            if index <= self._current_index:
                self._current_index = max(-1, self._current_index - 1)

    def move_file(self, from_index: int, to_index: int):
        """移动文件位置（拖拽排序）"""
        if 0 <= from_index < len(self._items) and 0 <= to_index < len(self._items):
            item = self._items.pop(from_index)
            self._items.insert(to_index, item)
            if self._current_index == from_index:
                self._current_index = to_index
            elif from_index < self._current_index <= to_index:
                self._current_index -= 1
            elif to_index <= self._current_index < from_index:
                self._current_index += 1

    def clear(self):
        self._items.clear()
        self._current_index = -1

    def set_current(self, index: int) -> Optional[str]:
        """设置当前播放项，返回文件路径"""
        if 0 <= index < len(self._items):
            self._current_index = index
            return self._items[index]
        return None

    def next(self) -> Optional[str]:
        """获取下一个文件"""
        if self._current_index + 1 < len(self._items):
            self._current_index += 1
            return self._items[self._current_index]
        return None

    def previous(self) -> Optional[str]:
        """获取上一个文件"""
        if self._current_index - 1 >= 0:
            self._current_index -= 1
            return self._items[self._current_index]
        return None

    def has_next(self) -> bool:
        return self._current_index + 1 < len(self._items)

    def has_previous(self) -> bool:
        return self._current_index - 1 >= 0

    def save(self):
        """保存播放列表到文件"""
        try:
            data = {'items': self._items[:20], 'current_index': self._current_index}
            os.makedirs(os.path.dirname(self.PLAYLIST_FILE), exist_ok=True)
            with open(self.PLAYLIST_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
        except (OSError, json.JSONDecodeError):
            pass

    def load(self):
        """从文件恢复播放列表"""
        try:
            if not os.path.exists(self.PLAYLIST_FILE):
                return
            with open(self.PLAYLIST_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            items = data.get('items', [])
            video_extensions = {'.mp4','.mkv','.avi','.mov','.wmv','.flv','.webm','.m4v'}
            self._items = [
                p for p in items
                if os.path.exists(p) and os.path.splitext(p)[1].lower() in video_extensions
            ]
            idx = data.get('current_index', -1)
            self._current_index = idx if 0 <= idx < len(self._items) else -1
        except (OSError, json.JSONDecodeError, ValueError):
            pass
