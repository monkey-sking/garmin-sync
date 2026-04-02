from pathlib import Path

from garmin_sync.config import AppConfig
from garmin_sync.config import ConfigStore
from garmin_sync.config import resolve_input_dir
from garmin_sync.config import resolve_site


def test_default_config_uses_null_site_and_dir():
    config = AppConfig()
    assert config.default_site is None
    assert config.default_input_dir is None
    assert config.headless is False


def test_config_store_creates_default_file(tmp_path: Path):
    store = ConfigStore(tmp_path / "data")
    config = store.load()
    assert config.default_site is None
    assert config.default_input_dir is None
    assert config.headless is False
    assert (tmp_path / "data" / "config.json").exists()


def test_config_store_recovers_from_corrupt_json(tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "config.json").write_text("{broken")

    store = ConfigStore(data_dir)
    config = store.load()

    assert config.default_site is None
    assert config.default_input_dir is None
    assert config.headless is False


def test_config_store_recovers_from_wrong_json_shape(tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "config.json").write_text("[]")

    store = ConfigStore(data_dir)
    config = store.load()

    assert config.default_site is None
    assert config.default_input_dir is None
    assert config.headless is False


def test_resolve_site_prefers_cli_then_config():
    assert resolve_site("cn", AppConfig(default_site="global")) == "cn"
    assert resolve_site(None, AppConfig(default_site="global")) == "global"


def test_resolve_site_prompts_when_missing(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "global")
    assert resolve_site(None, AppConfig()) == "global"


def test_resolve_site_reprompts_until_valid(monkeypatch):
    answers = iter(["bad", "CN"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    assert resolve_site(None, AppConfig()) == "cn"


def test_resolve_input_dir_prefers_cli_then_config(tmp_path: Path):
    config = AppConfig(default_input_dir=str(tmp_path))
    other = tmp_path / "other"
    other.mkdir()
    assert resolve_input_dir(None, config) == tmp_path
    assert resolve_input_dir(str(other), config) == other


def test_resolve_input_dir_prompts_when_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: str(tmp_path))
    assert resolve_input_dir(None, AppConfig()) == tmp_path


def test_resolve_input_dir_rejects_missing_directory(tmp_path: Path):
    missing = tmp_path / "missing"

    try:
        resolve_input_dir(str(missing), AppConfig())
    except FileNotFoundError as exc:
        assert str(missing) in str(exc)
    else:
        raise AssertionError("resolve_input_dir should reject a missing directory")
