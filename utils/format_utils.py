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
    half = (max_len - 3) // 2
    if len(directory) > half:
        directory = directory[:half] + '...' + directory[-half:]
    return os.path.join(directory, filename)


def restyle(widget) -> None:
    """统一重刷 widget 样式，替代项目中重复的 unpolish/polish 调用"""
    s = widget.style()
    if s is not None:
        s.unpolish(widget)
        s.polish(widget)



def safe_open_file(file_path: str) -> bool:
    """安全打开文件/文件夹：校验路径存在且无注入风险后调用系统关联程序"""
    if not file_path or not isinstance(file_path, str):
        return False
    if not os.path.exists(file_path):
        return False
    # 阻止包含 shell 元字符的可疑路径
    dangerous = {'&&', '||', '|', ';', '$', '`', '>', '<', '&'}
    if any(c in file_path for c in dangerous):
        return False
    try:
        os.startfile(file_path)
        return True
    except Exception:
        return False


def safe_open_folder(file_path: str) -> bool:
    """安全打开文件所在文件夹"""
    if not file_path or not os.path.exists(file_path):
        return False
    dangerous = {'&&', '||', '|', ';', '$', '`', '>', '<', '&'}
    if any(c in file_path for c in dangerous):
        return False
    try:
        import subprocess
        # ponytail: 使用 list 参数避免 shell 解析，同时保持双引号不会破坏命令
        subprocess.Popen(['explorer', '/select,', os.path.normpath(file_path)], shell=False)
        return True
    except Exception:
        return False
