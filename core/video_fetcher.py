# -*- coding: utf-8 -*-
"""网页视频嗅探模块 - 基于 yt-dlp 解析各类网站的视频直链"""

import sys
import re
from typing import Optional

YTDLP_AVAILABLE = False
try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    pass


# 常见视频网站域名匹配
_KNOWN_SITES = re.compile(r'https?://([a-z0-9-]+\.)*(' + '|'.join([
    'youtube\.com', 'youtu\.be',
    'bilibili\.com', 'b23\.tv',
    'v\.qq\.com',
    'douyin\.com', 'iesdouyin\.com',
    'kuaishou\.com',
    'weibo\.(com|cn)',
    'ixigua\.com',
    'huya\.com', 'douyu\.com',
    'twitch\.tv',
    'tiktok\.com',
    'twitter\.com', 'x\.com',
    'instagram\.com',
    'facebook\.com', 'fb\.watch',
    'reddit\.com',
    'pornhub\.com',
    'xvideos\.com',
]) + r')', re.IGNORECASE)


def is_fetchable_url(url: str) -> bool:
    """判断链接是否可用 yt-dlp 解析"""
    if not YTDLP_AVAILABLE:
        return False
    url = url.strip()
    # 更宽松的检测：检查是否包含任意已知域名即可
    domains = [
        'youtube.com', 'youtu.be',
        'bilibili.com', 'b23.tv',
        'v.qq.com',
        'douyin.com', 'iesdouyin.com',
        'kuaishou.com',
        'weibo.com', 'weibo.cn',
        'ixigua.com',
        'huya.com', 'douyu.com',
        'twitch.tv', 'tiktok.com',
        'twitter.com', 'x.com',
        'instagram.com',
        'facebook.com', 'fb.watch',
        'reddit.com',
    ]
    url_lower = url.lower()
    for d in domains:
        if d in url_lower:
            return True
    return False


def extract_video_info(url: str) -> dict:
    """
    解析视频链接，返回视频信息和可用画质列表。
    
    返回格式:
    {
        'success': True/False,
        'error': '错误信息',
        'title': '视频标题',
        'duration': 123,  # 秒
        'thumbnail': '封面URL',
        'formats': [
            {'id': 'xxx', 'ext': 'mp4', 'width': 1920, 'height': 1080,
             'filesize': 12345678, 'url': '直链', 'note': '1080p'},
        ],
        'original_url': '原始URL',
    }
    """
    result = {'success': False, 'formats': [], 'error': ''}
    
    if not YTDLP_AVAILABLE:
        result['error'] = 'yt-dlp 未安装，请执行: pip install yt-dlp'
        return result
    
    url = url.strip()
    if not is_fetchable_url(url):
        result['error'] = '暂不支持解析此网站'
        return result
    
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'skip_download': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                result['error'] = '解析失败，无法获取视频信息'
                return result
            
            result['success'] = True
            result['title'] = info.get('title', '未知标题')
            result['duration'] = info.get('duration', 0)
            result['thumbnail'] = info.get('thumbnail', '')
            result['original_url'] = info.get('webpage_url', url)
            
            # 整理所有可用格式
            formats = info.get('formats', [])
            seen = set()
            for f in formats:
                ext = f.get('ext', '')
                url_direct = f.get('url', '')
                if not url_direct or not ext:
                    continue
                # 只保留视频格式（有height才有视频）
                height = f.get('height', 0)
                if height == 0:
                    continue
                # 避免重复（同分辨率不同编码只保留一个，优先 mp4/h264）
                key = f'{height}p'
                if key in seen:
                    continue
                seen.add(key)
                
                filesize = f.get('filesize') or f.get('filesize_approx') or 0
                result['formats'].append({
                    'id': f.get('format_id', ''),
                    'ext': ext,
                    'width': f.get('width', 0),
                    'height': height,
                    'filesize': filesize,
                    'url': url_direct,
                    'note': f'{height}p' + (f' ({ext})' if ext not in ('mp4', 'webm') else ''),
                })
            
            # 按分辨率从高到低排序
            result['formats'].sort(key=lambda x: x['height'], reverse=True)
            
            if not result['formats']:
                result['error'] = '未找到可下载的视频格式'
                result['success'] = False
                
    except yt_dlp.utils.DownloadError as e:
        result['error'] = f'下载错误: {str(e)[:100]}'
    except yt_dlp.utils.ExtractorError as e:
        result['error'] = f'解析器错误: {str(e)[:100]}'
    except Exception as e:
        result['error'] = f'解析失败: {str(e)[:100]}'
    
    return result


def fetch_title(url: str) -> str:
    """快速获取视频标题（不提取全部格式）"""
    try:
        if not YTDLP_AVAILABLE:
            return ''
        ydl_opts = {'quiet': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info.get('title', '') or ''
    except Exception:
        return ''
