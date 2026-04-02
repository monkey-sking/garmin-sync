import json
import os
import re
import socket
import subprocess
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from queue import Queue
from queue import Empty

AION_SOCKET_PATH = Path.home() / "Library/Application Support/Aion/ipc/ai-protection.sock"
AION_BROWSER_APP_KEY = "com.google.Chrome"
AION_PROTOCOL_VERSION = 1
AION_LEASE_SECONDS = 1800
AION_RENEW_INTERVAL_SECONDS = 600
AION_RESPONSE_TIMEOUT_SECONDS = 10
AION_BEGIN_RETRY_WINDOW_SECONDS = 10
AION_BEGIN_RETRY_INTERVAL_SECONDS = 1
AION_CHROME_BINARY = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


class AionLeaseError(RuntimeError):
    pass


def site_uses_aion_lease(site: str) -> bool:
    return site in {"cn", "global", "onedrive"}


class AionLeaseClient:
    def __init__(
        self,
        socket_path: Path,
        holder_id: str,
        client_name: str,
        app_key: str,
        pid: int | None = None,
        lease_seconds: int = AION_LEASE_SECONDS,
        renew_interval_seconds: int = AION_RENEW_INTERVAL_SECONDS,
        app_key_candidates: list[str] | None = None,
    ) -> None:
        self.socket_path = socket_path
        self.holder_id = holder_id
        self.client_name = client_name
        self.app_key = app_key
        self.app_key_candidates = app_key_candidates or [app_key]
        self.pid = pid if pid is not None else os.getpid()
        self.lease_seconds = lease_seconds
        self.renew_interval_seconds = renew_interval_seconds
        self._socket: socket.socket | None = None
        self._socket_file = None
        self._send_lock = threading.Lock()
        self._pending: dict[str, Queue] = {}
        self._pending_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._ready_event = threading.Event()
        self._ready_error: str | None = None
        self._reader_thread: threading.Thread | None = None
        self._renew_thread: threading.Thread | None = None

    def start(self) -> None:
        if not self.socket_path.exists():
            raise AionLeaseError(f"Aion socket not found: {self.socket_path}")

        self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._socket.connect(str(self.socket_path))
        self._socket_file = self._socket.makefile("rwb", buffering=0)

        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

        self._send_json_line(
            {
                "action": "session.hello",
                "protocolVersion": AION_PROTOCOL_VERSION,
                "holderId": self.holder_id,
                "clientName": self.client_name,
                "pid": self.pid,
            }
        )

        if not self._ready_event.wait(timeout=AION_RESPONSE_TIMEOUT_SECONDS):
            raise AionLeaseError("Timed out waiting for Aion session.ready")
        if self._ready_error is not None:
            raise AionLeaseError(self._ready_error)

        self.app_key = self._begin_with_matching_app_key()

        self._renew_thread = threading.Thread(target=self._renew_loop, daemon=True)
        self._renew_thread.start()

    def close(self) -> None:
        self._stop_event.set()
        try:
            if self._socket is not None:
                try:
                    response = self._send_request(action="lease.end")
                    self._require_accepted(response, "lease.end")
                except Exception:
                    pass
        finally:
            self._close_transport()

    def _renew_loop(self) -> None:
        while not self._stop_event.wait(self.renew_interval_seconds):
            try:
                response = self._send_request(
                    action="lease.renew",
                    lease_seconds=self.lease_seconds,
                )
                self._require_accepted(response, "lease.renew")
            except Exception:
                self._stop_event.set()
                return

    def _reader_loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                line = self._read_line()
                if line is None:
                    if not self._ready_event.is_set():
                        self._ready_error = "Aion socket closed before session.ready"
                        self._ready_event.set()
                    self._fail_pending("Aion socket connection closed")
                    return

                payload = json.loads(line)
                action = payload.get("action")
                if action == "session.ready":
                    self._ready_event.set()
                    continue
                if action == "session.error":
                    self._ready_error = payload.get("message", "Aion session.error")
                    self._ready_event.set()
                    continue
                if action == "lease.can_close.request":
                    self._handle_close_check(payload)
                    continue

                request_id = payload.get("requestId")
                if request_id is None:
                    continue

                with self._pending_lock:
                    queue = self._pending.pop(request_id, None)
                if queue is not None:
                    queue.put(payload)
        except Exception as exc:
            if not self._ready_event.is_set():
                self._ready_error = str(exc)
                self._ready_event.set()
            self._fail_pending(str(exc))

    def _handle_close_check(self, payload: dict) -> None:
        self._send_json_line(
            {
                "action": "lease.can_close.reply",
                "requestId": payload["requestId"],
                "holderId": self.holder_id,
                "appKey": self.app_key,
                "result": "extend_lease",
                "leaseSeconds": self.lease_seconds,
            }
        )

    def _send_request(self, action: str, lease_seconds: int | None = None) -> dict:
        request_id = f"{action}-{uuid.uuid4().hex}"
        queue: Queue = Queue(maxsize=1)
        with self._pending_lock:
            self._pending[request_id] = queue

        payload = {
            "action": action,
            "requestId": request_id,
            "holderId": self.holder_id,
            "appKey": self.app_key,
        }
        if lease_seconds is not None:
            payload["leaseSeconds"] = lease_seconds

        self._send_json_line(payload)
        try:
            return queue.get(timeout=AION_RESPONSE_TIMEOUT_SECONDS)
        except Empty as exc:
            with self._pending_lock:
                self._pending.pop(request_id, None)
            raise AionLeaseError(f"Timed out waiting for Aion response to {action}") from exc

    def _require_accepted(self, payload: dict, action: str) -> None:
        if payload.get("code") != "accepted":
            raise AionLeaseError(f"Aion {action} rejected: {payload.get('code')}")

    def _begin_with_matching_app_key(self) -> str:
        deadline = time.monotonic() + AION_BEGIN_RETRY_WINDOW_SECONDS
        last_code = None
        while True:
            for app_key in self.app_key_candidates:
                self.app_key = app_key
                response = self._send_request(
                    action="lease.begin",
                    lease_seconds=self.lease_seconds,
                )
                code = response.get("code")
                if code == "accepted":
                    return app_key
                last_code = code

            if last_code != "unknown_app" or time.monotonic() >= deadline:
                break
            time.sleep(AION_BEGIN_RETRY_INTERVAL_SECONDS)
        raise AionLeaseError(f"Aion lease.begin rejected: {last_code}")

    def _send_json_line(self, payload: dict) -> None:
        if self._socket_file is None:
            raise AionLeaseError("Aion socket is not connected")
        line = json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n"
        with self._send_lock:
            self._socket_file.write(line)
            self._socket_file.flush()

    def _read_line(self) -> str | None:
        if self._socket_file is None:
            return None
        raw = self._socket_file.readline()
        if not raw:
            return None
        return raw.decode("utf-8").strip()

    def _fail_pending(self, message: str) -> None:
        with self._pending_lock:
            pending = list(self._pending.values())
            self._pending.clear()
        for queue in pending:
            queue.put({"code": "connection_closed", "message": message})

    def _close_transport(self) -> None:
        if self._socket_file is not None:
            try:
                self._socket_file.close()
            except Exception:
                pass
            self._socket_file = None
        if self._socket is not None:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None


@contextmanager
def maybe_with_aion_lease(site: str):
    if not site_uses_aion_lease(site):
        yield None
        return

    app_key_candidates = resolve_aion_app_key_candidates()
    client = AionLeaseClient(
        socket_path=AION_SOCKET_PATH,
        holder_id=f"garmin-sync:{site}:{uuid.uuid4().hex}",
        client_name=f"garmin-sync:{site}",
        app_key=AION_BROWSER_APP_KEY,
        app_key_candidates=app_key_candidates,
    )
    client.start()
    try:
        yield client
    finally:
        client.close()


def resolve_aion_app_key_candidates() -> list[str]:
    candidates: list[str] = []
    profile_key = detect_playwright_chrome_profile_app_key()
    if profile_key:
        candidates.append(profile_key)
    candidates.append(AION_BROWSER_APP_KEY)
    candidates.append(f"{AION_BROWSER_APP_KEY}#automation")
    return list(dict.fromkeys(candidates))


def detect_playwright_chrome_profile_app_key() -> str | None:
    try:
        output = subprocess.check_output(["ps", "-ax", "-o", "command="], text=True)
    except Exception:
        return None

    lines = [
        line
        for line in output.splitlines()
        if AION_CHROME_BINARY in line and "playwright_chromiumdev_profile" in line
    ]
    if not lines:
        return None

    target = lines[-1]
    match = re.search(r"--user-data-dir=([^\s]+)", target)
    if not match:
        return None

    profile_name = Path(match.group(1)).name
    return f"{AION_BROWSER_APP_KEY}#profile:{profile_name}"
