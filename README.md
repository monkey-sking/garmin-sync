# garmin-sync

<!-- badges:start -->
[![License](https://img.shields.io/badge/license-Apache--2.0-blue?style=flat-square)](https://github.com/monkey-sking/garmin-sync/blob/main/LICENSE) [![Last commit](https://img.shields.io/github/last-commit/monkey-sking/garmin-sync?style=flat-square)](https://github.com/monkey-sking/garmin-sync/commits/main) [![Python](https://img.shields.io/github/languages/top/monkey-sking/garmin-sync?style=flat-square)](https://github.com/monkey-sking/garmin-sync/search?l=Python) [![views](https://hits.sh/github.com/monkey-sking/garmin-sync.svg?style=flat-square&label=views&color=0e75b6)](https://github.com/monkey-sking/garmin-sync) [![Stars](https://img.shields.io/github/stars/monkey-sking/garmin-sync?style=flat-square)](https://github.com/monkey-sking/garmin-sync/stargazers) [![Forks](https://img.shields.io/github/forks/monkey-sking/garmin-sync?style=flat-square)](https://github.com/monkey-sking/garmin-sync/network/members)
<!-- badges:end -->

用于批量上传 `.fit` 和 `.gpx` 运动文件到 Garmin Connect 中国区或国际区的本地 CLI 工具，并可选支持个人 OneDrive 网页下载。

Local CLI for batch-uploading `.fit` and `.gpx` activity files into Garmin Connect China or Global, with optional personal OneDrive web download support.

## 安装 / Setup

```bash
cd garmin-sync
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m playwright install chromium
```

## 命令 / Commands

```bash
PYTHONPATH=src .venv/bin/python -m garmin_sync.cli upload /path/to/files --site cn
PYTHONPATH=src .venv/bin/python -m garmin_sync.cli login --site global
PYTHONPATH=src .venv/bin/python -m garmin_sync.cli config set-default-site cn
PYTHONPATH=src .venv/bin/python -m garmin_sync.cli config set-default-dir /path/to/files
PYTHONPATH=src .venv/bin/python -m garmin_sync.cli config show
PYTHONPATH=src .venv/bin/python -m garmin_sync.cli onedrive login
PYTHONPATH=src .venv/bin/python -m garmin_sync.cli onedrive pick-folder
PYTHONPATH=src .venv/bin/python -m garmin_sync.cli onedrive show-folder
PYTHONPATH=src .venv/bin/python -m garmin_sync.cli onedrive pull-fit --dir /path/to/files
```

## OneDrive 流程 / OneDrive Flow

1. 运行 `onedrive login`，并在浏览器窗口中完成正常的 OneDrive 网页登录。  
   Run `onedrive login` and finish normal OneDrive web login in the browser window.
2. 运行 `onedrive pick-folder`，在浏览器中手动打开源文件夹，然后回到终端确认。  
   Run `onedrive pick-folder`, manually open the source folder in the browser, then confirm in the terminal.
3. 运行 `onedrive pull-fit`，把选中文件夹的内容从 OneDrive 下载到本地，并在保留子目录结构的同时提取 `.fit` 文件。  
   Run `onedrive pull-fit` to download the selected folder contents from OneDrive and extract `.fit` files locally while preserving nested subdirectories.
4. 需要上传到 Garmin 时，运行 `upload`。  
   Run `upload` when you want to send local `.fit` and `.gpx` files to Garmin.

## 说明 / Notes

- 源 `.fit` 和 `.gpx` 文件会保留在原位置，不会被移动或删除。  
  Source `.fit` and `.gpx` files are left in place.
- 在 macOS 上，上传状态和浏览器会话存储在 `~/Library/Application Support/garmin-sync`。  
  Upload state and browser session storage live under `~/Library/Application Support/garmin-sync` on macOS.
- OneDrive 拉取状态也保存在同一个应用数据目录下。  
  OneDrive pull state lives in the same app data directory.
- OneDrive 网页流程依赖当前网页 UI，首次真实登录后可能仍需要少量选择器微调。  
  The OneDrive browser flow depends on the current web UI and may need small selector adjustments after the first real login.

## Aion 集成 / Aion Integration

如果这台 Mac 上的浏览器自动化会异常打开后立刻关闭，或与用户平时使用的 Chrome 会话表现不同，请查看共享的 Aion 集成说明：

If browser automation on this Mac opens and closes unexpectedly, or behaves differently from the user's normal Chrome session, see the shared Aion integration notes:

- Skill 入口 / Skill entry: [docs/skills/aion-browser-integration/SKILL.md](docs/skills/aion-browser-integration/SKILL.md)
- 详细说明 / Detailed reference: [docs/skills/aion-browser-integration/references/garmin-sync-aion-integration.md](docs/skills/aion-browser-integration/references/garmin-sync-aion-integration.md)

如果要在另一套 Codex 环境中复用这个 skill，把 `docs/skills/aion-browser-integration` 目录复制到 `$CODEX_HOME/skills` 或 `~/.codex/skills`。

To reuse the skill in another Codex setup, copy the `docs/skills/aion-browser-integration` folder into `$CODEX_HOME/skills` or `~/.codex/skills`.

## 公开分享 / Public Sharing

如果你准备把这个仓库发布到 GitHub，请先阅读清理说明：

If you plan to publish this repository to GitHub, read the cleanup note first:

- [docs/public-sharing.md](docs/public-sharing.md)
