from contextlib import contextmanager
from pathlib import Path

from garmin_sync.onedrive_auth import ONEDRIVE_HOME_URL
from garmin_sync.onedrive_client import OneDriveClient


class FakeLocator:
    def __init__(self, count: int = 0, text: str = ""):
        self._count = count
        self._text = text
        self.clicked = 0

    @property
    def first(self):
        return self

    def count(self) -> int:
        return self._count

    def click(self) -> None:
        self.clicked += 1

    def inner_text(self) -> str:
        return self._text


class FakeDownload:
    def __init__(self, suggested_filename: str = "workouts.zip", payload: bytes = b"zip"):
        self.suggested_filename = suggested_filename
        self.payload = payload
        self.saved_as: str | None = None

    def save_as(self, path: str) -> None:
        Path(path).write_bytes(self.payload)
        self.saved_as = path

    def cancel(self) -> None:
        return None


class FakeRequest:
    def __init__(
        self,
        url: str = "https://example.test/transform/zip?cs=fFNQTw",
        method: str = "POST",
        post_data: str | None = "zipFileName=workouts.zip",
    ):
        self.url = url
        self.method = method
        self.post_data = post_data


class FakeDownloadContext:
    def __init__(self, download: FakeDownload):
        self.value = download

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeRequestContext:
    def __init__(self, request: FakeRequest):
        self.value = request

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakePage:
    def __init__(
        self,
        url: str,
        title_text: str,
        locators: dict[str, FakeLocator] | None = None,
        locator_sequences: dict[str, list[FakeLocator]] | None = None,
        title_sequence: list[str] | None = None,
        request: FakeRequest | None = None,
        user_agent: str = "FakeBrowser/1.0",
    ):
        self.url = url
        self._title_text = title_text
        self._locators = locators or {}
        self._locator_sequences = locator_sequences or {}
        self._title_sequence = title_sequence or []
        self._request = request or FakeRequest()
        self._user_agent = user_agent
        self._wait_calls = 0
        self.goto_calls: list[tuple[str, str | None]] = []
        self.download = FakeDownload()

    def goto(self, url: str, wait_until: str | None = None):
        self.goto_calls.append((url, wait_until))
        self.url = url

    def title(self) -> str:
        if self._title_sequence:
            index = min(self._wait_calls, len(self._title_sequence) - 1)
            return self._title_sequence[index]
        return self._title_text

    def locator(self, selector: str) -> FakeLocator:
        if selector in self._locator_sequences:
            sequence = self._locator_sequences[selector]
            index = min(self._wait_calls, len(sequence) - 1)
            return sequence[index]
        return self._locators.get(selector, FakeLocator())

    def wait_for_timeout(self, timeout_ms: int) -> None:
        del timeout_ms
        self._wait_calls += 1

    def expect_download(self, timeout: int):
        del timeout
        return FakeDownloadContext(self.download)

    def expect_request(self, predicate, timeout: int):
        del timeout
        assert predicate(self._request)
        return FakeRequestContext(self._request)

    def route(self, pattern: str, handler):
        del pattern
        del handler

    def unroute(self, pattern: str, handler):
        del pattern
        del handler

    def evaluate(self, expression: str):
        if expression == "navigator.userAgent":
            return self._user_agent
        raise AssertionError(f"Unexpected evaluate expression: {expression}")


class FakeAuth:
    def __init__(self, page: FakePage):
        self.page = page
        self.open_calls: list[tuple[bool, bool]] = []
        self.ready_calls: list[str] = []

    @contextmanager
    def open_page(self, headless: bool = False, accept_downloads: bool = False):
        self.open_calls.append((headless, accept_downloads))
        yield self.page

    def ensure_ready(self, page, url: str):
        self.ready_calls.append(url)
        page.goto(url, wait_until="domcontentloaded")


def test_capture_selected_folder_uses_current_page_title(monkeypatch):
    page = FakePage(
        url="https://onedrive.live.com/",
        title_text="Workouts - OneDrive",
    )
    client = OneDriveClient(FakeAuth(page), headless=True)

    def fake_input(prompt: str) -> str:
        del prompt
        page.url = "https://onedrive.live.com/?id=%2FWorkouts"
        return ""

    monkeypatch.setattr("builtins.input", fake_input)

    selected = client.capture_selected_folder()

    assert selected.url == "https://onedrive.live.com/?id=%2FWorkouts"
    assert selected.name == "Workouts"


def test_capture_selected_folder_falls_back_to_url_segment(monkeypatch):
    page = FakePage(
        url="https://onedrive.live.com/",
        title_text="OneDrive",
    )
    client = OneDriveClient(FakeAuth(page))

    def fake_input(prompt: str) -> str:
        del prompt
        page.url = "https://onedrive.live.com/?id=%2FArchive%2FMarch"
        return ""

    monkeypatch.setattr("builtins.input", fake_input)

    selected = client.capture_selected_folder()

    assert selected.name == "March"


def test_capture_selected_folder_uses_home_when_playwright_starts_on_about_blank(monkeypatch):
    page = FakePage(
        url="about:blank",
        title_text="OneDrive",
    )
    auth = FakeAuth(page)
    client = OneDriveClient(auth)

    def fake_input(prompt: str) -> str:
        del prompt
        page.url = "https://onedrive.live.com/?id=%2FArchive%2FMarch"
        return ""

    monkeypatch.setattr("builtins.input", fake_input)

    selected = client.capture_selected_folder()

    assert auth.ready_calls == [ONEDRIVE_HOME_URL]
    assert selected.url == "https://onedrive.live.com/?id=%2FArchive%2FMarch"


def test_download_folder_archive_selects_all_and_saves_zip(tmp_path: Path):
    select_all = FakeLocator(count=1)
    download_button = FakeLocator(count=1)
    page = FakePage(
        url="https://onedrive.live.com/?id=%2FWorkouts",
        title_text="Workouts - OneDrive",
        locators={
            "body": FakeLocator(count=1, text="共享\n下载\n修改时间"),
            "[aria-label*='Select all']": select_all,
            "[aria-label='Download']": download_button,
        },
    )
    auth = FakeAuth(page)
    client = OneDriveClient(auth)
    saved_calls = []

    def fake_save_archive_from_request(request_url, request_body, archive_path, referer, user_agent):
        saved_calls.append((request_url, request_body, archive_path, referer, user_agent))
        archive_path.write_bytes(b"zip")

    client._save_archive_from_request = fake_save_archive_from_request

    archive_path = client.download_folder_archive("https://onedrive.live.com/?id=%2FWorkouts", tmp_path)

    assert archive_path == tmp_path / "workouts.zip"
    assert archive_path.exists()
    assert auth.open_calls == [(False, True)]
    assert select_all.clicked == 1
    assert download_button.clicked == 1
    assert saved_calls == [
        (
            "https://example.test/transform/zip?cs=fFNQTw",
            "zipFileName=workouts.zip",
            tmp_path / "workouts.zip",
            "https://onedrive.live.com/?id=%2FWorkouts",
            "FakeBrowser/1.0",
        )
    ]


def test_download_folder_archive_supports_menuitem_download_action(tmp_path: Path):
    download_button = FakeLocator(count=1)
    page = FakePage(
        url="https://onedrive.live.com/?id=%2FWorkouts",
        title_text="Workouts - OneDrive",
        locators={
            "body": FakeLocator(count=1, text="共享\n下载\n修改时间"),
            "[role='menuitem']:has-text('下载')": download_button,
        },
    )
    auth = FakeAuth(page)
    client = OneDriveClient(auth)
    client._save_archive_from_request = lambda request_url, request_body, archive_path, referer, user_agent: archive_path.write_bytes(
        b"zip"
    )

    archive_path = client.download_folder_archive("https://onedrive.live.com/?id=%2FWorkouts", tmp_path)

    assert archive_path == tmp_path / "workouts.zip"
    assert download_button.clicked == 1


def test_download_folder_archive_waits_for_folder_view_before_locating_actions(tmp_path: Path):
    select_all_early = FakeLocator(count=0)
    select_all_ready = FakeLocator(count=1)
    download_early = FakeLocator(count=0)
    download_ready = FakeLocator(count=1)
    page = FakePage(
        url="https://onedrive.live.com/?id=%2FWorkouts",
        title_text="Microsoft OneDrive",
        locator_sequences={
            "body": [FakeLocator(count=1, text=""), FakeLocator(count=1, text="共享\n下载\n修改时间")],
            "[aria-label*='Select all']": [select_all_early, select_all_ready],
            "[aria-label='Download']": [download_early, download_early],
            "[role='menuitem']:has-text('下载')": [download_early, download_ready],
        },
        title_sequence=["Microsoft OneDrive", "Workouts - OneDrive"],
    )
    auth = FakeAuth(page)
    client = OneDriveClient(auth)
    client._save_archive_from_request = lambda request_url, request_body, archive_path, referer, user_agent: archive_path.write_bytes(
        b"zip"
    )

    archive_path = client.download_folder_archive("https://onedrive.live.com/?id=%2FWorkouts", tmp_path)

    assert archive_path == tmp_path / "workouts.zip"
    assert page._wait_calls >= 1
    assert select_all_ready.clicked == 1
    assert download_ready.clicked == 1


def test_download_folder_archive_returns_none_for_empty_folder(tmp_path: Path):
    page = FakePage(
        url="https://onedrive.live.com/?id=%2FEmpty",
        title_text="Empty - OneDrive",
        locators={"body": FakeLocator(count=1, text="This folder is empty.")},
    )
    client = OneDriveClient(FakeAuth(page))

    archive_path = client.download_folder_archive("https://onedrive.live.com/?id=%2FEmpty", tmp_path)

    assert archive_path is None


def test_save_archive_from_request_streams_response_to_disk(tmp_path: Path, monkeypatch):
    client = OneDriveClient(auth=None)
    archive_path = tmp_path / "workouts.zip"
    captured = {}

    class FakeResponse:
        def __init__(self):
            self._chunks = [b"zip", b"-data", b""]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, _size: int):
            return self._chunks.pop(0)

    def fake_urlopen(request, timeout: int):
        captured["url"] = request.full_url
        captured["data"] = request.data
        captured["headers"] = dict(request.header_items())
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("garmin_sync.onedrive_client.urlopen", fake_urlopen)

    client._save_archive_from_request(
        request_url="https://example.test/transform/zip?cs=fFNQTw",
        request_body="zipFileName=workouts.zip",
        archive_path=archive_path,
        referer="https://onedrive.live.com/?id=%2FWorkouts",
        user_agent="FakeBrowser/1.0",
    )

    assert archive_path.read_bytes() == b"zip-data"
    assert captured == {
        "url": "https://example.test/transform/zip?cs=fFNQTw",
        "data": b"zipFileName=workouts.zip",
        "headers": {
            "Origin": "https://onedrive.live.com",
            "Referer": "https://onedrive.live.com/?id=%2FWorkouts",
            "User-agent": "FakeBrowser/1.0",
            "Content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        },
        "timeout": 120,
    }


def test_archive_filename_from_request_body_uses_zip_file_name():
    client = OneDriveClient(auth=None)

    assert client._archive_filename_from_request_body("zipFileName=HealthFit.zip&guid=abc") == "HealthFit.zip"
    assert client._archive_filename_from_request_body("") == "onedrive.zip"
