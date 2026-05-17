# -*- coding: utf-8 -*-
"""格式化工具模块 - 速度、文件大小、时间的格式化显示"""

import os


def format_size(size_bytes: int) -> str:
    """将字节数格式化为可读的文件大小字符串"""
    if size_bytes < 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    size = float(size_bytes)
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    if unit_index == 0:
        return f"{int(size)} B"
    return f"{size:.1f} {units[unit_index]}"


def format_speed(bytes_per_sec: float) -> str:
    """将每秒字节数格式化为下载速度字符串"""
    if bytes_per_sec <= 0:
        return "0 B/s"
    return f"{format_size(int(bytes_per_sec))}/s"


def format_time(seconds: float) -> str:
    """将秒数格式化为 HH:MM:SS 或 MM:SS 时间字符串"""
    if seconds < 0 or seconds == float('inf'):
        return "--:--"
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_time_ms(milliseconds: int) -> str:
    """将毫秒数格式化为 HH:MM:SS 或 MM:SS 时间字符串"""
    return format_time(milliseconds / 1000)


def ensure_long_path(path: str) -> str:
    """Windows 长路径兼容：超过 248 字符时加 \\\\?\\ 前缀"""
    if os.name != 'nt':
        return path
    if len(path) > 248 and not path.startswith('\\\\?\\'):
        # 转为绝对路径再加前缀
        abs_path = os.path.abspath(path)
        return '\\\\?\\' + abs_path
    return path


def shorten_path(path: str, max_len: int = 200) -> str:
    """截断过长的路径，保留文件名"""
    if len(path) <= max_len:
        return path
    directory = os.path.dirname(path)
    filename = os.path.basename(path)
    # 保留文件名的前 max_len//4 和后 max_len//4 字符
    half = (max_len - 3) // 2
    if len(directory) > half:
        directory = directory[:half] + '...' + directory[-half:]
    return os.path.join(directory, filename)
