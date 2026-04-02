from contextlib import contextmanager

from garmin_sync.models import UploadRecord
from garmin_sync.state import StateStore
from garmin_sync.uploader import filter_unsynced
from garmin_sync.uploader import run_batch
from garmin_sync.uploader import run_upload
from garmin_sync.uploader import UploadSummary


def test_filter_unsynced_skips_existing_successes():
    scanned = [UploadRecord(site="", sha256="abc", file_path="/tmp/a.fit", file_name="a.fit")]
    existing = [UploadRecord(site="cn", sha256="abc", file_path="/tmp/a.fit", file_name="a.fit", status="success")]

    remaining = filter_unsynced("cn", scanned, existing)

    assert remaining == []


def test_filter_unsynced_keeps_records_for_other_sites():
    scanned = [UploadRecord(site="", sha256="abc", file_path="/tmp/a.fit", file_name="a.fit")]
    existing = [UploadRecord(site="global", sha256="abc", file_path="/tmp/a.fit", file_name="a.fit", status="success")]

    remaining = filter_unsynced("cn", scanned, existing)

    assert len(remaining) == 1


class FakeSite:
    key = "cn"

    def ensure_login(self, browser) -> None:
        browser.append("login")

    def upload_file(self, browser, file_path: str) -> str:
        browser.append(file_path)
        return "success"


def test_run_batch_calls_login_once_and_uploads_each_file():
    browser = []
    records = [
        UploadRecord(site="cn", sha256="a", file_path="/tmp/a.fit", file_name="a.fit"),
        UploadRecord(site="cn", sha256="b", file_path="/tmp/b.fit", file_name="b.fit"),
    ]

    summary = run_batch(FakeSite(), browser, records)

    assert browser == ["login", "/tmp/a.fit", "/tmp/b.fit"]
    assert summary.success_count == 2
    assert summary.failed_count == 0


def test_upload_summary_render_reports_counts():
    summary = UploadSummary(
        scanned_count=3,
        queued_count=2,
        success_count=2,
        duplicate_count=1,
        failed_count=0,
        failures=[],
    )

    output = summary.render()

    assert "scanned: 3" in output.lower()
    assert "queued: 2" in output.lower()
    assert "success: 2" in output.lower()
    assert "duplicate: 1" in output.lower()


class RetrySite:
    key = "cn"

    def __init__(self) -> None:
        self.calls = 0

    def ensure_login(self, page) -> None:
        page.append("login")

    def upload_file(self, page, file_path: str) -> str:
        self.calls += 1
        page.append(file_path)
        if self.calls == 1:
            raise RuntimeError("temporary")
        return "success"


def test_run_upload_preserves_first_seen_at_and_retries_once(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    state_store = StateStore(data_dir)
    state_store.upsert(
        UploadRecord(
            site="cn",
            sha256="abc",
            file_path="/tmp/a.fit",
            file_name="a.fit",
            status="failed",
            first_seen_at="2026-03-01T00:00:00Z",
        )
    )

    monkeypatch.setattr(
        "garmin_sync.uploader.scan_activity_files",
        lambda directory: [UploadRecord(site="", sha256="abc", file_path="/tmp/a.fit", file_name="a.fit")],
    )
    site = RetrySite()
    monkeypatch.setattr("garmin_sync.uploader.get_site_adapter", lambda name: site)

    @contextmanager
    def fake_managed_page(site: str, data_dir, headless: bool = False):
        yield []

    monkeypatch.setattr("garmin_sync.uploader.managed_page", fake_managed_page)

    summary = run_upload(site="cn", directory=tmp_path, data_dir=data_dir, headless=False)
    persisted = StateStore(data_dir).get_by_key("cn", "abc")

    assert summary.success_count == 1
    assert summary.failed_count == 0
    assert persisted is not None
    assert persisted.first_seen_at == "2026-03-01T00:00:00Z"
    assert site.calls == 2


class UnexpectedOutcomeSite:
    key = "cn"

    def ensure_login(self, page) -> None:
        page.append("login")

    def upload_file(self, page, file_path: str) -> str:
        return "weird-status"


def test_run_upload_rejects_unexpected_adapter_status(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"

    monkeypatch.setattr(
        "garmin_sync.uploader.scan_activity_files",
        lambda directory: [UploadRecord(site="", sha256="abc", file_path="/tmp/a.fit", file_name="a.fit")],
    )
    monkeypatch.setattr("garmin_sync.uploader.get_site_adapter", lambda name: UnexpectedOutcomeSite())

    @contextmanager
    def fake_managed_page(site: str, data_dir, headless: bool = False):
        yield []

    monkeypatch.setattr("garmin_sync.uploader.managed_page", fake_managed_page)

    summary = run_upload(site="cn", directory=tmp_path, data_dir=data_dir, headless=False)
    persisted = StateStore(data_dir).get_by_key("cn", "abc")

    assert summary.success_count == 0
    assert summary.failed_count == 1
    assert persisted is not None
    assert persisted.status == "failed"
    assert "Unexpected upload outcome" in persisted.last_error


class ClosingSite:
    key = "cn"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def ensure_login(self, page) -> None:
        page.append("login")

    def upload_file(self, page, file_path: str) -> str:
        self.calls.append(file_path)
        raise RuntimeError("Page.goto: Target page, context or browser has been closed")


def test_run_upload_stops_batch_after_session_closed_error(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    records = [
        UploadRecord(site="", sha256="a", file_path="/tmp/a.fit", file_name="a.fit"),
        UploadRecord(site="", sha256="b", file_path="/tmp/b.fit", file_name="b.fit"),
    ]

    monkeypatch.setattr("garmin_sync.uploader.scan_activity_files", lambda directory: records)
    site = ClosingSite()
    monkeypatch.setattr("garmin_sync.uploader.get_site_adapter", lambda name: site)

    @contextmanager
    def fake_managed_page(site: str, data_dir, headless: bool = False):
        yield []

    monkeypatch.setattr("garmin_sync.uploader.managed_page", fake_managed_page)

    summary = run_upload(site="cn", directory=tmp_path, data_dir=data_dir, headless=False)
    persisted_a = StateStore(data_dir).get_by_key("cn", "a")
    persisted_b = StateStore(data_dir).get_by_key("cn", "b")

    assert site.calls == ["/tmp/a.fit"]
    assert summary.failed_count == 1
    assert "Upload session closed" in summary.failures[-1]
    assert persisted_a is not None
    assert persisted_a.status == "failed"
    assert persisted_b is None
