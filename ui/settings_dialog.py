# -*- coding: utf-8 -*-
"""设置对话框 - 集中管理所有用户偏好设置"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QWidget, QLineEdit, QSpinBox, QCheckBox,
    QComboBox, QFileDialog, QFormLayout, QGroupBox, QSlider
)

import config
from utils.settings import get as get_setting, set_value as set_setting


class SettingsDialog(QDialog):
    """应用程序设置对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('设置')
        self.setMinimumSize(750, 800)
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # 标签页
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_download_tab(), '下载')
        self.tabs.addTab(self._create_bt_tab(), 'BT / 磁力')
        self.tabs.addTab(self._create_player_tab(), '播放器')
        self.tabs.addTab(self._create_general_tab(), '通用')
        layout.addWidget(self.tabs)

        # 底部按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_save = QPushButton('保存')
        btn_save.setObjectName('PrimaryBtn')
        btn_save.setFixedWidth(90)
        btn_save.clicked.connect(self._save_and_close)
        btn_row.addWidget(btn_save)

        btn_cancel = QPushButton('取消')
        btn_cancel.setFixedWidth(90)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        layout.addLayout(btn_row)

    # ═══ 下载设置 ═══

    def _create_download_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)

        # 保存路径
        path_group = QGroupBox('保存路径')
        path_layout = QHBoxLayout(path_group)
        self.download_dir = QLineEdit()
        path_layout.addWidget(self.download_dir)
        btn_browse = QPushButton('浏览')
        btn_browse.setFixedWidth(60)
        btn_browse.clicked.connect(self._browse_download_dir)
        path_layout.addWidget(btn_browse)
        layout.addWidget(path_group)

        # 并发与线程
        dl_group = QGroupBox('下载参数')
        form = QFormLayout(dl_group)
        form.setSpacing(10)

        self.max_concurrent = QSpinBox()
        self.max_concurrent.setRange(1, 10)
        form.addRow('最大同时下载数:', self.max_concurrent)

        self.thread_count = QComboBox()
        for i in [1, 2, 4, 8, 16]:
            self.thread_count.addItem(str(i), i)
        form.addRow('默认线程数:', self.thread_count)

        self.speed_limit = QComboBox()
        self.speed_limit.addItem('无限制', 0)
        self.speed_limit.addItem('100 KB/s', 100 * 1024)
        self.speed_limit.addItem('500 KB/s', 500 * 1024)
        self.speed_limit.addItem('1 MB/s', 1024 * 1024)
        self.speed_limit.addItem('2 MB/s', 2 * 1024 * 1024)
        self.speed_limit.addItem('5 MB/s', 5 * 1024 * 1024)
        self.speed_limit.addItem('10 MB/s', 10 * 1024 * 1024)
        form.addRow('全局速度限制:', self.speed_limit)

        self.max_retries = QSpinBox()
        self.max_retries.setRange(0, 10)
        form.addRow('下载重试次数:', self.max_retries)

        layout.addWidget(dl_group)

        # 代理（与下载参数/下载完成后一样用 QFormLayout，不设任何固定宽度）
        proxy_group = QGroupBox('网络代理（HTTP下载 + BT 均生效）')
        proxy_form = QFormLayout(proxy_group)
        proxy_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        proxy_form.setSpacing(10)
        proxy_form.setContentsMargins(16, 18, 16, 14)
        proxy_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.proxy_enabled = QCheckBox()
        self.proxy_type = QComboBox()
        self.proxy_type.addItem('HTTP', 'http')
        self.proxy_type.addItem('SOCKS5', 'socks5')
        self.proxy_host = QLineEdit()
        self.proxy_host.setPlaceholderText('127.0.0.1')
        self.proxy_port = QSpinBox()
        self.proxy_port.setRange(1, 65535)
        self.proxy_username = QLineEdit()
        self.proxy_username.setPlaceholderText('（可选）')
        self.proxy_password = QLineEdit()
        self.proxy_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.proxy_password.setPlaceholderText('（可选）')

        proxy_form.addRow('启用代理:', self.proxy_enabled)
        proxy_form.addRow('代理类型:', self.proxy_type)
        proxy_form.addRow('代理地址:', self.proxy_host)
        proxy_form.addRow('代理端口:', self.proxy_port)
        proxy_form.addRow('用户名:', self.proxy_username)
        proxy_form.addRow('密码:', self.proxy_password)

        layout.addWidget(proxy_group)

        # 下载完成后操作
        actions_group = QGroupBox('下载完成后')
        actions_form = QFormLayout(actions_group)
        actions_form.setSpacing(10)

        self.completion_action = QComboBox()
        self.completion_action.addItem('无操作', 'none')
        self.completion_action.addItem('关机', 'shutdown')
        self.completion_action.addItem('休眠', 'hibernate')
        self.completion_action.addItem('打开下载目录', 'open_folder')
        actions_form.addRow('自动操作:', self.completion_action)

        layout.addWidget(actions_group)
        layout.addStretch()
        return tab

    # ═══ BT/磁力设置 ═══

    def _create_bt_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)

        bt_group = QGroupBox('BT / 磁力链接')
        form = QFormLayout(bt_group)
        form.setSpacing(10)

        self.bt_port = QSpinBox()
        self.bt_port.setRange(1024, 65535)
        form.addRow('监听端口:', self.bt_port)

        self.bt_max_connections = QSpinBox()
        self.bt_max_connections.setRange(50, 2000)
        form.addRow('最大连接数:', self.bt_max_connections)

        self.bt_upload_limit = QComboBox()
        self.bt_upload_limit.addItem('无限制', 0)
        self.bt_upload_limit.addItem('50 KB/s', 50 * 1024)
        self.bt_upload_limit.addItem('100 KB/s', 100 * 1024)
        self.bt_upload_limit.addItem('200 KB/s', 200 * 1024)
        self.bt_upload_limit.addItem('500 KB/s', 500 * 1024)
        form.addRow('上传限速:', self.bt_upload_limit)

        self.bt_metadata_timeout = QSpinBox()
        self.bt_metadata_timeout.setRange(60, 600)
        self.bt_metadata_timeout.setSuffix(' 秒')
        form.addRow('元数据解析超时:', self.bt_metadata_timeout)

        layout.addWidget(bt_group)
        layout.addStretch()
        return tab

    # ═══ 播放器设置 ═══

    def _create_player_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)

        player_group = QGroupBox('播放器')
        form = QFormLayout(player_group)
        form.setSpacing(10)

        # 默认音量
        vol_row = QHBoxLayout()
        self.default_volume = QSlider(Qt.Orientation.Horizontal)
        self.default_volume.setRange(0, 100)
        self.default_volume.valueChanged.connect(self._on_volume_changed)
        vol_row.addWidget(self.default_volume)
        self._vol_label = QLabel('70')
        self._vol_label.setFixedWidth(35)
        self._vol_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        vol_row.addWidget(self._vol_label)
        form.addRow('默认音量:', vol_row)

        self.auto_load_subtitle = QCheckBox()
        form.addRow('自动加载同名字幕:', self.auto_load_subtitle)

        # 字幕字体大小
        sub_size_row = QHBoxLayout()
        self.subtitle_font_size = QSlider(Qt.Orientation.Horizontal)
        self.subtitle_font_size.setRange(12, 48)
        self.subtitle_font_size.valueChanged.connect(self._on_sub_font_size_changed)
        sub_size_row.addWidget(self.subtitle_font_size)
        self._sub_fs_label = QLabel('16')
        self._sub_fs_label.setFixedWidth(35)
        self._sub_fs_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        sub_size_row.addWidget(self._sub_fs_label)
        form.addRow('字幕字体大小:', sub_size_row)

        layout.addWidget(player_group)
        layout.addStretch()
        return tab

    # ═══ 通用设置 ═══

    def _create_general_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)

        general_group = QGroupBox('通用')
        form = QFormLayout(general_group)
        form.setSpacing(10)

        self.clipboard_monitor = QCheckBox()
        form.addRow('剪贴板链接检测:', self.clipboard_monitor)

        self.completion_sound = QCheckBox()
        form.addRow('下载完成提示音:', self.completion_sound)

        layout.addWidget(general_group)
        layout.addStretch()
        return tab

    # ═══ 加载/保存 ═══

    def _load_settings(self):
        """从 settings.json 和 config 默认值加载当前设置"""
        # 下载
        self.download_dir.setText(get_setting('download_dir', config.DEFAULT_DOWNLOAD_DIR))
        self._set_combo_value(self.thread_count, get_setting('thread_count', config.DEFAULT_THREAD_COUNT))
        self.max_concurrent.setValue(get_setting('max_concurrent_tasks', config.MAX_CONCURRENT_TASKS))
        self._set_combo_value(self.speed_limit, get_setting('download_speed_limit', config.DOWNLOAD_SPEED_LIMIT))
        self.max_retries.setValue(get_setting('max_retries', config.MAX_RETRIES))

        # BT
        self.bt_port.setValue(get_setting('bt_listen_port', config.BT_LISTEN_PORT))
        self.bt_max_connections.setValue(get_setting('bt_max_connections', config.BT_MAX_CONNECTIONS))
        self._set_combo_value(self.bt_upload_limit, get_setting('bt_upload_rate_limit', config.BT_UPLOAD_RATE_LIMIT))
        self.bt_metadata_timeout.setValue(get_setting('bt_metadata_timeout', config.BT_METADATA_TIMEOUT))

        # 播放器
        self.default_volume.setValue(get_setting('default_volume', config.DEFAULT_VOLUME))
        self.auto_load_subtitle.setChecked(get_setting('subtitle_auto_load', config.SUBTITLE_AUTO_LOAD))
        self.subtitle_font_size.setValue(get_setting('subtitle_font_size', config.SUBTITLE_FONT_SIZE))

        # 下载完成后操作
        action = get_setting('completion_action', 'none')
        self._set_combo_value(self.completion_action, action)

        # 代理
        self.proxy_enabled.setChecked(get_setting('proxy_enabled', config.PROXY_ENABLED))
        self._set_combo_value(self.proxy_type, get_setting('proxy_type', config.PROXY_TYPE))
        self.proxy_host.setText(get_setting('proxy_host', config.PROXY_HOST))
        self.proxy_port.setValue(get_setting('proxy_port', config.PROXY_PORT))
        self.proxy_username.setText(get_setting('proxy_username', config.PROXY_USERNAME))
        self.proxy_password.setText(get_setting('proxy_password', config.PROXY_PASSWORD))

        # 通用
        self.clipboard_monitor.setChecked(get_setting('clipboard_monitor', True))
        self.completion_sound.setChecked(get_setting('completion_sound', True))

    def _save_and_close(self):
        """保存所有设置并关闭对话框"""
        # 下载
        set_setting('download_dir', self.download_dir.text().strip())
        set_setting('thread_count', self.thread_count.currentData())
        set_setting('max_concurrent_tasks', self.max_concurrent.value())
        speed = self.speed_limit.currentData()
        set_setting('download_speed_limit', speed)
        config.DOWNLOAD_SPEED_LIMIT = speed  # 运行时立即生效
        set_setting('max_retries', self.max_retries.value())

        # BT（保存到 settings，config 值在下次启动时生效）
        set_setting('bt_listen_port', self.bt_port.value())
        set_setting('bt_max_connections', self.bt_max_connections.value())
        set_setting('bt_upload_rate_limit', self.bt_upload_limit.currentData())
        set_setting('bt_metadata_timeout', self.bt_metadata_timeout.value())

        # 播放器
        set_setting('default_volume', self.default_volume.value())
        set_setting('subtitle_auto_load', self.auto_load_subtitle.isChecked())
        set_setting('subtitle_font_size', self.subtitle_font_size.value())
        config.SUBTITLE_FONT_SIZE = self.subtitle_font_size.value()

        # 下载完成后操作
        set_setting('completion_action', self.completion_action.currentData())

        # 代理（运行时立即生效）
        set_setting('proxy_enabled', self.proxy_enabled.isChecked())
        set_setting('proxy_type', self.proxy_type.currentData())
        set_setting('proxy_host', self.proxy_host.text().strip())
        set_setting('proxy_port', self.proxy_port.value())
        set_setting('proxy_username', self.proxy_username.text().strip())
        set_setting('proxy_password', self.proxy_password.text().strip())
        config.PROXY_ENABLED = self.proxy_enabled.isChecked()
        config.PROXY_TYPE = self.proxy_type.currentData()
        config.PROXY_HOST = self.proxy_host.text().strip()
        config.PROXY_PORT = self.proxy_port.value()
        config.PROXY_USERNAME = self.proxy_username.text().strip()
        config.PROXY_PASSWORD = self.proxy_password.text().strip()

        # 通用
        set_setting('clipboard_monitor', self.clipboard_monitor.isChecked())
        set_setting('completion_sound', self.completion_sound.isChecked())

        self.accept()

    # ═══ 辅助方法 ═══

    def _browse_download_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, '选择下载保存目录', self.download_dir.text())
        if dir_path:
            self.download_dir.setText(dir_path)

    def _on_volume_changed(self, value):
        self._vol_label.setText(str(value))

    def _on_sub_font_size_changed(self, value):
        self._sub_fs_label.setText(str(value))

    @staticmethod
    def _set_combo_value(combo: QComboBox, value):
        """设置 QComboBox 为指定 data 值的选项"""
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return
        # 未找到匹配项则选第一个
        combo.setCurrentIndex(0)
