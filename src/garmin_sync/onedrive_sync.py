from dataclasses import dataclass
from pathlib import Path
import zipfile


@dataclass(frozen=True)
class OneDriveArchiveFile:
    archive_member: str
    relative_path: str
    remote_marker: str


@dataclass
class PullSummary:
    downloaded_count: int
    skipped_count: int
    failed_count: int
    failures: list[str]

    def render(self) -> str:
        lines = [
            f"downloaded: {self.downloaded_count}",
            f"skipped: {self.skipped_count}",
            f"failed: {self.failed_count}",
        ]
        if self.failures:
            lines.append("failures:")
            lines.extend(f"- {failure}" for failure in self.failures)
        return "\n".join(lines)


def iter_archive_fit_files(archive_path: Path, folder_name: str) -> list[OneDriveArchiveFile]:
    with zipfile.ZipFile(archive_path) as archive:
        prefix = _common_root_prefix(archive.infolist(), folder_name)
        files: list[OneDriveArchiveFile] = []
        for member in archive.infolist():
            if member.is_dir():
                continue
            if member.filename.startswith("__MACOSX/"):
                continue
            if not member.filename.lower().endswith(".fit"):
                continue

            relative_path = _strip_prefix(member.filename, prefix)
            if not relative_path:
                relative_path = member.filename

            files.append(
                OneDriveArchiveFile(
                    archive_member=member.filename,
                    relative_path=relative_path,
                    remote_marker=f"{member.CRC}:{member.file_size}:{member.date_time}",
                )
            )
        return files


def filter_downloads(remote_files: list[OneDriveArchiveFile], existing_records: list[dict], download_dir: Path) -> list[OneDriveArchiveFile]:
    existing = {
        (record["relative_path"], record["remote_marker"]): record
        for record in existing_records
        if record.get("relative_path") and record.get("remote_marker")
    }
    queued: list[OneDriveArchiveFile] = []

    for item in remote_files:
        local_path = download_dir / item.relative_path
        if (item.relative_path, item.remote_marker) in existing and local_path.exists():
            continue
        queued.append(item)

    return queued


def pull_fit_files(client, folder_url: str, folder_name: str, download_dir: Path, state_store, retry_limit: int) -> PullSummary:
    download_dir.mkdir(parents=True, exist_ok=True)
    archive_dir = download_dir / ".onedrive-archives"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = _download_archive_with_retries(client, folder_url, archive_dir, retry_limit)
    if archive_path is None:
        return PullSummary(downloaded_count=0, skipped_count=0, failed_count=0, failures=[])

    try:
        remote_files = iter_archive_fit_files(archive_path, folder_name=folder_name)
        queued = filter_downloads(remote_files, state_store.list_records(), download_dir)

        downloaded_count = 0
        failures: list[str] = []
        with zipfile.ZipFile(archive_path) as archive:
            for item in queued:
                try:
                    destination = _destination_for(download_dir, item.relative_path)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(archive.read(item.archive_member))
                    state_store.upsert(
                        relative_path=item.relative_path,
                        remote_marker=item.remote_marker,
                        local_path=str(destination),
                        folder_url=folder_url,
                    )
                    downloaded_count += 1
                except Exception as exc:
                    failures.append(f"{Path(item.relative_path).name}: {exc}")

        return PullSummary(
            downloaded_count=downloaded_count,
            skipped_count=len(remote_files) - len(queued),
            failed_count=len(failures),
            failures=failures,
        )
    finally:
        if archive_path.exists():
            archive_path.unlink()


def _download_archive_with_retries(client, folder_url: str, archive_dir: Path, retry_limit: int) -> Path | None:
    last_error = None
    for _attempt in range(retry_limit):
        try:
            return client.download_folder_archive(folder_url, archive_dir)
        except Exception as exc:
            last_error = str(exc)
            if not _is_retryable_error(exc):
                break
    if last_error:
        raise RuntimeError(last_error)
    return None


def _common_root_prefix(members: list[zipfile.ZipInfo], folder_name: str) -> str:
    normalized_folder_name = folder_name.strip().lower()
    candidates = []
    for member in members:
        normalized = member.filename.strip("/")
        if not normalized or normalized.startswith("__MACOSX/"):
            continue
        parts = normalized.split("/", 1)
        if len(parts) == 2:
            candidates.append(parts[0])
    if not candidates:
        return ""
    first = candidates[0]
    if all(candidate == first for candidate in candidates) and first.strip().lower() == normalized_folder_name:
        return f"{first}/"
    return ""


def _strip_prefix(path: str, prefix: str) -> str:
    if prefix and path.startswith(prefix):
        return path[len(prefix):]
    return path


def _destination_for(download_dir: Path, relative_path: str) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise RuntimeError(f"Unsupported remote path: {relative_path}")
    return download_dir / relative


def _is_retryable_error(exc: Exception) -> bool:
    message = str(exc)
    return any(code in message for code in ("429", "500", "502", "503", "504"))
