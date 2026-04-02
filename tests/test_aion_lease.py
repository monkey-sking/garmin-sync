import json
import socket
import threading
from pathlib import Path
from uuid import uuid4

from garmin_sync.aion_lease import AionLeaseClient
from garmin_sync.aion_lease import detect_playwright_chrome_profile_app_key
from garmin_sync.aion_lease import resolve_aion_app_key_candidates


def _send_line(file_obj, payload: dict) -> None:
    file_obj.write(json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n")
    file_obj.flush()


def _read_line(file_obj) -> dict:
    return json.loads(file_obj.readline().decode("utf-8"))


class FakeAionServer:
    def __init__(self, socket_path: Path, handler):
        self.socket_path = socket_path
        self.handler = handler
        self.received: list[dict] = []
        self.error: Exception | None = None
        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._server.bind(str(self.socket_path))
        self._server.listen(1)
        self._thread.start()

    def stop(self) -> None:
        try:
            self._server.close()
        except Exception:
            pass
        self._thread.join(timeout=2)
        if self.error is not None:
            raise self.error

    def _run(self) -> None:
        try:
            conn, _ = self._server.accept()
            with conn:
                file_obj = conn.makefile("rwb", buffering=0)
                with file_obj:
                    self.handler(file_obj, self.received)
        except Exception as exc:
            self.error = exc


def make_short_socket_path() -> Path:
    return Path("/tmp") / f"aion-{uuid4().hex[:8]}.sock"


def test_aion_lease_client_completes_handshake_begin_and_end(tmp_path):
    socket_path = make_short_socket_path()

    def handler(file_obj, received):
        hello = _read_line(file_obj)
        received.append(hello)
        assert hello["action"] == "session.hello"
        _send_line(file_obj, {"action": "session.ready", "protocolVersion": 1})

        begin = _read_line(file_obj)
        received.append(begin)
        assert begin["action"] == "lease.begin"
        _send_line(file_obj, {"requestId": begin["requestId"], "code": "accepted", "effectiveLeaseSeconds": 1800})

        end = _read_line(file_obj)
        received.append(end)
        assert end["action"] == "lease.end"
        _send_line(file_obj, {"requestId": end["requestId"], "code": "accepted", "effectiveLeaseSeconds": None})

    server = FakeAionServer(socket_path, handler)
    server.start()

    client = AionLeaseClient(
        socket_path=socket_path,
        holder_id="agent.one",
        client_name="garmin-sync:test",
        app_key="com.google.Chrome",
        renew_interval_seconds=999,
    )
    client.start()
    client.close()

    try:
        server.stop()
        assert [payload["action"] for payload in server.received] == [
            "session.hello",
            "lease.begin",
            "lease.end",
        ]
    finally:
        socket_path.unlink(missing_ok=True)


def test_aion_lease_client_replies_to_close_check_with_extend_lease(tmp_path):
    socket_path = make_short_socket_path()
    close_check_reply = {}
    reply_seen = threading.Event()

    def handler(file_obj, received):
        hello = _read_line(file_obj)
        received.append(hello)
        _send_line(file_obj, {"action": "session.ready", "protocolVersion": 1})

        begin = _read_line(file_obj)
        received.append(begin)
        _send_line(file_obj, {"requestId": begin["requestId"], "code": "accepted", "effectiveLeaseSeconds": 1800})

        _send_line(
            file_obj,
            {
                "action": "lease.can_close.request",
                "requestId": "close-1",
                "holderId": hello["holderId"],
                "appKey": "com.google.Chrome",
                "timeoutSeconds": 3,
            },
        )

        reply = _read_line(file_obj)
        close_check_reply.update(reply)
        reply_seen.set()
        _send_line(file_obj, {"requestId": reply["requestId"], "code": "accepted", "effectiveLeaseSeconds": 1800})

        end = _read_line(file_obj)
        received.append(end)
        _send_line(file_obj, {"requestId": end["requestId"], "code": "accepted", "effectiveLeaseSeconds": None})

    server = FakeAionServer(socket_path, handler)
    server.start()

    client = AionLeaseClient(
        socket_path=socket_path,
        holder_id="agent.one",
        client_name="garmin-sync:test",
        app_key="com.google.Chrome",
        renew_interval_seconds=999,
    )
    client.start()
    assert reply_seen.wait(timeout=2)
    client.close()

    try:
        server.stop()
        assert close_check_reply["action"] == "lease.can_close.reply"
        assert close_check_reply["result"] == "extend_lease"
        assert close_check_reply["leaseSeconds"] == 1800
    finally:
        socket_path.unlink(missing_ok=True)


def test_aion_lease_client_falls_back_to_profile_app_key_on_unknown_app(tmp_path):
    socket_path = make_short_socket_path()
    begin_keys = []

    def handler(file_obj, received):
        hello = _read_line(file_obj)
        received.append(hello)
        _send_line(file_obj, {"action": "session.ready", "protocolVersion": 1})

        first_begin = _read_line(file_obj)
        begin_keys.append(first_begin["appKey"])
        _send_line(file_obj, {"requestId": first_begin["requestId"], "code": "unknown_app", "effectiveLeaseSeconds": None})

        second_begin = _read_line(file_obj)
        begin_keys.append(second_begin["appKey"])
        _send_line(file_obj, {"requestId": second_begin["requestId"], "code": "accepted", "effectiveLeaseSeconds": 1800})

        end = _read_line(file_obj)
        received.append(end)
        _send_line(file_obj, {"requestId": end["requestId"], "code": "accepted", "effectiveLeaseSeconds": None})

    server = FakeAionServer(socket_path, handler)
    server.start()

    client = AionLeaseClient(
        socket_path=socket_path,
        holder_id="agent.one",
        client_name="garmin-sync:test",
        app_key="com.google.Chrome",
        app_key_candidates=["com.google.Chrome", "com.google.Chrome#profile:playwright_chromiumdev_profile-abc"],
        renew_interval_seconds=999,
    )
    client.start()
    client.close()

    try:
        server.stop()
        assert begin_keys == [
            "com.google.Chrome",
            "com.google.Chrome#profile:playwright_chromiumdev_profile-abc",
        ]
        assert client.app_key == "com.google.Chrome#profile:playwright_chromiumdev_profile-abc"
    finally:
        socket_path.unlink(missing_ok=True)


def test_detect_playwright_chrome_profile_app_key(monkeypatch):
    output = "\n".join(
        [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --user-data-dir=/tmp/other",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --user-data-dir=/tmp/playwright_chromiumdev_profile-xyz --remote-debugging-pipe",
        ]
    )
    monkeypatch.setattr("garmin_sync.aion_lease.subprocess.check_output", lambda *args, **kwargs: output)

    app_key = detect_playwright_chrome_profile_app_key()

    assert app_key == "com.google.Chrome#profile:playwright_chromiumdev_profile-xyz"


def test_resolve_aion_app_key_candidates_prefers_detected_profile(monkeypatch):
    monkeypatch.setattr(
        "garmin_sync.aion_lease.detect_playwright_chrome_profile_app_key",
        lambda: "com.google.Chrome#profile:playwright_chromiumdev_profile-xyz",
    )

    candidates = resolve_aion_app_key_candidates()

    assert candidates == [
        "com.google.Chrome#profile:playwright_chromiumdev_profile-xyz",
        "com.google.Chrome",
        "com.google.Chrome#automation",
    ]


def test_aion_lease_client_retries_unknown_app_until_aion_recognizes_browser(tmp_path, monkeypatch):
    socket_path = make_short_socket_path()
    begin_attempts = 0

    def handler(file_obj, received):
        nonlocal begin_attempts
        hello = _read_line(file_obj)
        received.append(hello)
        _send_line(file_obj, {"action": "session.ready", "protocolVersion": 1})

        for _ in range(2):
            begin = _read_line(file_obj)
            begin_attempts += 1
            _send_line(file_obj, {"requestId": begin["requestId"], "code": "unknown_app", "effectiveLeaseSeconds": None})

        accepted_begin = _read_line(file_obj)
        begin_attempts += 1
        _send_line(file_obj, {"requestId": accepted_begin["requestId"], "code": "accepted", "effectiveLeaseSeconds": 1800})

        end = _read_line(file_obj)
        received.append(end)
        _send_line(file_obj, {"requestId": end["requestId"], "code": "accepted", "effectiveLeaseSeconds": None})

    server = FakeAionServer(socket_path, handler)
    server.start()
    monkeypatch.setattr("garmin_sync.aion_lease.AION_BEGIN_RETRY_INTERVAL_SECONDS", 0.01)

    client = AionLeaseClient(
        socket_path=socket_path,
        holder_id="agent.one",
        client_name="garmin-sync:test",
        app_key="com.google.Chrome#profile:playwright_chromiumdev_profile-abc",
        app_key_candidates=["com.google.Chrome#profile:playwright_chromiumdev_profile-abc"],
        renew_interval_seconds=999,
    )
    client.start()
    client.close()

    try:
        server.stop()
        assert begin_attempts == 3
    finally:
        socket_path.unlink(missing_ok=True)
