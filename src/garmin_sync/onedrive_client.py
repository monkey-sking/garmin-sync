from pathlib import Path
from urllib.parse import parse_qs
from urllib.parse import unquote
from urllib.parse import urlparse
from urllib.request import Request
from urllib.request import urlopen

from garmin_sync.onedrive_auth import ONEDRIVE_HOME_URL
from garmin_sync.onedrive_models import OneDriveFolder


DOWNLOAD_BUTTON_SELECTORS = (
    "[aria-label='Download']",
    "[aria-label='下载']",
    "[aria-label*='Download']",
    "[aria-label*='下载']",
    "button:has-text('Download')",
    "button:has-text('下载')",
    "[role='button']:has-text('Download')",
    "[role='button']:has-text('下载')",
    "[role='menuitem']:has-text('Download')",
    "[role='menuitem']:has-text('下载')",
)
SELECT_ALL_SELECTORS = (
    "[aria-label*='Select all']",
    "[aria-label*='全选']",
    "button:has-text('Select all')",
    "button:has-text('全选')",
    "[role='button']:has-text('Select all')",
    "[role='button']:has-text('全选')",
)
EMPTY_FOLDER_MARKERS = ("this folder is empty", "folder is empty", "no items", "此文件夹为空", "没有项目")
FOLDER_READY_TIMEOUT_MS = 15000
FOLDER_READY_POLL_MS = 500


def _guess_folder_name_from_title(title: str) -> str:
    stripped = title.strip()
    if not stripped:
        return ""
    if stripped.lower() == "onedrive":
        return ""
    suffix = " - OneDrive"
    if stripped.endswith(suffix):
        return stripped[: -len(suffix)].strip()
    return stripped


def _guess_folder_name_from_url(url: str) -> str:
    parsed = urlparse(url)
    for key_value in parsed.query.split("&"):
        if "=" not in key_value:
            continue
        key, value = key_value.split("=", 1)
        if key != "id":
            continue
        parts = [part for part in unquote(value).split("/") if part]
        if parts:
            return parts[-1]
    path_parts = [part for part in unquote(parsed.path).split("/") if part]
    if path_parts:
        return path_parts[-1]
    return ""


def _normalize_archive_filename(name: str) -> str:
    candidate = name.strip() or "onedrive.zip"
    if candidate.lower().endswith(".zip"):
        return candidate
    return f"{candidate}.zip"


class OneDriveClient:
    def __init__(self, auth, headless: bool = False):
        self._auth = auth
        self._headless = headless

    def capture_selected_folder(self, initial_url: str | None = None) -> OneDriveFolder:
        with self._auth.open_page(headless=self._headless, accept_downloads=False) as page:
            current_url = getattr(page, "url", "")
            current_or_home = initial_url or _usable_start_url(current_url) or ONEDRIVE_HOME_URL
            self._auth.ensure_ready(page, current_or_home)
            input("Navigate to the OneDrive folder you want to sync, then press Enter here: ")
            name = _guess_folder_name_from_title(page.title()) or _guess_folder_name_from_url(page.url)
            return OneDriveFolder(url=page.url, name=name or "Selected Folder")

    def download_folder_archive(self, folder_url: str, archive_dir: Path) -> Path | None:
        archive_dir.mkdir(parents=True, exist_ok=True)
        with self._auth.open_page(headless=self._headless, accept_downloads=True) as page:
            self._auth.ensure_ready(page, folder_url)
            self._wait_for_folder_view(page)
            if self._is_empty_folder(page):
                return None

            select_all = self._locate_first(page, SELECT_ALL_SELECTORS)
            if select_all:
                select_all.click()

            download_button = self._locate_first(page, DOWNLOAD_BUTTON_SELECTORS)
            if not download_button:
                raise RuntimeError("Could not find the OneDrive download action for the selected folder.")

            archive_abort = lambda route: route.abort()
            page.route("**/transform/zip*", archive_abort)
            try:
                with page.expect_request(self._is_archive_request, timeout=10000) as request_context:
                    download_button.click()
                archive_request = request_context.value
            finally:
                page.unroute("**/transform/zip*", archive_abort)

            archive_path = archive_dir / _normalize_archive_filename(
                self._archive_filename_from_request_body(archive_request.post_data)
            )
            self._save_archive_from_request(
                request_url=archive_request.url,
                request_body=archive_request.post_data,
                archive_path=archive_path,
                referer=folder_url,
                user_agent=page.evaluate("navigator.userAgent"),
            )
            return archive_path

    def _is_empty_folder(self, page) -> bool:
        body = page.locator("body")
        if body.count() == 0:
            return False
        body_text = body.first.inner_text().lower()
        return any(marker in body_text for marker in EMPTY_FOLDER_MARKERS)

    def _wait_for_folder_view(self, page) -> None:
        elapsed_ms = 0
        while elapsed_ms < FOLDER_READY_TIMEOUT_MS:
            if self._is_folder_view_ready(page):
                return
            page.wait_for_timeout(FOLDER_READY_POLL_MS)
            elapsed_ms += FOLDER_READY_POLL_MS

        if self._is_folder_view_ready(page):
            return
        raise RuntimeError("OneDrive folder view did not finish loading.")

    def _is_folder_view_ready(self, page) -> bool:
        if self._is_empty_folder(page):
            return True
        return self._locate_first(page, DOWNLOAD_BUTTON_SELECTORS) is not None

    def _locate_first(self, page, selectors: tuple[str, ...]):
        for selector in selectors:
            locator = page.locator(selector)
            if locator.count() > 0:
                return locator.first
        return None

    def _is_archive_request(self, request) -> bool:
        return request.method == "POST" and "transform/zip" in request.url

    def _archive_filename_from_request_body(self, request_body: str | None) -> str:
        if not request_body:
            return "onedrive.zip"
        payload = parse_qs(request_body)
        names = payload.get("zipFileName")
        if not names:
            return "onedrive.zip"
        return names[0] or "onedrive.zip"

    def _save_archive_from_request(
        self,
        request_url: str,
        request_body: str | None,
        archive_path: Path,
        referer: str,
        user_agent: str,
    ) -> None:
        headers = {
            "Origin": "https://onedrive.live.com",
            "Referer": referer,
            "User-Agent": user_agent,
        }
        data = None
        if request_body is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
            data = request_body.encode()

        request = Request(request_url, data=data, headers=headers)
        with urlopen(request, timeout=120) as response, archive_path.open("wb") as archive_file:
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                archive_file.write(chunk)

        if not archive_path.exists() or archive_path.stat().st_size == 0:
            raise RuntimeError("OneDrive archive download was empty.")


def _usable_start_url(url: str) -> str:
    candidate = url.strip()
    if candidate in {"", "about:blank"}:
        return ""
    return candidate
