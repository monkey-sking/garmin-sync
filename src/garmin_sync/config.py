from dataclasses import dataclass
import json
from json import JSONDecodeError
from pathlib import Path
from typing import Optional

from garmin_sync.prompts import prompt_for_input_dir
from garmin_sync.prompts import prompt_for_site


@dataclass
class AppConfig:
    default_site: Optional[str] = None
    default_input_dir: Optional[str] = None
    headless: bool = False
    onedrive_provider: Optional[str] = None
    onedrive_selected_folder_url: Optional[str] = None
    onedrive_selected_folder_name: Optional[str] = None
    onedrive_download_dir: Optional[str] = None


class ConfigStore:
    def __init__(self, data_dir: Path):
        self._data_dir = data_dir
        self._path = data_dir / "config.json"

    def load(self) -> AppConfig:
        self._data_dir.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            config = AppConfig()
            self.save(config)
            return config

        try:
            payload = json.loads(self._path.read_text() or "{}")
        except JSONDecodeError:
            config = AppConfig()
            self.save(config)
            return config
        if not isinstance(payload, dict):
            config = AppConfig()
            self.save(config)
            return config
        return AppConfig(
            default_site=payload.get("default_site"),
            default_input_dir=payload.get("default_input_dir"),
            headless=bool(payload.get("headless", False)),
            onedrive_provider=payload.get("onedrive_provider"),
            onedrive_selected_folder_url=payload.get("onedrive_selected_folder_url"),
            onedrive_selected_folder_name=payload.get("onedrive_selected_folder_name"),
            onedrive_download_dir=payload.get("onedrive_download_dir"),
        )

    def save(self, config: AppConfig) -> None:
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(
                {
                    "default_site": config.default_site,
                    "default_input_dir": config.default_input_dir,
                    "headless": config.headless,
                    "onedrive_provider": config.onedrive_provider,
                    "onedrive_selected_folder_url": config.onedrive_selected_folder_url,
                    "onedrive_selected_folder_name": config.onedrive_selected_folder_name,
                    "onedrive_download_dir": config.onedrive_download_dir,
                },
                indent=2,
                sort_keys=True,
            )
        )


def resolve_site(cli_site: Optional[str], config: AppConfig) -> str:
    if cli_site:
        return cli_site
    if config.default_site:
        return config.default_site
    return prompt_for_site()


def resolve_input_dir(cli_dir: Optional[str], config: AppConfig) -> Path:
    path: Path
    if cli_dir:
        path = Path(cli_dir).expanduser().resolve()
    elif config.default_input_dir:
        path = Path(config.default_input_dir).expanduser().resolve()
    else:
        path = prompt_for_input_dir()

    if not path.exists():
        raise FileNotFoundError(f"Input directory does not exist: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"Input path is not a directory: {path}")

    return path
