from argparse import Namespace
from pathlib import Path

from garmin_sync.cli import _resolve_onedrive_download_dir
from garmin_sync.cli import handle_onedrive
from garmin_sync.cli import build_parser
from garmin_sync.config import AppConfig
from garmin_sync.config import ConfigStore
from garmin_sync.onedrive_models import OneDriveFolder


def test_parser_supports_upload_login_and_config_commands():
    parser = build_parser()

    upload_args = parser.parse_args(["upload", "/tmp/input", "--site", "cn"])
    assert upload_args.command == "upload"
    assert upload_args.directory == Path("/tmp/input")
    assert upload_args.site == "cn"

    login_args = parser.parse_args(["login", "--site", "global"])
    assert login_args.command == "login"
    assert login_args.site == "global"

    config_args = parser.parse_args(["config", "set-default-site", "cn"])
    assert config_args.command == "config"
    assert config_args.config_command == "set-default-site"
    assert config_args.site == "cn"


def test_parser_supports_onedrive_commands():
    parser = build_parser()

    login_args = parser.parse_args(["onedrive", "login"])
    assert login_args.command == "onedrive"
    assert login_args.onedrive_command == "login"

    pull_args = parser.parse_args(["onedrive", "pull-fit", "--dir", "/tmp/downloads"])
    assert pull_args.command == "onedrive"
    assert pull_args.onedrive_command == "pull-fit"
    assert pull_args.directory == Path("/tmp/downloads")


def test_handle_onedrive_login_calls_auth(tmp_path, monkeypatch):
    store = ConfigStore(tmp_path / "data")
    store.save(AppConfig())
    called = {}

    class FakeAuth:
        def __init__(self, data_dir):
            self.data_dir = data_dir

        def login(self, headless=False):
            called["headless"] = headless

    monkeypatch.setattr("garmin_sync.cli.OneDriveAuth", FakeAuth)

    result = handle_onedrive(Namespace(onedrive_command="login", directory=None), store)

    assert result == 0
    assert called["headless"] is False


def test_handle_onedrive_show_folder_prints_selection(tmp_path, capsys):
    store = ConfigStore(tmp_path / "data")
    store.save(
        AppConfig(
            onedrive_provider="personal-web",
            onedrive_selected_folder_url="https://onedrive.live.com/?id=folder-123",
            onedrive_selected_folder_name="Workout Exports",
        )
    )

    result = handle_onedrive(Namespace(onedrive_command="show-folder", directory=None), store)

    captured = capsys.readouterr()
    assert result == 0
    assert "Workout Exports" in captured.out
    assert "https://onedrive.live.com/?id=folder-123" in captured.out


def test_handle_onedrive_pick_folder_saves_selection(tmp_path, monkeypatch):
    store = ConfigStore(tmp_path / "data")
    store.save(AppConfig())

    class FakeAuth:
        def __init__(self, data_dir):
            self.data_dir = data_dir

    class FakeClient:
        def __init__(self, auth, headless=False):
            self.auth = auth
            self.headless = headless

    monkeypatch.setattr("garmin_sync.cli.OneDriveAuth", FakeAuth)
    monkeypatch.setattr("garmin_sync.cli.OneDriveClient", FakeClient)
    monkeypatch.setattr(
        "garmin_sync.cli.choose_folder",
        lambda client, initial_url=None: client and OneDriveFolder(
            url="https://onedrive.live.com/?id=folder-123",
            name="Workout Exports",
        ),
    )

    result = handle_onedrive(Namespace(onedrive_command="pick-folder", directory=None), store)

    saved = store.load()
    assert result == 0
    assert saved.onedrive_provider == "personal-web"
    assert saved.onedrive_selected_folder_url == "https://onedrive.live.com/?id=folder-123"
    assert saved.onedrive_selected_folder_name == "Workout Exports"


def test_handle_onedrive_pull_fit_uses_saved_folder_and_directory(tmp_path, monkeypatch):
    store = ConfigStore(tmp_path / "data")
    download_dir = tmp_path / "downloads"
    store.save(
        AppConfig(
            onedrive_provider="personal-web",
            onedrive_selected_folder_url="https://onedrive.live.com/?id=folder-123",
            onedrive_selected_folder_name="Workout Exports",
            onedrive_download_dir=str(download_dir),
        )
    )
    calls = {}

    class FakeAuth:
        def __init__(self, data_dir):
            self.data_dir = data_dir

    class FakeClient:
        def __init__(self, auth, headless=False):
            self.auth = auth
            self.headless = headless

    class FakeSummary:
        failed_count = 0

        def render(self):
            return "downloaded: 1"

    def fake_pull_fit_files(client, folder_url, folder_name, download_dir, state_store, retry_limit):
        calls["folder_url"] = folder_url
        calls["folder_name"] = folder_name
        calls["download_dir"] = download_dir
        calls["retry_limit"] = retry_limit
        return FakeSummary()

    monkeypatch.setattr("garmin_sync.cli.OneDriveAuth", FakeAuth)
    monkeypatch.setattr("garmin_sync.cli.OneDriveClient", FakeClient)
    monkeypatch.setattr("garmin_sync.cli.pull_fit_files", fake_pull_fit_files)

    result = handle_onedrive(Namespace(onedrive_command="pull-fit", directory=None), store)

    assert result == 0
    assert calls["folder_url"] == "https://onedrive.live.com/?id=folder-123"
    assert calls["folder_name"] == "Workout Exports"
    assert calls["download_dir"] == download_dir
    assert calls["retry_limit"] == 2


def test_resolve_onedrive_download_dir_prompts_without_onedrive_dir(tmp_path, monkeypatch):
    configured_input = tmp_path / "input"
    configured_input.mkdir()
    prompted_dir = tmp_path / "prompted"
    monkeypatch.setattr("builtins.input", lambda _: str(prompted_dir))

    result = _resolve_onedrive_download_dir(
        None,
        AppConfig(default_input_dir=str(configured_input), onedrive_download_dir=None),
    )

    assert result == prompted_dir
