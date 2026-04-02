from pathlib import Path
import zipfile

from garmin_sync.onedrive_state import OneDriveStateStore
from garmin_sync.onedrive_sync import pull_fit_files


def write_zip(path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)


class ArchiveClient:
    def __init__(self, members: dict[str, bytes]):
        self.members = members
        self.calls = 0

    def download_folder_archive(self, folder_url: str, archive_dir: Path):
        del folder_url
        self.calls += 1
        archive_path = archive_dir / "workouts.zip"
        write_zip(archive_path, self.members)
        return archive_path


def test_pull_fit_files_extracts_nested_fit_files(tmp_path: Path):
    state_store = OneDriveStateStore(tmp_path / "data")
    client = ArchiveClient(
        {
            "2026/03/a.fit": b"abc",
            "notes.txt": b"skip",
        }
    )

    summary = pull_fit_files(
        client=client,
        folder_url="https://onedrive.live.com/?id=%2FWorkouts",
        folder_name="Workouts",
        download_dir=tmp_path,
        state_store=state_store,
        retry_limit=2,
    )

    assert summary.downloaded_count == 1
    assert summary.skipped_count == 0
    assert (tmp_path / "2026" / "03" / "a.fit").exists()


def test_pull_fit_files_skips_unchanged_files_on_second_run(tmp_path: Path):
    state_store = OneDriveStateStore(tmp_path / "data")
    client = ArchiveClient({"2026/03/a.fit": b"abc"})

    first = pull_fit_files(
        client=client,
        folder_url="https://onedrive.live.com/?id=%2FWorkouts",
        folder_name="Workouts",
        download_dir=tmp_path,
        state_store=state_store,
        retry_limit=2,
    )
    second = pull_fit_files(
        client=client,
        folder_url="https://onedrive.live.com/?id=%2FWorkouts",
        folder_name="Workouts",
        download_dir=tmp_path,
        state_store=state_store,
        retry_limit=2,
    )

    assert first.downloaded_count == 1
    assert second.downloaded_count == 0
    assert second.skipped_count == 1


class RetryableArchiveClient:
    def __init__(self):
        self.calls = 0

    def download_folder_archive(self, folder_url: str, archive_dir: Path):
        del folder_url
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("503 service unavailable")
        archive_path = archive_dir / "workouts.zip"
        write_zip(archive_path, {"a.fit": b"ok"})
        return archive_path


def test_pull_fit_files_retries_retryable_archive_download_errors(tmp_path: Path):
    state_store = OneDriveStateStore(tmp_path / "data")
    client = RetryableArchiveClient()

    summary = pull_fit_files(
        client=client,
        folder_url="https://onedrive.live.com/?id=%2FWorkouts",
        folder_name="Workouts",
        download_dir=tmp_path,
        state_store=state_store,
        retry_limit=2,
    )

    assert summary.downloaded_count == 1
    assert client.calls == 2


def test_pull_fit_files_reports_invalid_archive_member_paths(tmp_path: Path):
    state_store = OneDriveStateStore(tmp_path / "data")
    client = ArchiveClient(
        {
            "../escape.fit": b"bad",
            "safe.fit": b"ok",
        }
    )

    summary = pull_fit_files(
        client=client,
        folder_url="https://onedrive.live.com/?id=%2FWorkouts",
        folder_name="Workouts",
        download_dir=tmp_path,
        state_store=state_store,
        retry_limit=2,
    )

    assert summary.downloaded_count == 1
    assert summary.failed_count == 1
    assert any("escape.fit" in failure for failure in summary.failures)
    assert (tmp_path / "safe.fit").exists()
