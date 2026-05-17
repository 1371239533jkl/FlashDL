# -*- coding: utf-8 -*-
"""
PyInstaller 运行时钩子 - 在所有其他模块加载前初始化 libtorrent
"""
import sys
import os

# 在任何其他模块加载前，先尝试加载 libtorrent
# 这样可以确保 libtorrent 的 DLL 先于 PyQt6 加载
try:
    import libtorrent
    print('[Runtime Hook] libtorrent loaded successfully')
except ImportError:
    print('[Runtime Hook] libtorrent not available')
except Exception as e:
    print(f'[Runtime Hook] libtorrent load error: {e}')
