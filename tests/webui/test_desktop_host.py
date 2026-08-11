from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch

from meters_tool_webui import _desktop_host


class FakeResponse:
    status = 200

    def __init__(self, events: list[str]) -> None:
        self._events = events

    def __enter__(self):
        self._events.append("capabilities-ready")
        return self

    def __exit__(self, *_args):
        return None

    def read(self) -> bytes:
        return json.dumps({"app": {"name": "meters-tool-webui", "version": "test"}}).encode("utf-8")


class RecordingStream(io.StringIO):
    def __init__(self, events: list[str]) -> None:
        super().__init__()
        self._events = events

    def flush(self) -> None:
        self._events.append("stdout.flush")
        super().flush()


class FakeSocket:
    def __init__(self, events: list[str], port: int = 43123) -> None:
        self._events = events
        self._port = port
        self.closed = False

    def getsockname(self):
        return (_desktop_host.HOST, self._port)

    def close(self) -> None:
        self._events.append("socket.close")
        self.closed = True


class FakeServer:
    def __init__(self, events: list[str]) -> None:
        self._events = events
        self._should_exit = False

    @property
    def should_exit(self):
        return self._should_exit

    @should_exit.setter
    def should_exit(self, value):
        self._events.append("server.should_exit")
        self._should_exit = value


class FakeThread:
    def __init__(self, events: list[str]) -> None:
        self._events = events
        self._alive = False

    def start(self) -> None:
        self._events.append("server.start")
        self._alive = True

    def is_alive(self) -> bool:
        return self._alive

    def join(self) -> None:
        self._events.append("server.join")
        self._alive = False


class DesktopHostLifecycleTests(unittest.TestCase):
    def test_ready_uses_bound_ephemeral_port_and_shutdown_preserves_order(self):
        events: list[str] = []
        server_socket = FakeSocket(events)
        server = FakeServer(events)
        stdout = RecordingStream(events)

        class FakeManager:
            def shutdown(self):
                events.append("manager.shutdown")
                return True

        manager = FakeManager()
        server_thread = FakeThread(events)

        def thread_factory(*, target, args, name, daemon):
            self.assertIs(_desktop_host._run_server, target)
            self.assertEqual((server, server_socket, []), args)
            self.assertEqual("meters-tool-desktop-webui-server", name)
            self.assertFalse(daemon)
            return server_thread

        with (
            patch.object(_desktop_host.socket, "create_server", return_value=server_socket) as bind,
            patch.object(_desktop_host, "WebRunManager", return_value=manager),
            patch.object(
                _desktop_host,
                "create_uvicorn_server",
                return_value=server,
            ) as create_server,
            patch.object(_desktop_host.threading, "Thread", side_effect=thread_factory),
            patch.object(
                _desktop_host,
                "urlopen",
                return_value=FakeResponse(events),
            ) as urlopen,
            patch.object(_desktop_host.sys, "stdin", io.StringIO('{"command":"shutdown"}\n')),
            patch.object(_desktop_host.sys, "stdout", stdout),
        ):
            self.assertEqual(0, _desktop_host.main())

        bind.assert_called_once_with((_desktop_host.HOST, 0))
        create_server.assert_called_once_with(
            manager,
            host=_desktop_host.HOST,
            port=43123,
            access_log=False,
        )
        urlopen.assert_called_once_with(
            "http://127.0.0.1:43123/api/capabilities",
            timeout=0.5,
        )
        self.assertEqual(
            {"event": "ready", "url": "http://127.0.0.1:43123"},
            json.loads(stdout.getvalue()),
        )
        self.assertEqual(
            [
                "server.start",
                "capabilities-ready",
                "stdout.flush",
                "manager.shutdown",
                "server.should_exit",
                "server.join",
                "socket.close",
            ],
            events,
        )

    def test_shutdown_incomplete_keeps_server_and_socket_running(self):
        events: list[str] = []
        server_socket = FakeSocket(events)
        server = FakeServer(events)
        server_thread = FakeThread(events)
        server_thread.start()
        stdout = io.StringIO()

        class FakeManager:
            def shutdown(self):
                events.append("manager.shutdown")
                return False

        shutdown_complete = _desktop_host._request_shutdown(
            FakeManager(),
            server,
            server_thread,
            server_socket,
            stream=stdout,
        )

        self.assertFalse(shutdown_complete)
        self.assertEqual(
            {
                "event": "shutdown_incomplete",
                "message": "Timed out waiting for the active WebUI run to finish cleanup.",
            },
            json.loads(stdout.getvalue()),
        )
        self.assertFalse(server.should_exit)
        self.assertTrue(server_thread.is_alive())
        self.assertFalse(server_socket.closed)
        self.assertEqual(["server.start", "manager.shutdown"], events)


if __name__ == "__main__":
    unittest.main()
