# M3U8 视频下载器

本项目是一个基于 Python 的异步爬虫，能够从指定的视频播放页面自动提取 M3U8 链接、下载密钥（如果加密）、解析多级 M3U8 索引、并发下载所有 TS 片段，最后调用 FFmpeg 合并为完整的 MP4 文件，并清理临时文件。

---

## ✨ 功能特点

- **自动解析**：从播放页面的 `<script>` 标签中提取真实 M3U8 地址和视频标题。
- **支持多级 M3U8**：自动递归处理 `#EXT-X-STREAM-INF` 索引，直到获取最终的 TS 列表。
- **AES-128 解密支持**：自动下载密钥文件（enc.key），合并时 FFmpeg 自动解密。
- **异步并发下载**：使用 `asyncio` + `aiohttp` 实现高并发下载 TS 片段，速度更快。
- **本地化 M3U8**：将远程 M3U8 文件重写为仅包含本地 TS 文件名的版本，便于 FFmpeg 合并。
- **自动清理**：合并成功后删除所有临时文件（TS、key、M3U8），节省空间。
- **异常重试**：单个 TS 片段下载失败自动重试，保证完整性。

---

## 📋 环境要求

- Python 3.7 或更高版本
- [FFmpeg](https://ffmpeg.org/) 已安装并添加到系统环境变量（用于合并视频）
- 操作系统：Windows / macOS / Linux（路径分隔符已适配）

---

## 🔧 安装

1. **克隆或下载本项目**，进入项目目录。

2. **安装 Python 依赖**：
   ```bash
   pip install aiofiles aiohttp requests lxml
   ```

3. **安装 FFmpeg**：
   - **Windows**：从 [FFmpeg官网](https://ffmpeg.org/download.html) 下载并解压，将 `bin` 目录添加到系统 PATH。
   - **macOS**：`brew install ffmpeg`
   - **Linux**：`sudo apt install ffmpeg`（Ubuntu/Debian）或相应包管理器。

4. **验证安装**：
   ```bash
   ffmpeg -version
   ```
   应显示版本信息。

---

## 🚀 使用说明

1. **修改目标 URL**  
   打开脚本文件（例如 `downloader.py`），找到 `main()` 函数中的 `base_url` 和 `enc_key_url`，替换为你需要下载的视频播放页 URL 和密钥文件 URL（如果已知）。  
   ```python
   base_url = 'https://example.com/vodplay/xxx.html'
   enc_key_url = 'https://example.com/path/enc.key'   # 如果没有密钥可置空或删除
   ```

2. **运行脚本**  
   ```bash
   python downloader.py
   ```

3. **等待执行**  
   程序会自动创建 `movie/视频标题/` 目录，下载所有 TS 片段并合并为 `视频标题.mp4`，最后清理临时文件。

4. **查看结果**  
   合并后的 MP4 文件保存在 `movie/视频标题/` 目录下。

---

## 📁 代码结构

| 函数/组件 | 说明 |
|----------|------|
| `get_m3u8_url(url)` | 从播放页提取真实 M3U8 地址和标题 |
| `parse_m3u8_url(m3u8_url, file_path, file_name)` | 下载 M3U8 文件到本地 |
| `confirm_m3u8(full_file_path, m3u8_url)` | 检查当前 M3U8 是否为多级索引，返回下一级 URL |
| `download_key(url, file_path)` | 下载 AES 密钥文件（enc.key） |
| `create_tasks(full_file_path, m3u8_url)` | 从最终 M3U8 中提取所有 TS 片段的完整 URL |
| `download_tasks(tasks_urls, file_path)` | 并发调度下载任务 |
| `download_file(url, file_path, sem)` | 下载单个 TS 片段（支持重试） |
| `re_write_m3u8(file_path, file_name)` | 重写 M3U8，将远程路径改为本地文件名 |
| `merge_video(file_path, m3u8, title)` | 调用 FFmpeg 合并 TS 为 MP4 |
| `remove_files(file_path)` | 删除所有临时文件（.ts、.key、.m3u8） |
| `main()` | 主流程控制 |

---

## ⚠️ 注意事项

- **请求头**：代码中已包含常用的浏览器请求头，若目标网站有更严格的反爬策略，可能需要调整 `headers`（如添加 Cookie）。
- **密钥文件**：如果视频未加密，M3U8 中不会出现 `#EXT-X-KEY` 标签，此时无需下载密钥，可注释或删除 `download_key` 调用。
- **并发数**：`asyncio.Semaphore(100)` 控制最大并发连接数，可根据网络和系统性能调整（Windows 建议不超过 500）。
- **路径空格**：代码中未对文件名中的空格做特殊处理，但 FFmpeg 命令使用 `subprocess.run` 列表形式已避免空格问题。如果手动修改为字符串形式，请添加引号。
- **FFmpeg 参数**：`-allowed_extensions ALL` 是必需的，否则 FFmpeg 会因 `.key` 文件扩展名不常见而拒绝加载。
- **清理文件**：`remove_files` 会删除目录下所有 `.ts`、`.key`、`.m3u8` 文件，如果目录中还有其他重要文件请谨慎使用。

---

## 📄 许可证

本项目仅供学习交流使用，请勿用于商业或非法用途。下载的视频请遵守相关法律法规。

---

## 🤝 贡献

欢迎提交 Issue 或 Pull Request 改进代码。
