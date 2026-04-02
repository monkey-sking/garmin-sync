# garmin-sync

Local CLI for batch-uploading `.fit` and `.gpx` files into Garmin Connect China or Global, with optional personal OneDrive web download support.

## Setup

```bash
cd garmin-sync
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m playwright install chromium
```

## Commands

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

## OneDrive Flow

1. Run `onedrive login` and finish normal OneDrive web login in the browser window.
2. Run `onedrive pick-folder`, manually open the source folder in the browser, then confirm in the terminal.
3. Run `onedrive pull-fit` to download the selected folder contents from OneDrive and extract `.fit` files locally while preserving nested subdirectories.
4. Run `upload` when you want to send local `.fit` and `.gpx` files to Garmin.

## Notes

- Source `.fit` and `.gpx` files are left in place.
- Upload state and browser session storage live under `~/Library/Application Support/garmin-sync` on macOS.
- OneDrive pull state lives in the same app data directory.
- The OneDrive browser flow depends on the current web UI and may need small selector adjustments after the first real login.

## Aion Integration

If browser automation on this Mac opens and closes unexpectedly, or behaves differently from the user's normal Chrome session, see the shared Aion integration notes:

- Skill entry: [docs/skills/aion-browser-integration/SKILL.md](docs/skills/aion-browser-integration/SKILL.md)
- Detailed reference: [docs/skills/aion-browser-integration/references/garmin-sync-aion-integration.md](docs/skills/aion-browser-integration/references/garmin-sync-aion-integration.md)

To reuse the skill in another Codex setup, copy the `docs/skills/aion-browser-integration` folder into `$CODEX_HOME/skills` or `~/.codex/skills`.

## Public Sharing

If you plan to publish this repository to GitHub, read the cleanup note first:

- [docs/public-sharing.md](docs/public-sharing.md)
