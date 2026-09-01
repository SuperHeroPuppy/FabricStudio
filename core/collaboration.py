"""Direct, cross-platform workspace collaboration over TCP."""

from __future__ import annotations

import base64
import hmac
import http.server
import json
import queue
import secrets
import socket
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Callable
from urllib.parse import urlsplit

from core.public_tunnel import CloudflareQuickTunnel


PROTOCOL_VERSION = 1
DEFAULT_PORT = 45873
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_MESSAGE_BYTES = 48 * 1024 * 1024
WATCH_INTERVAL_SECONDS = 0.75

EXCLUDED_PARTS = {
    ".git",
    ".gradle",
    ".gradle-runtime",
    "__pycache__",
    "bin",
    "build",
    "run",
}


@dataclass(frozen=True)
class CollaborationEvent:
    kind: str
    message: str
    path: Path | None = None


@dataclass(eq=False)
class _Peer:
    sock: socket.socket
    stream: BinaryIO
    address: tuple[str, int]
    name: str
    send_lock: threading.Lock = field(default_factory=threading.Lock)


@dataclass(eq=False)
class _HttpPeer:
    token: str
    name: str
    messages: queue.Queue[dict] = field(default_factory=queue.Queue)
    last_seen: float = field(default_factory=time.monotonic)
    syncing: bool = True


@dataclass(eq=False)
class _HttpRemotePeer:
    base_url: str
    token: str
    name: str = "Host"
    send_lock: threading.Lock = field(default_factory=threading.Lock)


class CollaborationSession:
    """Host or join a direct-IP, last-save-wins workspace session."""

    def __init__(
        self,
        workspace_root: Path,
        on_event: Callable[[CollaborationEvent], None] | None = None,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.on_event = on_event
        self.role = ""
        self.display_name = ""
        self.code = ""
        self.host = ""
        self.port = 0
        self.connection_mode = ""
        self.public_invite_url = ""
        self._server: socket.socket | None = None
        self._server_peer: _Peer | _HttpRemotePeer | None = None
        self._peers: set[_Peer | _HttpPeer] = set()
        self._peers_lock = threading.RLock()
        self._state_lock = threading.RLock()
        self._stop_event = threading.Event()
        self._sync_ready = False
        self._baseline: dict[str, tuple[int, int]] = {}
        self._threads: list[threading.Thread] = []
        self._public_http: http.server.ThreadingHTTPServer | None = None
        self._public_secret = ""
        self._tunnel: CloudflareQuickTunnel | None = None

    @property
    def active(self) -> bool:
        return bool(self.role) and not self._stop_event.is_set()

    @property
    def peer_count(self) -> int:
        if self.role == "guest":
            return 1 if self._server_peer is not None else 0
        with self._peers_lock:
            return len(self._peers)

    @property
    def peer_names(self) -> list[str]:
        if self.role == "guest":
            return ["Host"] if self._server_peer is not None else []
        with self._peers_lock:
            return sorted(peer.name for peer in self._peers)

    def start_host(self, display_name: str, port: int = DEFAULT_PORT) -> None:
        if self.active:
            raise RuntimeError("A collaboration session is already active.")
        if not 0 <= int(port) <= 65535:
            raise ValueError("Port must be between 0 and 65535.")

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind(("0.0.0.0", int(port)))
            server.listen(8)
            server.settimeout(1.0)
        except OSError:
            server.close()
            raise

        self._initialize_host(display_name, "direct")
        self.code = f"{secrets.randbelow(1_000_000):06d}"
        self.host = local_network_address()
        self.port = int(server.getsockname()[1])
        self._server = server
        self._start_thread(self._accept_loop, "fabricstudio-collab-accept")
        self._emit(
            "started",
            f"Hosting on {self.host}:{self.port} with code {self.code}.",
        )

    def start_internet_host(
        self,
        display_name: str,
        cloudflared_path: Path,
        tunnel_factory: Callable[[Path], CloudflareQuickTunnel] = CloudflareQuickTunnel,
    ) -> None:
        """Host through an accountless HTTPS Quick Tunnel."""

        if self.active:
            raise RuntimeError("A collaboration session is already active.")
        self._initialize_host(display_name, "internet")
        try:
            gateway_port = self._start_public_gateway()
            tunnel = tunnel_factory(Path(cloudflared_path))
            public_url = tunnel.start(gateway_port)
        except Exception:
            self.stop()
            raise

        self._tunnel = tunnel
        self.host = urlsplit(public_url).netloc
        self.public_invite_url = f"{public_url.rstrip('/')}/join#{self._public_secret}"
        self._emit("started", "Internet collaboration is ready; share the invitation link.")

    def _initialize_host(self, display_name: str, connection_mode: str) -> None:
        self._reset_runtime()
        self.role = "host"
        self.connection_mode = connection_mode
        self.display_name = _clean_display_name(display_name)
        with self._state_lock:
            self._baseline = self._scan_files()
        self._sync_ready = True
        self._start_thread(self._watch_loop, "fabricstudio-collab-watch")

    def join(
        self,
        host: str,
        port: int,
        code: str,
        display_name: str,
        timeout: float = 8.0,
    ) -> None:
        if self.active:
            raise RuntimeError("A collaboration session is already active.")
        host = str(host).strip()
        if not host:
            raise ValueError("Host address is required.")
        if not 1 <= int(port) <= 65535:
            raise ValueError("Port must be between 1 and 65535.")

        sock = socket.create_connection((host, int(port)), timeout=timeout)
        stream = sock.makefile("rwb")
        peer = _Peer(sock, stream, (host, int(port)), "Host")
        try:
            self._send(
                peer,
                {
                    "type": "hello",
                    "protocol": PROTOCOL_VERSION,
                    "code": str(code).strip(),
                    "name": _clean_display_name(display_name),
                    "workspace_id": self._workspace_id(),
                },
            )
            response = self._read(peer)
            if response.get("type") == "error":
                raise ConnectionError(str(response.get("message") or "Connection rejected."))
            if response.get("type") != "welcome":
                raise ConnectionError("The host returned an invalid handshake.")
        except Exception:
            _close_peer(peer)
            raise

        sock.settimeout(None)
        self._reset_runtime()
        self.role = "guest"
        self.connection_mode = "direct"
        self.display_name = _clean_display_name(display_name)
        self.code = str(code).strip()
        self.host = host
        self.port = int(port)
        self._server_peer = peer
        self._sync_ready = False
        self._start_thread(lambda: self._guest_receive_loop(peer), "fabricstudio-collab-receive")
        self._start_thread(self._watch_loop, "fabricstudio-collab-watch")
        self._emit("connected", f"Connected to {host}:{port}; receiving the host workspace.")

    def join_internet(
        self,
        invite_url: str,
        display_name: str,
        timeout: float = 30.0,
    ) -> None:
        if self.active:
            raise RuntimeError("A collaboration session is already active.")
        parsed = urlsplit(str(invite_url).strip())
        if parsed.scheme not in {"https", "http"} or not parsed.netloc or not parsed.fragment:
            raise ValueError("Enter the complete Internet invitation link.")
        if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("Internet invitation links must use HTTPS.")

        base_url = f"{parsed.scheme}://{parsed.netloc}"
        hello = {
            "type": "hello",
            "protocol": PROTOCOL_VERSION,
            "name": _clean_display_name(display_name),
            "workspace_id": self._workspace_id(),
        }
        response = _http_json_request(
            f"{base_url}/api/hello",
            method="POST",
            payload=hello,
            authorization=parsed.fragment,
            timeout=timeout,
        )
        token = str(response.get("token") or "")
        if not token:
            raise ConnectionError(str(response.get("message") or "The host rejected the invitation."))

        self._reset_runtime()
        self.role = "guest"
        self.connection_mode = "internet"
        self.display_name = _clean_display_name(display_name)
        self.host = parsed.netloc
        self.port = 443 if parsed.scheme == "https" else int(parsed.port or 80)
        self.public_invite_url = str(invite_url).strip()
        peer = _HttpRemotePeer(base_url, token)
        self._server_peer = peer
        self._sync_ready = False
        self._start_thread(
            lambda: self._guest_http_receive_loop(peer),
            "fabricstudio-collab-internet-receive",
        )
        self._start_thread(self._watch_loop, "fabricstudio-collab-watch")
        self._emit("connected", "Connected through the Internet tunnel; receiving the host workspace.")

    def stop(self) -> None:
        if not self.role and self._stop_event.is_set():
            return
        was_active = self.active
        self._stop_event.set()

        tunnel = self._tunnel
        self._tunnel = None
        if tunnel is not None:
            tunnel.stop()

        public_http = self._public_http
        self._public_http = None
        if public_http is not None:
            public_http.shutdown()
            public_http.server_close()

        if self._server is not None:
            try:
                self._server.close()
            except OSError:
                pass
            self._server = None

        peer = self._server_peer
        self._server_peer = None
        if peer is not None:
            try:
                self._send(peer, {"type": "bye"})
            except (OSError, ValueError):
                pass
            _close_peer(peer)

        with self._peers_lock:
            peers = list(self._peers)
            self._peers.clear()
        for item in peers:
            try:
                self._send(item, {"type": "bye"})
            except (OSError, ValueError):
                pass
            _close_peer(item)

        self.role = ""
        self.connection_mode = ""
        self.code = ""
        self.host = ""
        self.port = 0
        self.public_invite_url = ""
        self._public_secret = ""
        self._sync_ready = False
        if was_active:
            self._emit("stopped", "Collaboration session stopped.")

    def _reset_runtime(self) -> None:
        self._stop_event = threading.Event()
        self._baseline = {}
        self._threads = []

    def _start_public_gateway(self) -> int:
        self._public_secret = secrets.token_urlsafe(32)
        server = _CollaborationHttpServer(("127.0.0.1", 0), _PublicRequestHandler, self)
        self._public_http = server
        self._start_thread(server.serve_forever, "fabricstudio-collab-http")
        return int(server.server_address[1])

    def _public_hello(self, hello: dict, authorization: str) -> tuple[dict, _HttpPeer | None]:
        if not hmac.compare_digest(str(authorization), self._public_secret):
            return {"message": "The Internet invitation is invalid or expired."}, None
        error = self._validate_hello(
            {
                **hello,
                "code": self.code,
            }
        )
        if error:
            return {"message": error}, None
        peer = _HttpPeer(
            token=secrets.token_urlsafe(32),
            name=_clean_display_name(str(hello.get("name") or "Guest")),
        )
        with self._peers_lock:
            self._peers.add(peer)
        self._emit("peer_joined", f"{peer.name} joined through the Internet tunnel.")
        return {"token": peer.token, "protocol": PROTOCOL_VERSION}, peer

    def _public_poll(self, token: str) -> dict:
        peer = self._http_peer(token)
        if peer is None:
            raise PermissionError("The Internet session has expired.")
        peer.last_seen = time.monotonic()
        try:
            message = peer.messages.get(timeout=20.0)
        except queue.Empty:
            return {"messages": []}
        return {"messages": [message]}

    def _public_receive(self, token: str, message: dict) -> None:
        peer = self._http_peer(token)
        if peer is None:
            raise PermissionError("The Internet session has expired.")
        peer.last_seen = time.monotonic()
        message_type = message.get("type")
        if message_type == "bye":
            peer.messages.put({"type": "bye"})
            with self._peers_lock:
                self._peers.discard(peer)
            self._emit("peer_left", f"{peer.name} disconnected.")
            return
        if message_type != "file":
            raise ValueError("Unsupported Internet collaboration message.")
        path = self._apply_file_message(message)
        self._broadcast(message, exclude=peer)
        self._emit("remote_change", f"{peer.name} updated {path}.", path)

    def _http_peer(self, token: str) -> _HttpPeer | None:
        with self._peers_lock:
            for peer in self._peers:
                if isinstance(peer, _HttpPeer) and hmac.compare_digest(peer.token, str(token)):
                    return peer
        return None

    def _accept_loop(self) -> None:
        while not self._stop_event.is_set() and self._server is not None:
            try:
                sock, address = self._server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            self._start_thread(
                lambda client=sock, remote=address: self._accept_peer(client, remote),
                "fabricstudio-collab-client",
            )

    def _accept_peer(self, sock: socket.socket, address: tuple[str, int]) -> None:
        sock.settimeout(8.0)
        stream = sock.makefile("rwb")
        peer = _Peer(sock, stream, address, "Guest")
        try:
            hello = self._read(peer)
            error = self._validate_hello(hello)
            if error:
                self._send(peer, {"type": "error", "message": error})
                return
            peer.name = _clean_display_name(str(hello.get("name") or "Guest"))
            self._send(
                peer,
                {
                    "type": "welcome",
                    "protocol": PROTOCOL_VERSION,
                    "workspace_id": self._workspace_id(),
                },
            )
            sock.settimeout(None)
            with self._peers_lock:
                self._peers.add(peer)
            self._send_snapshot(peer)
            self._emit("peer_joined", f"{peer.name} joined from {address[0]}.")
            self._host_receive_loop(peer)
        except (ConnectionError, OSError, ValueError, json.JSONDecodeError) as exc:
            if not self._stop_event.is_set():
                self._emit("error", f"Collaboration peer error: {exc}")
        finally:
            with self._peers_lock:
                was_connected = peer in self._peers
                self._peers.discard(peer)
            _close_peer(peer)
            if was_connected and not self._stop_event.is_set():
                self._emit("peer_left", f"{peer.name} disconnected.")

    def _validate_hello(self, hello: dict) -> str:
        if hello.get("type") != "hello":
            return "Invalid handshake."
        if hello.get("protocol") != PROTOCOL_VERSION:
            return "FabricStudio collaboration protocol versions do not match."
        if str(hello.get("code") or "") != self.code:
            return "Incorrect collaboration code."
        if str(hello.get("workspace_id") or "") != self._workspace_id():
            return "The open workspaces have different mod IDs."
        return ""

    def _host_receive_loop(self, peer: _Peer) -> None:
        while not self._stop_event.is_set():
            message = self._read(peer)
            message_type = message.get("type")
            if message_type == "bye":
                return
            if message_type == "file":
                path = self._apply_file_message(message)
                self._broadcast(message, exclude=peer)
                self._emit("remote_change", f"{peer.name} updated {path}.", path)

    def _guest_receive_loop(self, peer: _Peer) -> None:
        receiving_snapshot = False
        try:
            while not self._stop_event.is_set():
                message = self._read(peer)
                message_type = message.get("type")
                if message_type == "bye":
                    break
                if message_type == "snapshot_start":
                    self._sync_ready = False
                    receiving_snapshot = True
                    continue
                if message_type == "snapshot_end":
                    with self._state_lock:
                        self._baseline = self._scan_files()
                    self._sync_ready = True
                    receiving_snapshot = False
                    self._emit("synced", "Initial workspace sync complete.")
                    continue
                if message_type == "file":
                    path = self._apply_file_message(message)
                    if not receiving_snapshot:
                        self._emit("remote_change", f"Host updated {path}.", path)
        except (ConnectionError, OSError, ValueError, json.JSONDecodeError) as exc:
            if not self._stop_event.is_set():
                self._emit("error", f"Collaboration connection ended: {exc}")
        finally:
            _close_peer(peer)
            if self._server_peer is peer:
                self._server_peer = None
            if not self._stop_event.is_set():
                self._stop_event.set()
                self._emit("stopped", "Disconnected from the host.")

    def _guest_http_receive_loop(self, peer: _HttpRemotePeer) -> None:
        receiving_snapshot = False
        try:
            while not self._stop_event.is_set():
                response = _http_json_request(
                    f"{peer.base_url}/api/poll",
                    method="GET",
                    authorization=peer.token,
                    timeout=35.0,
                )
                messages = response.get("messages", [])
                if not isinstance(messages, list):
                    raise ConnectionError("The Internet host returned an invalid response.")
                for message in messages:
                    if not isinstance(message, dict):
                        continue
                    message_type = message.get("type")
                    if message_type == "bye":
                        return
                    if message_type == "snapshot_start":
                        self._sync_ready = False
                        receiving_snapshot = True
                        continue
                    if message_type == "snapshot_end":
                        with self._state_lock:
                            self._baseline = self._scan_files()
                        self._sync_ready = True
                        receiving_snapshot = False
                        self._emit("synced", "Initial Internet workspace sync complete.")
                        continue
                    if message_type == "file":
                        path = self._apply_file_message(message)
                        if not receiving_snapshot:
                            self._emit("remote_change", f"Host updated {path}.", path)
        except (ConnectionError, OSError, ValueError) as exc:
            if not self._stop_event.is_set():
                self._emit("error", f"Internet collaboration connection ended: {exc}")
        finally:
            if self._server_peer is peer:
                self._server_peer = None
            if not self._stop_event.is_set():
                self._stop_event.set()
                self._emit("stopped", "Disconnected from the Internet host.")

    def _send_snapshot(self, peer: _Peer | _HttpPeer) -> None:
        if isinstance(peer, _HttpPeer):
            with self._state_lock:
                self._send(peer, {"type": "snapshot_start"})
                for relative in sorted(self._scan_files()):
                    path = self.workspace_root / Path(relative)
                    try:
                        content = path.read_bytes()
                    except OSError:
                        continue
                    if len(content) > MAX_FILE_BYTES:
                        self._emit("skipped", f"Skipped large file during sync: {relative}", path)
                        continue
                    self._send(peer, _file_message(relative, content))
                self._send(peer, {"type": "snapshot_end"})
                peer.syncing = False
            return
        with peer.send_lock, self._state_lock:
            peer.stream.write(_encode_message({"type": "snapshot_start"}))
            for relative in sorted(self._scan_files()):
                path = self.workspace_root / Path(relative)
                try:
                    content = path.read_bytes()
                except OSError:
                    continue
                if len(content) > MAX_FILE_BYTES:
                    self._emit("skipped", f"Skipped large file during sync: {relative}", path)
                    continue
                peer.stream.write(_encode_message(_file_message(relative, content)))
            peer.stream.write(_encode_message({"type": "snapshot_end"}))
            peer.stream.flush()

    def _watch_loop(self) -> None:
        while not self._stop_event.wait(WATCH_INTERVAL_SECONDS):
            if not self._sync_ready:
                continue
            try:
                changes = self._poll_changes()
                for message, path in changes:
                    if self.role == "host":
                        self._broadcast(message)
                    elif self._server_peer is not None:
                        self._send(self._server_peer, message)
                    self._emit("local_change", f"Shared {path}.", path)
            except (OSError, ValueError) as exc:
                if not self._stop_event.is_set():
                    self._emit("error", f"Could not share a workspace change: {exc}")

    def _poll_changes(self) -> list[tuple[dict, Path]]:
        changes: list[tuple[dict, Path]] = []
        with self._state_lock:
            current = self._scan_files()
            for relative, state in current.items():
                if self._baseline.get(relative) == state:
                    continue
                path = self.workspace_root / Path(relative)
                try:
                    content = path.read_bytes()
                except OSError:
                    continue
                if len(content) > MAX_FILE_BYTES:
                    self._emit("skipped", f"Skipped large file: {relative}", path)
                    continue
                changes.append((_file_message(relative, content), path))

            for relative in self._baseline.keys() - current.keys():
                path = self.workspace_root / Path(relative)
                changes.append(({"type": "file", "op": "delete", "path": relative}, path))
            self._baseline = current
        return changes

    def _apply_file_message(self, message: dict) -> Path:
        relative = _validate_relative_path(message.get("path"))
        path = _safe_workspace_path(self.workspace_root, relative)
        operation = message.get("op")
        with self._state_lock:
            if operation == "delete":
                if path.is_file() or path.is_symlink():
                    path.unlink()
                self._baseline.pop(relative, None)
                return path
            if operation != "write":
                raise ValueError("Unknown collaboration file operation.")
            encoded = message.get("content")
            if not isinstance(encoded, str):
                raise ValueError("Missing collaboration file content.")
            try:
                content = base64.b64decode(encoded, validate=True)
            except ValueError as exc:
                raise ValueError("Invalid collaboration file content.") from exc
            if len(content) > MAX_FILE_BYTES:
                raise ValueError("Collaboration file exceeds the size limit.")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            stat = path.stat()
            self._baseline[relative] = (stat.st_mtime_ns, stat.st_size)
        return path

    def _scan_files(self) -> dict[str, tuple[int, int]]:
        files: dict[str, tuple[int, int]] = {}
        if not self.workspace_root.exists():
            return files
        for path in self.workspace_root.rglob("*"):
            if not path.is_file() or path.is_symlink() or _is_excluded(path, self.workspace_root):
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            files[path.relative_to(self.workspace_root).as_posix()] = (
                stat.st_mtime_ns,
                stat.st_size,
            )
        return files

    def _broadcast(
        self,
        message: dict,
        exclude: _Peer | _HttpPeer | None = None,
    ) -> None:
        with self._peers_lock:
            peers = [
                peer
                for peer in self._peers
                if peer is not exclude
                and not (isinstance(peer, _HttpPeer) and peer.syncing)
            ]
        for peer in peers:
            try:
                self._send(peer, message)
            except (OSError, ValueError):
                _close_peer(peer)

    def _send(self, peer: _Peer | _HttpPeer | _HttpRemotePeer, message: dict) -> None:
        if isinstance(peer, _HttpPeer):
            peer.messages.put(message)
            return
        if isinstance(peer, _HttpRemotePeer):
            with peer.send_lock:
                _http_json_request(
                    f"{peer.base_url}/api/send",
                    method="POST",
                    payload=message,
                    authorization=peer.token,
                    timeout=35.0,
                )
            return
        encoded = _encode_message(message)
        with peer.send_lock:
            peer.stream.write(encoded)
            peer.stream.flush()

    @staticmethod
    def _read(peer: _Peer) -> dict:
        line = peer.stream.readline(MAX_MESSAGE_BYTES + 1)
        if not line:
            raise ConnectionError("Peer disconnected.")
        if len(line) > MAX_MESSAGE_BYTES:
            raise ValueError("Collaboration message exceeds the size limit.")
        payload = json.loads(line.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Collaboration message must be an object.")
        return payload

    def _workspace_id(self) -> str:
        path = self.workspace_root / "project_info.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        if isinstance(payload, dict) and payload.get("mod_id"):
            return str(payload["mod_id"]).strip().lower()
        return self.workspace_root.name.strip().lower()

    def _start_thread(self, target: Callable[[], None], name: str) -> None:
        thread = threading.Thread(target=target, name=name, daemon=True)
        self._threads.append(thread)
        thread.start()

    def _emit(self, kind: str, message: str, path: Path | None = None) -> None:
        if self.on_event is None:
            return
        try:
            self.on_event(CollaborationEvent(kind, message, path))
        except Exception:
            pass


class _CollaborationHttpServer(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, handler, session: CollaborationSession) -> None:
        self.session = session
        super().__init__(address, handler)


class _PublicRequestHandler(http.server.BaseHTTPRequestHandler):
    server: _CollaborationHttpServer

    def do_POST(self) -> None:
        try:
            payload = self._read_payload()
            authorization = self._authorization()
            if self.path == "/api/hello":
                response, peer = self.server.session._public_hello(payload, authorization)
                self._write_response(200 if peer is not None else 403, response)
                if peer is not None:
                    self.server.session._send_snapshot(peer)
                return
            if self.path == "/api/send":
                self.server.session._public_receive(authorization, payload)
                self._write_response(200, {"ok": True})
                return
            self._write_response(404, {"message": "Not found."})
        except PermissionError as exc:
            self._write_response(401, {"message": str(exc)})
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
            self._write_response(400, {"message": str(exc)})
        except OSError:
            self._write_response(500, {"message": "Could not apply the workspace update."})

    def do_GET(self) -> None:
        if self.path != "/api/poll":
            self._write_response(404, {"message": "Not found."})
            return
        try:
            response = self.server.session._public_poll(self._authorization())
            self._write_response(200, response)
        except PermissionError as exc:
            self._write_response(401, {"message": str(exc)})

    def _read_payload(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Invalid request length.") from exc
        if length < 0 or length > MAX_MESSAGE_BYTES:
            raise ValueError("Internet collaboration message exceeds the size limit.")
        raw = self.rfile.read(length)
        payload = json.loads(raw.decode("utf-8")) if raw else {}
        if not isinstance(payload, dict):
            raise ValueError("Internet collaboration message must be an object.")
        return payload

    def _authorization(self) -> str:
        header = str(self.headers.get("Authorization") or "")
        return header.removeprefix("Bearer ").strip()

    def _write_response(self, status: int, payload: dict) -> None:
        encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, _format: str, *_args) -> None:
        return


def local_network_address() -> str:
    """Best-effort LAN address without sending network traffic."""

    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 80))
        return str(probe.getsockname()[0])
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
    finally:
        probe.close()


def _file_message(relative: str, content: bytes) -> dict:
    return {
        "type": "file",
        "op": "write",
        "path": relative,
        "content": base64.b64encode(content).decode("ascii"),
    }


def _encode_message(message: dict) -> bytes:
    encoded = (json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8")
    if len(encoded) > MAX_MESSAGE_BYTES:
        raise ValueError("Collaboration message exceeds the size limit.")
    return encoded


def _validate_relative_path(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > 1024:
        raise ValueError("Invalid collaboration file path.")
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise ValueError("Collaboration file path escapes the workspace.")
    if any(part in EXCLUDED_PARTS for part in path.parts):
        raise ValueError("Collaboration file path is excluded from sharing.")
    return path.as_posix()


def _is_excluded(path: Path, workspace_root: Path) -> bool:
    relative = path.relative_to(workspace_root)
    return any(
        part in EXCLUDED_PARTS or part.startswith(".fabricstudio-sync-")
        for part in relative.parts
    )


def _safe_workspace_path(workspace_root: Path, relative: str) -> Path:
    path = workspace_root / Path(relative)
    resolved = path.resolve()
    try:
        resolved.relative_to(workspace_root)
    except ValueError as exc:
        raise ValueError("Collaboration file path escapes through a symbolic link.") from exc
    if path.is_symlink():
        raise ValueError("Collaboration cannot replace a symbolic link.")
    return resolved


def _clean_display_name(value: str) -> str:
    cleaned = " ".join(str(value or "").split()).strip()
    return cleaned[:48] or "FabricStudio User"


def _http_json_request(
    url: str,
    method: str,
    payload: dict | None = None,
    authorization: str = "",
    timeout: float = 30.0,
) -> dict:
    encoded = None
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {authorization}",
        "User-Agent": "FabricStudio",
    }
    if payload is not None:
        encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        if len(encoded) > MAX_MESSAGE_BYTES:
            raise ValueError("Internet collaboration message exceeds the size limit.")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=encoded, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(MAX_MESSAGE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        try:
            error_payload = json.loads(exc.read().decode("utf-8"))
            message = str(error_payload.get("message") or exc.reason)
        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
            message = str(exc.reason)
        raise ConnectionError(message) from exc
    except urllib.error.URLError as exc:
        raise ConnectionError(str(exc.reason)) from exc
    if len(raw) > MAX_MESSAGE_BYTES:
        raise ValueError("Internet collaboration response exceeds the size limit.")
    result = json.loads(raw.decode("utf-8")) if raw else {}
    if not isinstance(result, dict):
        raise ConnectionError("The Internet collaboration response was invalid.")
    return result


def _close_peer(peer: _Peer | _HttpPeer | _HttpRemotePeer) -> None:
    if not isinstance(peer, _Peer):
        return
    try:
        peer.stream.close()
    except OSError:
        pass
    try:
        peer.sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    try:
        peer.sock.close()
    except OSError:
        pass
