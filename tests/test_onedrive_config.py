from pathlib import Path

from garmin_sync.config import AppConfig
from garmin_sync.config import ConfigStore


def test_config_store_persists_onedrive_web_settings(tmp_path: Path):
    store = ConfigStore(tmp_path / "data")
    config = AppConfig(
        onedrive_provider="personal-web",
        onedrive_selected_folder_url="https://onedrive.live.com/?id=%2FWorkouts",
        onedrive_selected_folder_name="Workouts",
        onedrive_download_dir=str(tmp_path / "downloads"),
    )
    store.save(config)

    loaded = store.load()

    assert loaded.onedrive_provider == "personal-web"
    assert loaded.onedrive_selected_folder_url == "https://onedrive.live.com/?id=%2FWorkouts"
    assert loaded.onedrive_selected_folder_name == "Workouts"
    assert loaded.onedrive_download_dir == str(tmp_path / "downloads")


def test_config_store_ignores_legacy_graph_folder_id(tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "config.json").write_text(
        '{"onedrive_selected_folder_id":"folder-123","onedrive_selected_folder_name":"Legacy"}'
    )

    loaded = ConfigStore(data_dir).load()

    assert loaded.onedrive_selected_folder_url is None
    assert loaded.onedrive_selected_folder_name == "Legacy"
