from pathlib import Path

from garmin_sync.onedrive_state import OneDriveStateStore


def test_state_store_upserts_extracted_file_by_relative_path(tmp_path: Path):
    store = OneDriveStateStore(tmp_path / "data")
    store.upsert(
        relative_path="2026/03/a.fit",
        remote_marker="marker-1",
        local_path="/tmp/a.fit",
        folder_url="https://onedrive.live.com/?id=%2FWorkouts",
    )
    store.upsert(
        relative_path="2026/03/a.fit",
        remote_marker="marker-2",
        local_path="/tmp/a.fit",
        folder_url="https://onedrive.live.com/?id=%2FWorkouts",
    )

    records = store.list_records()

    assert len(records) == 1
    assert records[0]["relative_path"] == "2026/03/a.fit"
    assert records[0]["remote_marker"] == "marker-2"
