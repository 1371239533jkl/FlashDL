# -*- coding: utf-8 -*-
"""字幕管理模块 - 使用 pysubs2 加载字幕，提供同步查找和自动检测"""

import os
from bisect import bisect_right
from dataclasses import dataclass

import pysubs2

import config


@dataclass
class SubtitleItem:
    """字幕条目"""
    start_ms: int
    end_ms: int
    text: str


class SubtitleManager:
    """字幕管理器：加载、查找、自动检测"""

    def __init__(self):
        self._items: list[SubtitleItem] = []
        self._starts: list[int] = []  # 用于二分查找的 start_ms 列表
        self._current_index: int = -1
        self.enabled: bool = True
        self._loaded_path: str = ''
        self._offset: int = 0  # 字幕时间偏移量(毫秒)，正数=字幕提前，负数=字幕延后

    @property
    def offset(self) -> int:
        """当前字幕偏移量(毫秒)"""
        return self._offset

    @offset.setter
    def offset(self, value: int):
        """设置字幕偏移量(毫秒)"""
        self._offset = max(-300000, min(300000, value))  # 限制 ±5 分钟
        # 偏移改变时重置索引，强制下次重新查找
        self._current_index = -1

    @property
    def is_loaded(self) -> bool:
        return len(self._items) > 0

    def load_subtitle(self, file_path: str) -> bool:
        """加载字幕文件，返回是否成功（自动尝试多种编码）"""
        self.clear()
        # 尝试多种编码，很多字幕文件是 UTF-16 或 GBK 编码
        encodings = ['utf-8', 'utf-8-sig', 'utf-16', 'gbk', 'gb2312', 'gb18030']
        last_error = ''
        for enc in encodings:
            try:
                subs = pysubs2.load(file_path, encoding=enc)
                for event in subs.events:
                    if event.is_comment:
                        continue
                    text = event.plaintext.strip()
                    if text:
                        self._items.append(SubtitleItem(
                            start_ms=event.start,
                            end_ms=event.end,
                            text=text
                        ))
                # 按 start_ms 排序
                self._items.sort(key=lambda x: x.start_ms)
                self._starts = [item.start_ms for item in self._items]
                self._loaded_path = file_path
                return len(self._items) > 0
            except Exception as e:
                last_error = str(e)
                continue

        # 所有编码都失败了
        self.clear()
        return False

    def get_subtitle_at(self, position_ms: int) -> SubtitleItem | None:
        """根据播放位置查找当前字幕（已考虑偏移量），返回 SubtitleItem 或 None"""
        if not self._items or not self.enabled:
            return None

        # 偏移量修正：用户说"字幕快了"就把字幕往后推(offset负值=字幕延后显示)
        # 所以查找时 position_ms 减去 offset
        adjusted_pos = position_ms - self._offset

        # 快速路径：检查当前索引是否仍然有效
        if 0 <= self._current_index < len(self._items):
            current = self._items[self._current_index]
            if current.start_ms <= adjusted_pos <= current.end_ms:
                return current

        # 邻近搜索（±3 范围），适用于正常播放
        start = max(0, self._current_index - 3)
        end = min(len(self._items), self._current_index + 4)
        for i in range(start, end):
            item = self._items[i]
            if item.start_ms <= adjusted_pos <= item.end_ms:
                self._current_index = i
                return item

        # 二分查找（快进/快退/拖拽时）
        idx = bisect_right(self._starts, adjusted_pos) - 1
        if 0 <= idx < len(self._items):
            item = self._items[idx]
            if item.start_ms <= adjusted_pos <= item.end_ms:
                self._current_index = idx
                return item

        # 没有匹配的字幕（字幕间隙）
        self._current_index = max(0, idx)
        return None

    def auto_detect_subtitle(self, video_path: str) -> str | None:
        """自动检测同目录下的同名字幕文件，返回路径或 None"""
        if not video_path:
            return None
        base = os.path.splitext(video_path)[0]
        # 检查多种后缀变体
        suffixes = ['', '.zh', '.chs', '.chi', '.cn', '.sc']
        for suffix in suffixes:
            for ext in config.SUBTITLE_EXTENSIONS:
                candidate = f'{base}{suffix}{ext}'
                if os.path.isfile(candidate):
                    return candidate
        return None

    def toggle_enabled(self) -> bool:
        """切换字幕开关，返回新状态"""
        self.enabled = not self.enabled
        return self.enabled

    def clear(self):
        """清空字幕数据"""
        self._items.clear()
        self._starts.clear()
        self._current_index = -1
        self._loaded_path = ''
