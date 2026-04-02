from contextlib import contextmanager
from pathlib import Path

from garmin_sync.onedrive_auth import ONEDRIVE_HOME_URL
from garmin_sync.onedrive_auth import OneDriveAuth


class FakePage:
    def __init__(self, redirect_url: str | None = None):
        self.url = ""
        self.redirect_url = redirect_url
        self.goto_calls: list[tuple[str, str | None]] = []

    def goto(self, url: str, wait_until: str | None = None):
        self.goto_calls.append((url, wait_until))
        self.url = self.redirect_url or url


def test_onedrive_auth_login_uses_browser_session(tmp_path: Path, monkeypatch):
    page = FakePage()
    calls = {}

    @contextmanager
    def fake_managed_page(site, data_dir, headless=False, accept_downloads=False):
        calls["site"] = site
        calls["data_dir"] = data_dir
        calls["headless"] = headless
        calls["accept_downloads"] = accept_downloads
        yield page

    monkeypatch.setattr("garmin_sync.onedrive_auth.managed_page", fake_managed_page)
    monkeypatch.setattr("builtins.input", lambda _: "")

    auth = OneDriveAuth(tmp_path)
    auth.login(headless=True)

    assert calls == {
        "site": "onedrive",
        "data_dir": tmp_path,
        "headless": True,
        "accept_downloads": False,
    }
    assert page.goto_calls == [(ONEDRIVE_HOME_URL, "domcontentloaded")]


def test_onedrive_auth_ensure_ready_prompts_after_login_redirect(monkeypatch):
    target_url = "https://onedrive.live.com/?id=%2FWorkouts"
    page = FakePage(redirect_url="https://login.live.com/")
    prompts: list[str] = []

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        page.redirect_url = None
        page.url = target_url
        return ""

    monkeypatch.setattr("builtins.input", fake_input)

    auth = OneDriveAuth(Path("/tmp/data"))
    auth.ensure_ready(page, target_url)

    assert prompts
    assert page.goto_calls[0] == (target_url, "domcontentloaded")
