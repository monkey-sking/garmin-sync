from pathlib import Path

from garmin_sync.models import UploadRecord
from garmin_sync.state import StateStore


def test_state_store_upserts_by_site_and_sha(tmp_path: Path):
    store = StateStore(tmp_path / "data")
    store.upsert(UploadRecord(site="cn", sha256="abc", file_path="/tmp/a.fit", file_name="a.fit"))
    store.upsert(
        UploadRecord(
            site="cn",
            sha256="abc",
            file_path="/tmp/b.fit",
            file_name="b.fit",
            status="success",
        )
    )
    records = store.list_records()
    assert len(records) == 1
    assert records[0].status == "success"
    assert records[0].file_name == "b.fit"


def test_state_store_filters_by_site_and_sha(tmp_path: Path):
    store = StateStore(tmp_path / "data")
    store.upsert(UploadRecord(site="cn", sha256="abc", file_path="/tmp/a.fit", file_name="a.fit"))
    store.upsert(UploadRecord(site="global", sha256="abc", file_path="/tmp/a.fit", file_name="a.fit"))
    assert store.get_by_key("cn", "abc") is not None
    assert store.get_by_key("global", "abc") is not None
