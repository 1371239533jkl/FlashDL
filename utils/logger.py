# -*- coding: utf-8 -*-
"""统一日志模块 - 分级日志输出到文件和控制台"""

import logging
import os
import sys
from pathlib import Path

# 日志文件路径
_LOG_DIR = Path(__file__).parent.parent / 'data'
_LOG_FILE = _LOG_DIR / 'app.log'


def _setup_logger() -> logging.Logger:
    """初始化全局 logger"""
    os.makedirs(_LOG_DIR, exist_ok=True)

    logger = logging.getLogger('FlashDL')
    logger.setLevel(logging.DEBUG)

    # 避免重复添加 handler（模块被多次导入时）
    if logger.handlers:
        return logger

    # 文件 handler（DEBUG 及以上）
    fh = logging.FileHandler(str(_LOG_FILE), encoding='utf-8', mode='a')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)-7s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    logger.addHandler(fh)

    # 控制台 handler（INFO 及以上，仅在开发模式输出）
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.WARNING)
    ch.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
    logger.addHandler(ch)

    return logger


# 全局 logger 实例
logger = _setup_logger()


def get_logger(name: str = '') -> logging.Logger:
    """获取子 logger（如 'FlashDL.download'）"""
    if name:
        return logging.getLogger(f'FlashDL.{name}')
    return logger
