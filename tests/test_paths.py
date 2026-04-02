from pathlib import Path

from garmin_sync.paths import get_app_data_dir


def test_get_app_data_dir_uses_application_support_on_macos(tmp_path: Path):
    path = get_app_data_dir(home=tmp_path, platform_name="darwin", xdg_config_home=None)
    assert path == tmp_path / "Library" / "Application Support" / "garmin-sync"


def test_get_app_data_dir_uses_xdg_when_available(tmp_path: Path):
    xdg_root = tmp_path / "xdg"
    path = get_app_data_dir(home=tmp_path, platform_name="linux", xdg_config_home=str(xdg_root))
    assert path == xdg_root / "garmin-sync"
