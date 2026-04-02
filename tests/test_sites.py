from garmin_sync.sites.base import GarminSiteAdapter


class FakeLocator:
    def __init__(self, count_value: int, inner_text_value: str = "", disabled: bool = False):
        self._count_value = count_value
        self._inner_text_value = inner_text_value
        self.uploaded_files: list[str] = []
        self.clicked = 0
        self.disabled = disabled

    @property
    def first(self):
        return self

    def count(self) -> int:
        return self._count_value

    def inner_text(self) -> str:
        return self._inner_text_value

    def set_input_files(self, file_path: str) -> None:
        self.uploaded_files.append(file_path)

    def click(self) -> None:
        self.clicked += 1

    def is_disabled(self) -> bool:
        return self.disabled


class FakePage:
    def __init__(self, auth_url: str = "https://connect.example.com/login") -> None:
        self.url = auth_url
        self.auth_url = auth_url
        self.goto_calls: list[str] = []
        self.wait_calls = 0

    def goto(self, url: str, wait_until: str = "domcontentloaded") -> None:
        self.goto_calls.append(url)
        if self.wait_calls < 2:
            self.url = self.auth_url
        else:
            self.url = url

    def locator(self, selector: str) -> FakeLocator:
        if selector == "input[type='file']" and self.url == "https://connect.example.com/modern/import-data":
            return FakeLocator(1)
        if selector == "body":
            return FakeLocator(1, "")
        return FakeLocator(0)

    def wait_for_timeout(self, timeout_ms: int) -> None:
        self.wait_calls += 1
        if self.wait_calls == 1:
            self.url = "https://connect.example.com/login"
        else:
            self.url = "https://connect.example.com/home"


class DelayedInputPage:
    def __init__(self) -> None:
        self.url = "about:blank"
        self.goto_calls: list[str] = []
        self.wait_calls = 0
        self.file_input = FakeLocator(0)
        self.submit_button = FakeLocator(1)

    def goto(self, url: str, wait_until: str = "domcontentloaded") -> None:
        del wait_until
        self.goto_calls.append(url)
        self.url = url

    def locator(self, selector: str) -> FakeLocator:
        if selector == "input[type='file']":
            self.file_input._count_value = 1 if self.wait_calls >= 2 else 0
            return self.file_input
        if selector == "button:has-text('导入数据')":
            self.submit_button.disabled = self.wait_calls < 4
            return self.submit_button
        if selector == "body":
            return FakeLocator(1, "")
        return FakeLocator(0)

    def wait_for_timeout(self, timeout_ms: int) -> None:
        del timeout_ms
        self.wait_calls += 1


class SecurityVerificationPage:
    def __init__(self) -> None:
        self.url = "https://sso.garmin.cn/portal/sso/en-US/sign-in"
        self.goto_calls: list[str] = []
        self.wait_calls = 0
        self.short_wait_calls = 0

    def goto(self, url: str, wait_until: str = "domcontentloaded") -> None:
        del wait_until
        self.goto_calls.append(url)

    def locator(self, selector: str) -> FakeLocator:
        if selector == "input[type='file']":
            if self.wait_calls >= 1:
                return FakeLocator(1)
            return FakeLocator(0)
        if selector == "body":
            if self.wait_calls == 0:
                return FakeLocator(
                    1,
                    "sso.garmin.cn\n正在进行安全验证\n本网站使用安全服务防护恶意自动程序。",
                )
            return FakeLocator(1, "")
        return FakeLocator(0)

    def wait_for_timeout(self, timeout_ms: int) -> None:
        if timeout_ms == 500:
            self.short_wait_calls += 1
            return
        self.wait_calls += 1
        if self.wait_calls >= 1:
            self.url = "https://connect.example.com/modern/import-data"


def test_ensure_login_does_not_interrupt_login_page(monkeypatch):
    adapter = GarminSiteAdapter(
        key="test",
        label="Test Garmin",
        import_url="https://connect.example.com/modern/import-data",
        file_input_selectors=("input[type='file']",),
        submit_button_selectors=(),
        success_markers=("success",),
        duplicate_markers=("duplicate",),
        failure_markers=("failed",),
    )
    page = FakePage()
    monotonic_values = iter([0, 1, 2, 3, 301])
    monkeypatch.setattr("garmin_sync.sites.base.time.monotonic", lambda: next(monotonic_values))

    adapter.ensure_login(page)

    assert page.goto_calls == [
        "https://connect.example.com/modern/import-data",
        "https://connect.example.com/modern/import-data",
    ]


def test_ensure_login_waits_through_oauth_urls(monkeypatch):
    adapter = GarminSiteAdapter(
        key="test",
        label="Test Garmin",
        import_url="https://connect.example.com/modern/import-data",
        file_input_selectors=("input[type='file']",),
        submit_button_selectors=(),
        success_markers=("success",),
        duplicate_markers=("duplicate",),
        failure_markers=("failed",),
    )
    page = FakePage(auth_url="https://auth.example.com/oauth/authorize")
    monotonic_values = iter([0, 1, 2, 3, 301])
    monkeypatch.setattr("garmin_sync.sites.base.time.monotonic", lambda: next(monotonic_values))

    adapter.ensure_login(page)

    assert page.goto_calls == [
        "https://connect.example.com/modern/import-data",
        "https://connect.example.com/modern/import-data",
    ]


def test_ensure_login_waits_for_delayed_upload_input(monkeypatch):
    adapter = GarminSiteAdapter(
        key="test",
        label="Test Garmin",
        import_url="https://connect.example.com/modern/import-data",
        file_input_selectors=("input[type='file']",),
        submit_button_selectors=(),
        success_markers=("success",),
        duplicate_markers=("duplicate",),
        failure_markers=("failed",),
    )
    page = DelayedInputPage()
    monotonic_values = iter([0, 1, 301])
    monkeypatch.setattr("garmin_sync.sites.base.time.monotonic", lambda: next(monotonic_values))

    adapter.ensure_login(page)

    assert page.goto_calls == ["https://connect.example.com/modern/import-data"]
    assert page.wait_calls == 2


def test_ensure_login_reports_security_verification_instead_of_login(monkeypatch, capsys):
    adapter = GarminSiteAdapter(
        key="test",
        label="Garmin China",
        import_url="https://connect.example.com/modern/import-data",
        file_input_selectors=("input[type='file']",),
        submit_button_selectors=(),
        success_markers=("success",),
        duplicate_markers=("duplicate",),
        failure_markers=("failed",),
    )
    page = SecurityVerificationPage()
    monotonic_values = iter([0, 1, 2, 301])
    monkeypatch.setattr("garmin_sync.sites.base.time.monotonic", lambda: next(monotonic_values))

    adapter.ensure_login(page)

    captured = capsys.readouterr()
    assert "security verification" in captured.out.lower()
    assert "login" not in captured.out.lower()
    assert page.goto_calls == ["https://connect.example.com/modern/import-data"]


def test_upload_file_waits_for_delayed_upload_input(monkeypatch):
    adapter = GarminSiteAdapter(
        key="test",
        label="Test Garmin",
        import_url="https://connect.example.com/modern/import-data",
        file_input_selectors=("input[type='file']",),
        submit_button_selectors=("button:has-text('导入数据')",),
        success_markers=("success",),
        duplicate_markers=("duplicate",),
        failure_markers=("failed",),
    )
    page = DelayedInputPage()
    monkeypatch.setattr(GarminSiteAdapter, "_wait_for_upload_result", lambda self, page: "success")

    outcome = adapter.upload_file(page, "/tmp/a.fit")

    assert outcome == "success"
    assert page.goto_calls == ["https://connect.example.com/modern/import-data"]
    assert page.wait_calls == 4
    assert page.file_input.uploaded_files == ["/tmp/a.fit"]
    assert page.submit_button.clicked == 1


def test_wait_for_upload_result_treats_chinese_duplicate_copy_as_duplicate(monkeypatch):
    adapter = GarminSiteAdapter(
        key="test",
        label="Test Garmin",
        import_url="https://connect.example.com/modern/import-data",
        file_input_selectors=("input[type='file']",),
        submit_button_selectors=(),
        success_markers=("成功",),
        duplicate_markers=("此文件已上传",),
        failure_markers=("失败",),
    )

    class ResultPage:
        def locator(self, selector: str) -> FakeLocator:
            if selector == "body":
                return FakeLocator(1, "2026-02-26-162357-HIIT-Watch.fit\n此文件已上传。")
            return FakeLocator(0)

        def wait_for_timeout(self, timeout_ms: int) -> None:
            del timeout_ms

    monotonic_values = iter([0, 1])
    monkeypatch.setattr("garmin_sync.sites.base.time.monotonic", lambda: next(monotonic_values))

    assert adapter._wait_for_upload_result(ResultPage()) == "skipped_duplicate"


def test_collect_status_text_keeps_body_text_when_alerts_exist():
    adapter = GarminSiteAdapter(
        key="test",
        label="Test Garmin",
        import_url="https://connect.example.com/modern/import-data",
        file_input_selectors=("input[type='file']",),
        submit_button_selectors=(),
        success_markers=("success",),
        duplicate_markers=("duplicate",),
        failure_markers=("failed",),
    )

    class AlertBodyPage:
        def locator(self, selector: str) -> FakeLocator:
            if selector == "[role='alert']":
                return FakeLocator(1, "toast only")
            if selector == "body":
                return FakeLocator(1, "body duplicate text")
            return FakeLocator(0)

    status_text = adapter._collect_status_text(AlertBodyPage())

    assert "toast only" in status_text
    assert "body duplicate text" in status_text
