import json
from pathlib import Path


class OneDriveStateStore:
    def __init__(self, data_dir: Path):
        self._data_dir = data_dir
        self._path = data_dir / "onedrive_state.json"

    def list_records(self) -> list[dict]:
        self._ensure_file()
        payload = json.loads(self._path.read_text() or "[]")
        return payload if isinstance(payload, list) else []

    def upsert(self, relative_path: str, remote_marker: str, local_path: str, folder_url: str) -> None:
        records = self.list_records()
        updated = []
        replaced = False

        for record in records:
            if record.get("relative_path") == relative_path:
                updated.append(
                    {
                        "relative_path": relative_path,
                        "remote_marker": remote_marker,
                        "local_path": local_path,
                        "folder_url": folder_url,
                    }
                )
                replaced = True
            else:
                updated.append(record)

        if not replaced:
            updated.append(
                {
                    "relative_path": relative_path,
                    "remote_marker": remote_marker,
                    "local_path": local_path,
                    "folder_url": folder_url,
                }
            )

        self._write(updated)

    def _ensure_file(self) -> None:
        self._data_dir.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.write_text("[]")

    def _write(self, records: list[dict]) -> None:
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(records, indent=2, sort_keys=True))
