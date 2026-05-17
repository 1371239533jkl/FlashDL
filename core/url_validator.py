# -*- coding: utf-8 -*-
"""URL验证模块 - 验证下载链接有效性并获取文件信息，支持 HTTP/HTTPS 和磁力链接"""

import re
import requests
from urllib.parse import urlparse, unquote, parse_qs
from pathlib import PurePosixPath

import config


def validate_url(url: str, headers: dict = None) -> dict:
    """
    验证URL并获取文件信息。自动路由到对应协议的验证逻辑。

    返回字典:
        valid: bool - URL是否有效
        file_name: str - 文件名
        file_size: int - 文件大小(字节), -1表示未知
        supports_range: bool - 是否支持Range请求
        content_type: str - 内容类型
        is_magnet: bool - 是否为磁力链接
        error: str - 错误信息(仅在valid=False时)
    """
    url = url.strip()
    if url.startswith('magnet:'):
        return _validate_magnet_url(url)
    else:
        return _validate_http_url(url, headers or {})


def _validate_http_url(url: str, custom_headers: dict = None) -> dict:
    """验证 HTTP/HTTPS 链接并获取文件信息"""
    result = {
        'valid': False,
        'file_name': '',
        'file_size': -1,
        'supports_range': False,
        'content_type': '',
        'is_magnet': False,
        'error': ''
    }

    # 基本URL格式检查
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            result['error'] = '不支持的协议，仅支持 HTTP/HTTPS 和磁力链接'
            return result
        if not parsed.netloc:
            result['error'] = 'URL 格式不正确'
            return result
    except Exception:
        result['error'] = 'URL 格式不正确'
        return result

    custom_headers = custom_headers or {}
    # 发送HEAD请求获取文件信息
    try:
        headers = {
            'User-Agent': custom_headers.get('User-Agent',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        }
        # 传入自定义 Referer 用于 CDN 防盗链验证
        if custom_headers.get('Referer'):
            headers['Referer'] = custom_headers['Referer']

        resp = requests.head(
            url, headers=headers, allow_redirects=True,
            timeout=(config.CONNECT_TIMEOUT, config.READ_TIMEOUT),
            verify=False  # 兼容CDN证书不匹配
        )
        resp.raise_for_status()
        _parse_response(result, resp, url)
        return result

    except requests.HTTPError as e:
        # 某些 CDN/服务器不支持 HEAD(如返回405)，回退到 GET+stream
        if e.response.status_code in (403, 405, 400):
            try:
                headers['Range'] = 'bytes=0-0'
                get_resp = requests.get(
                    url, headers=headers, stream=True,
                    timeout=(config.CONNECT_TIMEOUT, config.READ_TIMEOUT),
                    verify=False
                )
                if get_resp.status_code in (200, 206, 301, 302, 307, 308):
                    try:
                        next(get_resp.iter_content(1))
                    except (StopIteration, requests.RequestException):
                        pass
                    _parse_response(result, get_resp, url)
                    get_resp.close()
                    return result
                get_resp.close()
            except Exception:
                pass
        result['error'] = f'HTTP 错误: {e.response.status_code}'
        return result

    except requests.ConnectionError:
        result['error'] = '无法连接到服务器'
        return result
    except requests.Timeout:
        result['error'] = '连接超时'
        return result
    except Exception as e:
        result['error'] = f'请求失败: {str(e)}'
        return result


def _validate_magnet_url(url: str) -> dict:
    """验证磁力链接格式并提取基本信息"""
    result = {
        'valid': False,
        'file_name': '',
        'file_size': -1,
        'supports_range': False,
        'content_type': 'application/x-bittorrent',
        'is_magnet': True,
        'error': ''
    }

    if not url.startswith('magnet:?'):
        result['error'] = '磁力链接格式错误，应以 magnet:? 开头'
        return result

    match = re.search(r'xt=urn:btih:([a-fA-F0-9]{40})', url)
    if not match:
        match = re.search(r'xt=urn:btih:([A-Za-z2-7]{32})', url)
    if not match:
        result['error'] = '磁力链接中未找到有效的 infohash'
        return result

    infohash = match.group(1)
    try:
        params = parse_qs(url.split('?', 1)[1])
        dn_list = params.get('dn', [])
        if dn_list:
            result['file_name'] = unquote(dn_list[0])
        else:
            result['file_name'] = f'magnet_{infohash[:8]}'
    except Exception:
        result['file_name'] = f'magnet_{infohash[:8]}'

    result['valid'] = True
    return result


def _extract_filename(response: requests.Response, url: str) -> str:
    """从响应头或URL中提取文件名"""
    cd = response.headers.get('Content-Disposition', '')
    if 'filename=' in cd:
        parts = cd.split('filename=')
        if len(parts) > 1:
            name = parts[1].strip().strip('"').strip("'")
            if name:
                return name
    parsed = urlparse(response.url or url)
    path = PurePosixPath(unquote(parsed.path))
    if path.name:
        return path.name
    return 'download'


def _parse_response(result: dict, resp: requests.Response, url: str):
    """从 HTTP 响应中解析文件名、大小、Range 支持等信息"""
    file_name = _extract_filename(resp, url)
    result['file_name'] = file_name
    content_length = resp.headers.get('Content-Length')
    if content_length:
        try:
            result['file_size'] = int(content_length)
        except ValueError:
            pass
    accept_ranges = resp.headers.get('Accept-Ranges', '').lower()
    result['supports_range'] = accept_ranges == 'bytes'
    result['content_type'] = resp.headers.get('Content-Type', '')
    result['valid'] = True
