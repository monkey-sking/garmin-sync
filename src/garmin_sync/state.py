import json
from pathlib import Path
from typing import Optional

from garmin_sync.models import UploadRecord


class StateStore:
    def __init__(self, data_dir: Path):
        self._data_dir = data_dir
        self._path = data_dir / "state.json"

    def list_records(self) -> list[UploadRecord]:
        self._ensure_file()
        payload = json.loads(self._path.read_text() or "[]")
        return [UploadRecord(**item) for item in payload]

    def get_by_key(self, site: str, sha256: str) -> Optional[UploadRecord]:
        for record in self.list_records():
            if record.site == site and record.sha256 == sha256:
                return record
        return None

    def upsert(self, record: UploadRecord) -> None:
        records = self.list_records()
        updated: list[UploadRecord] = []
        replaced = False

        for existing in records:
            if existing.site == record.site and existing.sha256 == record.sha256:
                updated.append(record)
                replaced = True
            else:
                updated.append(existing)

        if not replaced:
            updated.append(record)

        self._write(updated)

    def _ensure_file(self) -> None:
        self._data_dir.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.write_text("[]")

    def _write(self, records: list[UploadRecord]) -> None:
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps([record.to_dict() for record in records], indent=2, sort_keys=True))
