import os
import sys
from pathlib import Path
from typing import Optional


def get_app_data_dir(
    home: Optional[Path] = None,
    platform_name: Optional[str] = None,
    xdg_config_home: Optional[str] = None,
) -> Path:
    home_dir = home or Path.home()
    active_platform = platform_name or sys.platform

    if active_platform == "darwin":
        return home_dir / "Library" / "Application Support" / "garmin-sync"

    xdg_root = xdg_config_home or os.environ.get("XDG_CONFIG_HOME")
    if xdg_root:
        return Path(xdg_root) / "garmin-sync"

    return home_dir / ".config" / "garmin-sync"
