import hashlib
from pathlib import Path

from garmin_sync.models import UploadRecord

SUPPORTED_ACTIVITY_SUFFIXES = {".fit", ".gpx"}


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def scan_activity_files(directory: Path) -> list[UploadRecord]:
    records: list[UploadRecord] = []
    for path in sorted(p for p in directory.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_ACTIVITY_SUFFIXES):
        records.append(
            UploadRecord(
                site="",
                sha256=compute_sha256(path),
                file_path=str(path.resolve()),
                file_name=path.name,
            )
        )
    return records


def scan_fit_files(directory: Path) -> list[UploadRecord]:
    return scan_activity_files(directory)
