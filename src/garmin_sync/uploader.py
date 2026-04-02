from dataclasses import dataclass
from dataclasses import replace
from datetime import datetime
from datetime import timezone
from pathlib import Path

from garmin_sync.browser import managed_page
from garmin_sync.models import UploadRecord
from garmin_sync.scanner import scan_activity_files
from garmin_sync.sites import get_site_adapter
from garmin_sync.state import StateStore

EXPECTED_UPLOAD_OUTCOMES = {"success", "skipped_duplicate"}
SESSION_CLOSED_MARKERS = (
    "target page, context or browser has been closed",
    "browser has been closed",
    "context has been closed",
    "page has been closed",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def is_session_closed_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in SESSION_CLOSED_MARKERS)


@dataclass
class UploadSummary:
    scanned_count: int
    queued_count: int
    success_count: int
    duplicate_count: int
    failed_count: int
    failures: list[str]

    def render(self) -> str:
        lines = [
            f"scanned: {self.scanned_count}",
            f"queued: {self.queued_count}",
            f"success: {self.success_count}",
            f"duplicate: {self.duplicate_count}",
            f"failed: {self.failed_count}",
        ]
        if self.failures:
            lines.append("failures:")
            lines.extend(f"- {failure}" for failure in self.failures)
        return "\n".join(lines)


def filter_unsynced(site: str, scanned: list[UploadRecord], existing: list[UploadRecord]) -> list[UploadRecord]:
    completed = {
        (record.site, record.sha256)
        for record in existing
        if record.status in {"success", "skipped_duplicate"}
    }
    return [record for record in scanned if (site, record.sha256) not in completed]


def run_batch(site_adapter, browser, records: list[UploadRecord]) -> UploadSummary:
    summary = UploadSummary(
        scanned_count=len(records),
        queued_count=len(records),
        success_count=0,
        duplicate_count=0,
        failed_count=0,
        failures=[],
    )

    if records:
        site_adapter.ensure_login(browser)

    for record in records:
        try:
            result = site_adapter.upload_file(browser, record.file_path)
        except Exception as exc:
            summary.failed_count += 1
            summary.failures.append(f"{record.file_name}: {exc}")
            continue

        if result == "skipped_duplicate":
            summary.duplicate_count += 1
        else:
            summary.success_count += 1

    return summary


def run_login(site: str, data_dir: Path, headless: bool = False) -> None:
    adapter = get_site_adapter(site)
    with managed_page(site=site, data_dir=data_dir, headless=headless) as page:
        adapter.ensure_login(page)


def run_upload(site: str, directory: Path, data_dir: Path, headless: bool = False) -> UploadSummary:
    state_store = StateStore(data_dir)
    existing_records = state_store.list_records()
    scanned = [
        replace(record, site=site)
        for record in scan_activity_files(directory)
    ]
    queued = filter_unsynced(site, scanned, existing_records)
    adapter = get_site_adapter(site)

    summary = UploadSummary(
        scanned_count=len(scanned),
        queued_count=len(queued),
        success_count=0,
        duplicate_count=0,
        failed_count=0,
        failures=[],
    )

    if not queued:
        return summary

    with managed_page(site=site, data_dir=data_dir, headless=headless) as page:
        adapter.ensure_login(page)
        for record in queued:
            existing = state_store.get_by_key(site, record.sha256)
            first_seen_at = existing.first_seen_at if existing and existing.first_seen_at else now_iso()
            try:
                outcome = None
                last_error = None
                for _attempt in range(2):
                    try:
                        outcome = adapter.upload_file(page, record.file_path)
                        break
                    except Exception as exc:
                        last_error = str(exc)
                        if is_session_closed_error(exc):
                            break
                if outcome is None:
                    raise RuntimeError(last_error or "Upload failed")
                if outcome not in EXPECTED_UPLOAD_OUTCOMES:
                    raise RuntimeError(f"Unexpected upload outcome: {outcome}")

                persisted = replace(
                    record,
                    first_seen_at=first_seen_at,
                    status=outcome,
                    last_attempt_at=now_iso(),
                    last_error=None,
                )
                state_store.upsert(persisted)
                if outcome == "skipped_duplicate":
                    summary.duplicate_count += 1
                else:
                    summary.success_count += 1
            except Exception as exc:
                failed_record = replace(
                    record,
                    first_seen_at=first_seen_at,
                    status="failed",
                    last_attempt_at=now_iso(),
                    last_error=str(exc),
                )
                state_store.upsert(failed_record)
                summary.failed_count += 1
                summary.failures.append(f"{record.file_name}: {exc}")
                if is_session_closed_error(exc):
                    summary.failures.append("Upload session closed. Stopped batch; rerun upload after logging in again.")
                    break

    return summary
