# FlashDL 可扩展功能清单

基于当前项目架构分析与同类竞品横评，输出结构化功能生长路线图。

---

## 一、项目现状与定位

FlashDL 当前核心定位是"下载+播放一体化工具"，已具备：

- **下载引擎**：HTTP Range 多线程下载、断点续传、磁力/BT 下载（libtorrent）
- **播放器**：mpv 内核嵌入、播放列表管理、字幕/音轨/章节支持
- **管理能力**：任务卡片队列、拖拽排序、历史记录搜索分页、剪贴板监听
- **体验层**：Design Tokens 双主题系统、无边框窗口、系统托盘

竞品格局中，FlashDL 的差异化在于**下载与播放的自然融合**——IDM/FDM 侧重下载但无播放器，PotPlayer/VLC 侧重播放但无下载管理。这是核心生长原点。

---

## 二、核心功能（P0）—— 补齐竞品基线，强化融合优势

此类功能直接影响用户留存与口碑，应在 1-3 个版本周期内落地。

### P0-1. HLS / m3u8 流媒体下载

- **扩展目标**：支持解析 .m3u8 播放列表，下载 TS 分片并自动合并为 MP4
- **适用场景**：直播回放、在线课程、流媒体网站视频下载
- **架构关联**：复用 `DownloadWorker` 的多线程分块能力；新增 `HLSDownloadTask` 子类继承 `BaseDownloadTask`；合并逻辑可复用现有 chunk 完成后的状态机
- **竞品参考**：Ninja Download Manager 内置视频下载器、JDownloader 的解密插件体系

### P0-2. 下载队列调度与定时任务

- **扩展目标**：支持设定下载时间窗口（如凌晨 2:00-6:00 不限速下载）、任务启动/暂停的排程
- **适用场景**：大文件夜间下载、避免高峰时段占用带宽
- **架构关联**：在 `DownloadManager` 中新增 `Scheduler` 模块，基于 Qt 的 `QTimer` 实现；配置持久化到 `settings.json`
- **竞品参考**：IDM Scheduler、FDM 下载调度

### P0-3. 下载后自动分类与文件整理

- **扩展目标**：按文件类型（视频/音频/文档/压缩包）或自定义规则自动归类到不同文件夹
- **适用场景**：大量下载后文件散落在同一目录，手动整理耗时
- **架构关联**：在 `DownloadTask.completed` 信号处理中增加后置分类逻辑；规则引擎可用简单的 dict 映射，无需引入新依赖
- **竞品参考**：Download Pilot 智能分类、IDM 下载类别

### P0-4. 进度缩略图预览

- **扩展目标**：下载完成前在进度条上悬浮显示当前下载的视频帧缩略图
- **适用场景**：确认下载内容是否正确（避免下错资源）
- **架构关联**：利用 mpv 的截图能力定时（如每 10% 进度）截取一帧；缩略图存到 temp 目录，在 `TaskCard` 上展示
- **竞品参考**：PotPlayer 进度缩略图

### P0-5. 浏览器扩展集成（下载链接自动捕获）

- **扩展目标**：开发 Chrome/Firefox 扩展，自动嗅探网页中的视频/下载链接并发送到 FlashDL
- **适用场景**：浏览网页时一键发送下载任务到桌面端
- **架构关联**：本地 HTTP Server（Flask/aiohttp 轻量嵌入）接收浏览器扩展发来的 URL；`main.py` 启动时在后台线程启动本地监听
- **竞品参考**：IDM Integration Module、XDM 浏览器扩展

---

## 三、增值功能（P1）—— 建立差异化壁垒，扩大用户覆盖面

此类功能是区别于竞品的核心卖点，应在 3-6 个月内逐步落地。

### P1-1. AI 智能下载助手

- **扩展目标**：
  - **智能命名**：从网页标题/视频描述中提取语义化文件名，替代 URL 中的乱码文件名
  - **内容摘要**：下载完成后自动生成视频/音频的文字摘要（调用本地/在线 LLM）
  - **智能分类**：基于文件内容和元数据的 AI 分类（视频类型：电影/教程/音乐MV 等）
- **适用场景**：批量下载时自动组织内容库
- **架构关联**：新增 `ai/` 模块，调用 OpenAI 兼容 API；在 `DownloadTask.prepare()` 中注入 AI 命名逻辑；利用现有 `Database` 存储 AI 元数据
- **竞品参考**：AB Download Manager 2025 路线图中的智能调度

### P1-2. 播放器画面增强引擎

- **扩展目标**：
  - **RTX Video HDR**：SDR 视频实时转 HDR（利用 NVIDIA 显卡 AI 超分）
  - **超分辨率**：低分辨率视频实时放大（mpv 的 anime4k/shaders）
  - **画面滤镜链**：锐化、降噪、色彩校正的可视化配置
- **适用场景**：老视频/低画质资源提升观看体验
- **架构关联**：mpv 原生支持 GLSL shader 和 user-shaders；在 `PlayerTab` 的视频菜单中新增滤镜面板
- **竞品参考**：PotPlayer RTX Video HDR、mpv anime4k 着色器

### P1-3. 远程控制与 Web 面板

- **扩展目标**：通过手机/平板浏览器远程管理下载任务——添加、暂停、查看进度
- **适用场景**：离开电脑时通过手机查看下载状态，远程添加任务
- **架构关联**：本地 Flask/FastAPI 服务 + WebSocket 推送进度；复用 `signal_bus` 的事件广播机制；前端用简约单页 HTML
- **竞品参考**：qBittorrent Web UI、FDM 远程控制

### P1-4. RSS 订阅自动下载

- **扩展目标**：订阅 RSS/Atom 源，按关键词/正则过滤，有新资源时自动添加到下载队列
- **适用场景**：追剧、追番、订阅 YouTube 频道更新自动下载
- **架构关联**：新增 `rss/` 订阅模块；规则引擎复用 `Database` 存储；`DownloadManager` 中增加 `RSSWatcher` 定时检查
- **竞品参考**：qBittorrent RSS 订阅器

### P1-5. BT 内置搜索引擎

- **扩展目标**：在应用内搜索主流 BT 站点的资源，并一键添加磁力下载
- **适用场景**：不需要打开浏览器即可搜索和下载 BT 资源
- **架构关联**：新增 `bt_search/` 模块，调用各站点 API 或解析 HTML；搜索结果在 `DownloadTab` 中以弹窗形式展示
- **竞品参考**：qBittorrent 内置搜索

### P1-6. 下载格式转换与后处理

- **扩展目标**：下载完成后自动转换为目标格式（如 TS→MP4、FLV→MP4、无损音频压缩）
- **适用场景**：下载的流媒体文件格式不兼容播放设备时自动转换
- **架构关联**：在 `DownloadTask.completed` 后增加 PostProcessor 管道；调用 FFmpeg（subprocess）；可复用 `task_worker.py` 的 Worker 线程模式
- **竞品参考**：Ninja Download Manager 格式转换

---

## 四、远期功能（P2）—— 前瞻性布局，建立长期壁垒

此类功能探索技术前沿或拓展新场景，建议在 P0/P1 稳定后择机投入。

### P2-1. 多设备同步与云存储集成

- **扩展目标**：通过云盘（OneDrive/Google Drive）同步下载任务列表和历史记录；支持直接下载到云盘目录
- **适用场景**：多台电脑间共享下载队列和播放进度
- **架构关联**：`utils/settings.py` 的 JSON 持久化可升级为云同步后端；播放进度（progress 记忆）同步
- **竞品参考**：IDM 无此功能（差异化机会）

### P2-2. P2P 加速下载（分布式 CDN）

- **扩展目标**：用户之间共享已下载文件的缓存，其他用户下载相同 URL 时可从对等节点加速
- **适用场景**：热门资源（如大版本更新包）的分布式加速
- **架构关联**：基于 libtorrent 的 P2P 能力改造；新增加速层在 `DownloadWorker` 中优先从 P2P 网络获取数据块
- **竞品参考**：类似迅雷的 P2SP 技术，但没有竞品将此内置到独立下载器中

### P2-3. 视频编辑轻量化工具集

- **扩展目标**：内置 GIF 截取、视频裁剪、片段合并、关键帧提取
- **适用场景**：下载后直接进行简单编辑，无需打开专业工具
- **架构关联**：通过 mpv 定位关键帧 + FFmpeg 执行裁剪/合并；在 `PlayerTab` 上增加编辑模式
- **竞品参考**：PotPlayer 内置视频编辑器

### P2-4. 插件市场与社区生态

- **扩展目标**：开放插件 API（Python），用户可开发下载站点解析器、UI 主题、后处理脚本
- **适用场景**：用户自定义 YouTube/Bilibili 等站点解析器，社区贡献主题
- **架构关联**：设计插件加载器（基于 importlib）；插件通过注册到 `signal_bus` 或实现特定接口接入
- **竞品参考**：JDownloader 300+ 解密插件、PotPlayer OpenCodec/Skins

### P2-5. 跨平台支持（macOS / Linux）

- **扩展目标**：移植到 macOS 和 Linux（当前仅 Windows）
- **适用场景**：扩大用户基础
- **架构关联**：PyQt6 + python-mpv 本身跨平台；需处理 OS 特定逻辑（如 `os.startfile`、`winsound`、Windows 长路径）；条件导入 + 适配层
- **竞品参考**：FDM（Win+Mac+Linux）、qBittorrent（全平台）

### P2-6. 命令行模式与自动化脚本支持

- **扩展目标**：提供 CLI 接口（`flashdl download <url>`），支持 CI/脚本批量下载和自动化
- **适用场景**：服务器端无人值守下载、爬虫流水线集成
- **架构关联**：将 `DownloadManager` 解耦为无 UI 核心；CLI 入口参考 `main.py` 的事件循环模式
- **竞品参考**：mpv 命令行模式、aria2c

---

## 五、功能优先级矩阵

| 优先级 | 功能 | 实现复杂度 | 用户价值 | 差异化程度 | 推荐周期 |
|--------|------|-----------|---------|-----------|---------|
| P0 | HLS/m3u8 流媒体下载 | 中 | 极高 | 中 | v2.2 |
| P0 | 队列调度与定时任务 | 低 | 高 | 低 | v2.2 |
| P0 | 自动分类整理 | 低 | 高 | 中 | v2.3 |
| P0 | 进度缩略图预览 | 中 | 中 | 高 | v2.3 |
| P0 | 浏览器扩展集成 | 中 | 极高 | 中 | v2.4 |
| P1 | AI 智能助手 | 高 | 高 | 极高 | v2.5 |
| P1 | 画面增强引擎 | 中 | 高 | 高 | v2.5 |
| P1 | 远程控制 Web 面板 | 中 | 高 | 中 | v2.6 |
| P1 | RSS 订阅下载 | 中 | 中 | 中 | v2.6 |
| P1 | BT 内置搜索 | 中 | 中 | 低 | v2.7 |
| P1 | 格式转换后处理 | 低 | 中 | 中 | v2.7 |
| P2 | 多设备云同步 | 高 | 中 | 极高 | v3.0 |
| P2 | P2P 加速 | 极高 | 高 | 极高 | v3.0 |
| P2 | 视频编辑工具集 | 高 | 中 | 高 | v3.1 |
| P2 | 插件市场生态 | 极高 | 极高 | 极高 | v3.2 |
| P2 | 跨平台支持 | 高 | 极高 | 中 | v3.2 |
| P2 | CLI 命令行模式 | 低 | 中 | 中 | v3.1 |

---

## 六、架构演进建议

针对以上功能清单的执行，建议对现有架构做三处前瞻性调整：

### 6.1 下载后处理管道

当前 `DownloadTask` 的 `completed` 信号直接触达 UI 层。建议在 `DownloadManager` 中插入 PostProcessor 管道：

```
DownloadTask.completed → PostProcessor Chain → signal_bus.task_completed
                          ├── Format Converter
                          ├── AI Naming/Tagging
                          └── Auto Classifier
```

实现方式：`DownloadManager` 维护一个 `post_processor` 列表，每个 processor 实现 `process(task_id, file_path) → file_path` 接口。在 P1 的格式转换和 AI 分类中直接复用。

### 6.2 本地 HTTP 网关

浏览器扩展、远程 Web 面板、CLI 模式都需要与 FlashDL 核心通信。建议统一到一个轻量本地 HTTP 服务：

```
                     ┌─────────────────┐
  Browser Extension ─┤                 │
  Web Remote Panel ──┤  Local Gateway  ├── DownloadManager
  CLI Tool ──────────┤  (Flask/WS)     │
                     └─────────────────┘
```

在 `main.py` 启动时开启后台线程运行，端口可配置。该网关是 P0-5 和 P1-3 的前置基础设施。

### 6.3 插件加载器

为 P2-4 插件市场做准备，建议在 `core/` 下预置插件注册机制：

```python
# core/plugin_loader.py (预留接口)
class PluginBase:
    name: str
    version: str

    def on_download_start(self, task): ...
    def on_download_complete(self, task): ...
    def get_ui_panel(self) -> QWidget | None: ...
```

初期可先实现 URL 解析器插件类型（对应 JDownloader 的解密插件概念），后续扩展到 UI 主题和媒体后处理。

---

## 七、参考资料

1. [TechRadar - Best Free Download Manager of 2026](https://www.techradar.com/best/free-download-manager)
2. [IDM 官方功能列表](https://www.internetdownloadmanager.com/features2.html)
3. [qBittorrent 功能特性](https://www.qbittorrent.org.cn/features.html)
4. [PotPlayer 完整功能介绍](https://potplayer.dev/cn/features.html)
5. [开源视频播放器横向对比：VLC/mpv/IINA/PotPlayer](https://erweng.com/posts/free-video-player-comparison/)
6. [AB Download Manager 2025 路线图](https://blog.gitcode.com/42f32b3a92ea1e0137bae003db09922f.html)
7. [HLS Downloader - 浏览器流媒体捕获](https://github.com/puemos/hls-downloader)
8. [2026下载工具横评：IDM还值得买吗](https://zhuanlan.zhihu.com/p/2042925662412043326)
