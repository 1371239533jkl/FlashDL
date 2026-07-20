# -*- coding: utf-8 -*-
"""数据库模块 - SQLite历史记录管理"""

import sqlite3
import csv
import os
from typing import Optional

import config


class Database:
    """SQLite数据库管理，存储下载历史记录"""

    def __init__(self, db_path: str = config.DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with self._connect() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS download_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT UNIQUE NOT NULL,
                    url TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    save_path TEXT NOT NULL,
                    file_size INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'completed',
                    created_time TEXT NOT NULL,
                    completed_time TEXT
                )
            ''')

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA journal_mode=WAL')  # 读写并发性能提升
        return conn

    def add_record(self, task_id: str, url: str, file_name: str,
                   save_path: str, file_size: int, status: str,
                   created_time: str, completed_time: str = ''):
        """添加一条下载历史记录"""
        with self._connect() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO download_history
                (task_id, url, file_name, save_path, file_size, status, created_time, completed_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (task_id, url, file_name, save_path, file_size, status,
                  created_time, completed_time))

    def get_all_records(self) -> list[dict]:
        """获取所有历史记录，按时间倒序"""
        with self._connect() as conn:
            rows = conn.execute(
                'SELECT * FROM download_history ORDER BY id DESC'
            ).fetchall()
            return [dict(row) for row in rows]

    def search_records(self, keyword: str) -> list[dict]:
        """按文件名搜索历史记录"""
        with self._connect() as conn:
            rows = conn.execute(
                'SELECT * FROM download_history WHERE file_name LIKE ? ORDER BY id DESC',
                (f'%{keyword}%',)
            ).fetchall()
            return [dict(row) for row in rows]

    def get_records_by_status(self, status: str, keyword: str = '') -> list[dict]:
        """按状态过滤历史记录，可选关键字搜索"""
        with self._connect() as conn:
            if keyword:
                rows = conn.execute(
                    'SELECT * FROM download_history WHERE status = ? AND file_name LIKE ? ORDER BY id DESC',
                    (status, f'%{keyword}%')
                ).fetchall()
            else:
                rows = conn.execute(
                    'SELECT * FROM download_history WHERE status = ? ORDER BY id DESC',
                    (status,)
                ).fetchall()
            return [dict(row) for row in rows]

    def delete_record(self, task_id: str):
        """删除一条历史记录"""
        with self._connect() as conn:
            conn.execute('DELETE FROM download_history WHERE task_id = ?', (task_id,))

    def clear_all(self):
        """清空所有历史记录"""
        with self._connect() as conn:
            conn.execute('DELETE FROM download_history')

    def get_record(self, task_id: str) -> Optional[dict]:
        """获取单条历史记录"""
        with self._connect() as conn:
            row = conn.execute(
                'SELECT * FROM download_history WHERE task_id = ?', (task_id,)
            ).fetchone()
            return dict(row) if row else None

    # ═══ 分页查询 ═══

    def get_records_page(self, page: int, page_size: int = 50) -> tuple[list[dict], int]:
        """分页获取所有历史记录，返回 (records, total_count)"""
        with self._connect() as conn:
            total = conn.execute('SELECT COUNT(*) FROM download_history').fetchone()[0]
            rows = conn.execute(
                'SELECT * FROM download_history ORDER BY id DESC LIMIT ? OFFSET ?',
                (page_size, page * page_size)
            ).fetchall()
            return [dict(row) for row in rows], total

    def search_records_page(self, keyword: str, page: int, page_size: int = 50) -> tuple[list[dict], int]:
        """分页搜索历史记录"""
        with self._connect() as conn:
            total = conn.execute(
                'SELECT COUNT(*) FROM download_history WHERE file_name LIKE ?',
                (f'%{keyword}%',)
            ).fetchone()[0]
            rows = conn.execute(
                'SELECT * FROM download_history WHERE file_name LIKE ? ORDER BY id DESC LIMIT ? OFFSET ?',
                (f'%{keyword}%', page_size, page * page_size)
            ).fetchall()
            return [dict(row) for row in rows], total

    def get_records_by_status_page(self, status: str, page: int,
                                    page_size: int = 50, keyword: str = '') -> tuple[list[dict], int]:
        """分页按状态过滤历史记录"""
        with self._connect() as conn:
            if keyword:
                total = conn.execute(
                    'SELECT COUNT(*) FROM download_history WHERE status = ? AND file_name LIKE ?',
                    (status, f'%{keyword}%')
                ).fetchone()[0]
                rows = conn.execute(
                    'SELECT * FROM download_history WHERE status = ? AND file_name LIKE ? ORDER BY id DESC LIMIT ? OFFSET ?',
                    (status, f'%{keyword}%', page_size, page * page_size)
                ).fetchall()
            else:
                total = conn.execute(
                    'SELECT COUNT(*) FROM download_history WHERE status = ?',
                    (status,)
                ).fetchone()[0]
                rows = conn.execute(
                    'SELECT * FROM download_history WHERE status = ? ORDER BY id DESC LIMIT ? OFFSET ?',
                    (status, page_size, page * page_size)
                ).fetchall()
            return [dict(row) for row in rows], total

    # ═══ 统计查询 ═══

    def get_statistics(self, time_filter: str = 'all') -> dict:
        """获取下载统计：总数、成功数、失败数、累计流量。
        time_filter: 'all' | 'today' | 'week' | 'month'"""
        time_clause = ''
        if time_filter == 'today':
            time_clause = "AND date(created_time) = date('now', 'localtime')"
        elif time_filter == 'week':
            time_clause = "AND date(created_time) >= date('now', '-7 days', 'localtime')"
        elif time_filter == 'month':
            time_clause = "AND date(created_time) >= date('now', '-30 days', 'localtime')"

        with self._connect() as conn:
            total = conn.execute(
                f'SELECT COUNT(*) FROM download_history WHERE 1=1 {time_clause}'
            ).fetchone()[0]
            completed = conn.execute(
                f"SELECT COUNT(*) FROM download_history WHERE status='completed' {time_clause}"
            ).fetchone()[0]
            failed = conn.execute(
                f"SELECT COUNT(*) FROM download_history WHERE status='failed' {time_clause}"
            ).fetchone()[0]
            total_size = conn.execute(
                f"SELECT COALESCE(SUM(file_size), 0) FROM download_history WHERE status='completed' {time_clause}"
            ).fetchone()[0]
            return {
                'total': total,
                'completed': completed,
                'failed': failed,
                'total_size': total_size,
                'success_rate': round(completed / total * 100, 1) if total > 0 else 0.0,
            }

    # ═══ 导出 ═══

    def export_csv(self, file_path: str) -> int:
        """导出所有历史记录到 CSV 文件，返回导出条数"""
        records = self.get_all_records()
        with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['文件名', 'URL', '保存路径', '文件大小(字节)', '状态', '创建时间', '完成时间'])
            for r in records:
                writer.writerow([
                    r.get('file_name', ''),
                    r.get('url', ''),
                    r.get('save_path', ''),
                    r.get('file_size', 0),
                    r.get('status', ''),
                    r.get('created_time', ''),
                    r.get('completed_time', ''),
                ])
        return len(records)
