from contextlib import contextmanager
from pathlib import Path

from garmin_sync.browser import managed_page


ONEDRIVE_HOME_URL = "https://onedrive.live.com/"
LOGIN_URL_MARKERS = (
    "login.live.com",
    "login.microsoftonline.com",
    "account.live.com",
)


def _is_login_url(url: str) -> bool:
    lowered = url.lower()
    return any(marker in lowered for marker in LOGIN_URL_MARKERS)


class OneDriveAuth:
    def __init__(self, data_dir: Path):
        self._data_dir = data_dir

    @contextmanager
    def open_page(self, headless: bool = False, accept_downloads: bool = False):
        with managed_page(
            site="onedrive",
            data_dir=self._data_dir,
            headless=headless,
            accept_downloads=accept_downloads,
        ) as page:
            yield page

    def login(self, headless: bool = False) -> None:
        with self.open_page(headless=headless, accept_downloads=False) as page:
            page.goto(ONEDRIVE_HOME_URL, wait_until="domcontentloaded")
            input("Complete OneDrive login in the browser, then press Enter here: ")

    def ensure_ready(self, page, url: str) -> None:
        page.goto(url, wait_until="domcontentloaded")
        if not _is_login_url(getattr(page, "url", "")):
            return

        input("OneDrive session expired. Log in in the browser, then press Enter here: ")
        page.goto(url, wait_until="domcontentloaded")
        if _is_login_url(getattr(page, "url", "")):
            raise RuntimeError("OneDrive login was not completed. Run 'garmin-sync onedrive login' again.")
