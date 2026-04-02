from contextlib import contextmanager
from pathlib import Path

from garmin_sync.aion_lease import maybe_with_aion_lease


def _load_playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on local setup
        raise RuntimeError(
            "Playwright is not installed. Run '.venv/bin/python -m pip install -e \".[dev]\"' first."
        ) from exc
    return sync_playwright


def get_storage_state_path(data_dir: Path, site: str) -> Path:
    path = data_dir / "playwright"
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{site}.json"


def get_browser_launch_kwargs(site: str, headless: bool) -> dict:
    return {
        "headless": headless,
        "channel": "chrome",
        "args": [
            "--disable-blink-features=AutomationControlled",
        ],
    }


def is_already_closed_error(exc: Exception) -> bool:
    return "target page, context or browser has been closed" in str(exc).lower()


def safe_playwright_close(closer) -> None:
    try:
        closer()
    except Exception as exc:
        if not is_already_closed_error(exc):
            raise


@contextmanager
def managed_page(site: str, data_dir: Path, headless: bool = False, accept_downloads: bool = False):
    sync_playwright = _load_playwright()
    storage_state_path = get_storage_state_path(data_dir, site)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(**get_browser_launch_kwargs(site, headless))
        context = None
        try:
            context_kwargs = {}
            if storage_state_path.exists():
                context_kwargs["storage_state"] = str(storage_state_path)

            context = browser.new_context(accept_downloads=accept_downloads, **context_kwargs)
            page = context.new_page()
            with maybe_with_aion_lease(site):
                try:
                    yield page
                    context.storage_state(path=str(storage_state_path))
                finally:
                    safe_playwright_close(context.close)
                    context = None
        finally:
            try:
                if context is not None:
                    safe_playwright_close(context.close)
            finally:
                safe_playwright_close(browser.close)
