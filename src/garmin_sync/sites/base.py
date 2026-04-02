import time
from dataclasses import dataclass

UPLOAD_INPUT_TIMEOUT_MS = 10000
UPLOAD_INPUT_POLL_MS = 500


@dataclass(frozen=True)
class GarminSiteAdapter:
    key: str
    label: str
    import_url: str
    file_input_selectors: tuple[str, ...]
    submit_button_selectors: tuple[str, ...]
    success_markers: tuple[str, ...]
    duplicate_markers: tuple[str, ...]
    failure_markers: tuple[str, ...]
    auth_markers: tuple[str, ...] = ("login", "signin", "sso", "oauth", "authorize", "mfa", "verify", "consent")
    security_verification_markers: tuple[str, ...] = (
        "security verification",
        "cloudflare",
        "正在进行安全验证",
        "恶意自动程序",
    )

    def ensure_login(self, page) -> None:
        deadline = time.monotonic() + 300
        prompted = False
        while time.monotonic() < deadline:
            if not prompted:
                page.goto(self.import_url, wait_until="domcontentloaded")
            if self._wait_for_upload_input(page):
                return
            if self._is_security_verification(page):
                if not prompted:
                    print(f"Complete security verification for {self.label} in the opened browser window.")
                    prompted = True
                page.wait_for_timeout(2000)
                continue

            current_url = getattr(page, "url", "").lower()
            if not prompted:
                print(f"Complete Garmin login for {self.label} in the opened browser window.")
                prompted = True
            elif not any(marker in current_url for marker in self.auth_markers):
                page.goto(self.import_url, wait_until="domcontentloaded")
                if self._wait_for_upload_input(page):
                    return

            page.wait_for_timeout(2000)
        raise TimeoutError(f"Timed out waiting for Garmin login on {self.label}")

    def upload_file(self, page, file_path: str) -> str:
        page.goto(self.import_url, wait_until="domcontentloaded")
        selector = self._wait_for_upload_input(page)
        if not selector:
            raise RuntimeError(f"Could not find a file input on {self.label}")

        page.locator(selector).first.set_input_files(file_path)
        submit_selector = self._wait_for_submit_selector(page)
        if submit_selector:
            page.locator(submit_selector).first.click()
        return self._wait_for_upload_result(page)

    def _has_upload_input(self, page) -> bool:
        return self._get_upload_selector(page) is not None

    def _get_upload_selector(self, page):
        for selector in self.file_input_selectors:
            locator = page.locator(selector).first
            if locator.count() > 0:
                return selector
        return None

    def _wait_for_upload_input(self, page):
        selector = self._get_upload_selector(page)
        elapsed_ms = 0
        while selector is None and elapsed_ms < UPLOAD_INPUT_TIMEOUT_MS:
            page.wait_for_timeout(UPLOAD_INPUT_POLL_MS)
            elapsed_ms += UPLOAD_INPUT_POLL_MS
            selector = self._get_upload_selector(page)
        return selector

    def _get_submit_selector(self, page):
        for selector in self.submit_button_selectors:
            locator = page.locator(selector).first
            if locator.count() > 0:
                return selector
        return None

    def _wait_for_submit_selector(self, page):
        if not self.submit_button_selectors:
            return None

        elapsed_ms = 0
        while elapsed_ms < UPLOAD_INPUT_TIMEOUT_MS:
            for selector in self.submit_button_selectors:
                locator = page.locator(selector).first
                if locator.count() > 0 and not locator.is_disabled():
                    return selector
            page.wait_for_timeout(UPLOAD_INPUT_POLL_MS)
            elapsed_ms += UPLOAD_INPUT_POLL_MS
        return None

    def _wait_for_upload_result(self, page) -> str:
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            status_text = self._collect_status_text(page)
            if any(marker in status_text for marker in self.duplicate_markers):
                return "skipped_duplicate"
            if any(marker in status_text for marker in self.success_markers):
                return "success"
            if any(marker in status_text for marker in self.failure_markers):
                raise RuntimeError(f"Garmin import failed on {self.label}")
            page.wait_for_timeout(1000)
        raise TimeoutError(f"Timed out waiting for upload result on {self.label}")

    def _collect_status_text(self, page) -> str:
        selectors = (
            "[role='alert']",
            "[aria-live='assertive']",
            "[aria-live='polite']",
            ".toast",
            ".notification",
            ".alert",
            ".banner",
        )
        chunks: list[str] = []
        for selector in selectors:
            locator = page.locator(selector)
            if locator.count() > 0:
                chunks.append(locator.first.inner_text().lower())

        body_text = page.locator("body").inner_text().lower()
        if chunks:
            return " ".join(chunks + [body_text])
        return body_text

    def _is_security_verification(self, page) -> bool:
        status_text = self._collect_status_text(page)
        return any(marker in status_text for marker in self.security_verification_markers)
