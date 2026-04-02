from contextlib import contextmanager

from garmin_sync.browser import get_browser_launch_kwargs
from garmin_sync.browser import managed_page
from garmin_sync.browser import safe_playwright_close


def test_get_browser_launch_kwargs_prefers_system_chrome_for_onedrive():
    kwargs = get_browser_launch_kwargs("onedrive", headless=False)

    assert kwargs["headless"] is False
    assert kwargs["channel"] == "chrome"
    assert "--disable-blink-features=AutomationControlled" in kwargs["args"]


def test_get_browser_launch_kwargs_uses_system_chrome_for_garmin():
    kwargs = get_browser_launch_kwargs("cn", headless=True)

    assert kwargs["headless"] is True
    assert kwargs["channel"] == "chrome"
    assert "--disable-blink-features=AutomationControlled" in kwargs["args"]


def test_safe_playwright_close_ignores_already_closed_error():
    def closer():
        raise RuntimeError("Target page, context or browser has been closed")

    safe_playwright_close(closer)


def test_safe_playwright_close_reraises_other_errors():
    def closer():
        raise RuntimeError("different problem")

    try:
        safe_playwright_close(closer)
    except RuntimeError as exc:
        assert str(exc) == "different problem"
    else:
        raise AssertionError("Expected RuntimeError")


def test_managed_page_acquires_aion_lease_after_page_creation(tmp_path, monkeypatch):
    events = []

    class FakePage:
        pass

    class FakeContext:
        def new_page(self):
            events.append("new_page")
            return FakePage()

        def storage_state(self, path):
            events.append("storage_state")

        def close(self):
            events.append("context_close")

    class FakeBrowser:
        def new_context(self, **kwargs):
            events.append("new_context")
            return FakeContext()

        def close(self):
            events.append("browser_close")

    class FakeChromium:
        def launch(self, **kwargs):
            events.append("launch")
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    @contextmanager
    def fake_sync_playwright():
        events.append("playwright_enter")
        yield FakePlaywright()
        events.append("playwright_exit")

    @contextmanager
    def fake_aion_lease(site):
        events.append("lease_enter")
        yield None
        events.append("lease_exit")

    monkeypatch.setattr("garmin_sync.browser._load_playwright", lambda: fake_sync_playwright)
    monkeypatch.setattr("garmin_sync.browser.maybe_with_aion_lease", fake_aion_lease)

    with managed_page(site="cn", data_dir=tmp_path) as page:
        assert isinstance(page, FakePage)
        events.append("body")

    assert events.index("new_page") < events.index("lease_enter")
