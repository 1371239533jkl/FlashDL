# -*- coding: utf-8 -*-
"""数据库模块 - SQLite历史记录管理"""

import sqlite3
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
