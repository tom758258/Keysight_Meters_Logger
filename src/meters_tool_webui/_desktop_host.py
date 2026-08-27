from __future__ import annotations

import asyncio
import json
import socket
import sys
import threading
import time
from typing import Any, TextIO
from urllib.error import URLError
from urllib.request import urlopen

from meters_tool_webui.web_ui import (
    PACKAGE_NAME,
    WebRunManager,
    create_uvicorn_server,
)


HOST = "127.0.0.1"
READINESS_TIMEOUT_S = 8.0
READINESS_POLL_INTERVAL_S = 0.2


def _emit_event(payload: dict[str, Any], *, stream: TextIO) -> None:
    print(json.dumps(payload, separators=(",", ":")), file=stream, flush=True)


def _server_is_ready(url: str) -> bool:
    try:
        with urlopen(url, timeout=0.5) as response:
            if int(response.status) != 200:
                return False
            payload = json.loads(response.read().decode("utf-8"))
            app = payload.get("app", {}) if isinstance(payload, dict) else {}
            return app.get("name") == PACKAGE_NAME
    except (OSError, URLError, ValueError, json.JSONDecodeError):
        return False


def _run_server(
    server: Any,
    server_socket: socket.socket,
    errors: list[BaseException],
) -> None:
    try:
        asyncio.run(server.serve(sockets=[server_socket]))
    except BaseException as exc:  # pragma: no cover - runtime safety net
        errors.append(exc)


def _wait_for_ready(
    health_url: str,
    server_thread: threading.Thread,
    server_errors: list[BaseException],
) -> None:
    deadline = time.monotonic() + READINESS_TIMEOUT_S
    while time.monotonic() < deadline:
        if _server_is_ready(health_url):
            return
        if not server_thread.is_alive():
            if server_errors:
                raise RuntimeError(
                    "Desktop WebUI server stopped during startup"
                ) from server_errors[0]
            raise RuntimeError("Desktop WebUI server stopped during startup")
        time.sleep(READINESS_POLL_INTERVAL_S)
    raise TimeoutError("Desktop WebUI server did not become ready")


def _request_shutdown(
    manager: WebRunManager,
    server: Any,
    server_thread: threading.Thread,
    server_socket: socket.socket,
    *,
    stream: TextIO,
) -> bool:
    try:
        shutdown_complete = manager.shutdown()
    except Exception as exc:
        _emit_event(
            {
                "event": "shutdown_incomplete",
                "message": f"{type(exc).__name__}: {exc}",
            },
            stream=stream,
        )
        return False

    if not shutdown_complete:
        _emit_event(
            {
                "event": "shutdown_incomplete",
                "message": "Timed out waiting for the active WebUI run to finish cleanup.",
            },
            stream=stream,
        )
        return False

    server.should_exit = True
    server_thread.join()
    server_socket.close()
    return True


def main() -> int:
    manager: WebRunManager | None = None
    server: Any | None = None
    server_socket: socket.socket | None = None
    server_thread: threading.Thread | None = None
    server_errors: list[BaseException] = []

    try:
        server_socket = socket.create_server((HOST, 0))
        port = int(server_socket.getsockname()[1])
        url = f"http://{HOST}:{port}"
        manager = WebRunManager()
        server = create_uvicorn_server(
            manager,
            host=HOST,
            port=port,
            access_log=False,
        )
        server_thread = threading.Thread(
            target=_run_server,
            args=(server, server_socket, server_errors),
            name="meters-tool-desktop-webui-server",
            daemon=False,
        )
        server_thread.start()
        _wait_for_ready(f"{url}/api/capabilities", server_thread, server_errors)
        _emit_event({"event": "ready", "url": url}, stream=sys.stdout)

        for raw_line in sys.stdin:
            try:
                payload = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            if payload != {"command": "shutdown"}:
                continue
            if _request_shutdown(
                manager,
                server,
                server_thread,
                server_socket,
                stream=sys.stdout,
            ):
                server_socket = None
                return 0

        # Stdin EOF lifecycle semantics intentionally remain undefined.
        server_thread.join()
        if server_errors:
            raise RuntimeError("Desktop WebUI server stopped") from server_errors[0]
        return 0
    except BaseException as exc:
        _emit_event(
            {"event": "error", "message": f"{type(exc).__name__}: {exc}"},
            stream=sys.stdout,
        )
        if manager is not None:
            try:
                shutdown_complete = manager.shutdown()
            except Exception:
                shutdown_complete = False
            if shutdown_complete and server is not None:
                server.should_exit = True
                if server_thread is not None:
                    server_thread.join()
        if server_socket is not None and (server_thread is None or not server_thread.is_alive()):
            server_socket.close()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
