from __future__ import annotations

import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from meters_tool_webui.launcher import (
    DEFAULT_PORT,
    LauncherApp,
    build_local_url,
    main,
    parse_port,
    run_self_test,
)


class LauncherHelperTests(unittest.TestCase):
    def test_default_url_uses_loopback_and_default_port(self):
        self.assertEqual("http://127.0.0.1:8767", build_local_url(DEFAULT_PORT))

    def test_parse_port_rejects_invalid_values(self):
        for value in ("", "abc", "0", "65536"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_port(value)

    def test_parse_port_accepts_valid_values(self):
        self.assertEqual(8767, parse_port("8767"))
        self.assertEqual(8080, parse_port(" 8080 "))

    def test_self_test_succeeds_with_required_static_resources(self):
        with (
            patch("meters_tool_webui.launcher.import_module"),
            patch("meters_tool_webui.launcher.files") as resource_files,
        ):
            static_root = resource_files.return_value.joinpath.return_value
            static_root.joinpath.return_value.is_file.return_value = True

            self.assertEqual(0, run_self_test())

    def test_self_test_fails_when_static_resource_is_missing(self):
        with (
            patch("meters_tool_webui.launcher.import_module"),
            patch("meters_tool_webui.launcher.files") as resource_files,
        ):
            static_root = resource_files.return_value.joinpath.return_value
            static_root.joinpath.return_value.is_file.side_effect = [True, False, True]

            self.assertEqual(1, run_self_test())

    @patch("meters_tool_webui.launcher.tk.Tk")
    def test_self_test_does_not_create_tk_root(self, tk_root):
        self.assertEqual(0, main(["--self-test"]))
        tk_root.assert_not_called()

    def test_script_entry_point_is_after_readiness_helper(self):
        source = (
            Path(__file__).parents[2]
            / "src"
            / "meters_tool_webui"
            / "launcher.py"
        ).read_text(encoding="utf-8")

        self.assertLess(
            source.index("def _server_is_ready"),
            source.index('if __name__ == "__main__"'),
        )


class LauncherLifecycleTests(unittest.TestCase):
    def test_idle_quit_shuts_down_manager_server_and_window(self):
        events = []

        class FakeManager:
            def shutdown(self):
                events.append("manager.shutdown")
                return True

        class FakeServer:
            should_exit = False

        launcher = _make_shutdown_launcher(
            manager=FakeManager(),
            server=FakeServer(),
            events=events,
        )
        launcher.quit()

        self.assertEqual(["manager.shutdown", "window.destroy"], events)
        self.assertTrue(launcher.server.should_exit)

    def test_active_quit_waits_for_manager_before_stopping_server(self):
        events = []

        class FakeManager:
            def shutdown(self):
                events.extend(["manager.stop", "worker.join"])
                return True

        class FakeServer:
            def __init__(self):
                self._should_exit = False

            @property
            def should_exit(self):
                return self._should_exit

            @should_exit.setter
            def should_exit(self, value):
                self._should_exit = value
                events.append("server.should_exit")

        class FakeServerThread:
            def is_alive(self):
                return True

            def join(self, timeout=None):
                events.append("server.join")

        launcher = _make_shutdown_launcher(
            manager=FakeManager(),
            server=FakeServer(),
            server_thread=FakeServerThread(),
            events=events,
        )
        launcher.quit()

        self.assertEqual(
            [
                "manager.stop",
                "worker.join",
                "server.should_exit",
                "server.join",
                "window.destroy",
            ],
            events,
        )

    def test_repeated_quit_only_starts_shutdown_once(self):
        shutdown_calls = []

        class FakeManager:
            def shutdown(self):
                shutdown_calls.append("shutdown")
                return True

        launcher = _make_shutdown_launcher(manager=FakeManager())
        launcher.quit()
        launcher.quit()

        self.assertEqual(["shutdown"], shutdown_calls)

    def test_shutdown_timeout_keeps_launcher_open_and_retry_completes_exit(self):
        class FakeManager:
            def __init__(self):
                self.shutdown_results = iter((False, True))

            def shutdown(self):
                return next(self.shutdown_results)

        class FakeServer:
            should_exit = False

        class FakeServerThread:
            def __init__(self):
                self.join_calls = 0

            def is_alive(self):
                return True

            def join(self, timeout=None):
                self.join_calls += 1

        events = []
        server_thread = FakeServerThread()
        launcher = _make_shutdown_launcher(
            manager=FakeManager(),
            server=FakeServer(),
            server_thread=server_thread,
            events=events,
        )

        started = time.monotonic()
        with patch("meters_tool_webui.launcher.messagebox.showerror") as showerror:
            launcher.quit()
        elapsed = time.monotonic() - started

        self.assertLess(elapsed, 1.0)
        self.assertFalse(launcher.server.should_exit)
        self.assertEqual(0, server_thread.join_calls)
        self.assertEqual([], events)
        self.assertFalse(launcher._quitting)
        self.assertEqual("normal", launcher._quit_button.state)
        self.assertEqual("disabled", launcher._start_button.state)
        self.assertEqual("disabled", launcher._default_checkbox.state)
        self.assertEqual("disabled", launcher._port_entry.state)
        self.assertEqual(
            "Shutdown incomplete: Timed out waiting for the active run to finish cleanup.",
            launcher._status_value.value,
        )
        showerror.assert_called_once_with(
            "Shutdown incomplete",
            "Timed out waiting for the active run to finish cleanup.",
        )

        launcher.quit()

        self.assertTrue(launcher.server.should_exit)
        self.assertEqual(1, server_thread.join_calls)
        self.assertEqual(["window.destroy"], events)

    def test_start_locks_controls_opens_browser_and_quit_stops_server(self):
        tk, root = _make_tk_root()
        root.withdraw()
        opened_urls = []
        servers = []

        class FakeServer:
            def __init__(self):
                self.should_exit = False
                self.run_called = False

            def run(self):
                self.run_called = True
                while not self.should_exit:
                    time.sleep(0.01)

        def server_factory(_manager, port):
            self.assertEqual(DEFAULT_PORT, port)
            server = FakeServer()
            servers.append(server)
            return server

        try:
            readiness_calls = []

            def readiness(_url):
                readiness_calls.append(_url)
                return len(readiness_calls) > 1

            launcher = LauncherApp(
                root,
                server_factory=server_factory,
                browser_open=opened_urls.append,
                readiness_checker=readiness,
                http_checker=lambda _url: False,
            )

            with patch("meters_tool_webui.launcher.messagebox.showerror") as showerror:
                launcher.start()
                _drain_tk_events(root, condition=lambda: bool(opened_urls))

            self.assertEqual(["http://127.0.0.1:8767"], opened_urls)
            showerror.assert_not_called()
            self.assertEqual("disabled", launcher._start_button.cget("state"))
            self.assertEqual("disabled", launcher._port_entry.cget("state"))
            self.assertIs(servers[0], launcher.server)
            self.assertIsNotNone(launcher.server_thread)
            launcher.server_thread.join(timeout=1.0)
            self.assertTrue(servers[0].run_called)

            launcher.quit()

            self.assertTrue(servers[0].should_exit)
        finally:
            try:
                root.destroy()
            except tk.TclError:
                pass

    def test_existing_webui_readiness_opens_browser_without_starting_server(self):
        tk, root = _make_tk_root()
        root.withdraw()
        opened_urls = []
        server_factory_called = False

        def server_factory(_manager, _port):
            nonlocal server_factory_called
            server_factory_called = True
            raise AssertionError("already-running WebUI should not start a second server")

        try:
            launcher = LauncherApp(
                root,
                server_factory=server_factory,
                browser_open=opened_urls.append,
                readiness_checker=lambda _url: True,
                http_checker=lambda _url: False,
            )

            with patch("meters_tool_webui.launcher.messagebox.showerror") as showerror:
                launcher.start()
                _drain_tk_events(root)

            self.assertFalse(server_factory_called)
            self.assertEqual(["http://127.0.0.1:8767"], opened_urls)
            self.assertIsNone(launcher.server_thread)
            self.assertIn("Server already running", launcher._status_value.get())
            showerror.assert_not_called()
        finally:
            try:
                root.destroy()
            except tk.TclError:
                pass

    def test_server_exits_before_readiness_reports_start_failed(self):
        tk, root = _make_tk_root()
        root.withdraw()

        class FailingServer:
            should_exit = False

            def run(self):
                raise SystemExit(1)

        try:
            launcher = LauncherApp(
                root,
                server_factory=lambda _manager, _port: FailingServer(),
                browser_open=lambda _url: None,
                readiness_checker=lambda _url: False,
                http_checker=lambda _url: False,
            )

            with patch("meters_tool_webui.launcher.messagebox.showerror") as showerror:
                launcher.start()
                _drain_tk_events(root, condition=lambda: showerror.called)

            showerror.assert_called_once()
            title, message = showerror.call_args.args
            self.assertEqual("Start failed", title)
            self.assertIn("SystemExit: 1", message)
        finally:
            try:
                root.destroy()
            except tk.TclError:
                pass

    def test_system_exit_after_readiness_success_does_not_show_start_failed(self):
        tk, root = _make_tk_root()
        root.withdraw()
        opened_urls = []
        ready_seen = threading.Event()

        class ExitingAfterReadyServer:
            should_exit = False

            def run(self):
                while not ready_seen.is_set():
                    time.sleep(0.01)
                raise SystemExit(1)

        readiness_calls = []

        def readiness(_url):
            readiness_calls.append(_url)
            if len(readiness_calls) == 1:
                return False
            ready_seen.set()
            return True

        try:
            launcher = LauncherApp(
                root,
                server_factory=lambda _manager, _port: ExitingAfterReadyServer(),
                browser_open=opened_urls.append,
                readiness_checker=readiness,
                http_checker=lambda _url: False,
            )

            with patch("meters_tool_webui.launcher.messagebox.showerror") as showerror:
                launcher.start()
                _drain_tk_events(root, condition=lambda: bool(opened_urls))
                if launcher.server_thread is not None:
                    launcher.server_thread.join(timeout=1.0)
                _drain_tk_events(root)

            self.assertEqual(["http://127.0.0.1:8767"], opened_urls)
            showerror.assert_not_called()
        finally:
            try:
                root.destroy()
            except tk.TclError:
                pass

    def test_new_server_root_ready_opens_browser_when_capabilities_not_ready(self):
        tk, root = _make_tk_root()
        root.withdraw()
        opened_urls = []
        server_started = threading.Event()
        servers = []

        class FakeServer:
            def __init__(self):
                self.should_exit = False

            def run(self):
                server_started.set()
                while not self.should_exit:
                    time.sleep(0.01)

        def server_factory(_manager, _port):
            server = FakeServer()
            servers.append(server)
            return server

        try:
            launcher = LauncherApp(
                root,
                server_factory=server_factory,
                browser_open=opened_urls.append,
                readiness_checker=lambda _url: False,
                http_checker=lambda _url: server_started.is_set(),
            )

            with patch("meters_tool_webui.launcher.messagebox.showerror") as showerror:
                launcher.start()
                _drain_tk_events(root, condition=lambda: bool(opened_urls))

            self.assertEqual(["http://127.0.0.1:8767"], opened_urls)
            self.assertIn("Running at", launcher._status_value.get())
            showerror.assert_not_called()

            launcher.quit()
            self.assertTrue(servers[0].should_exit)
        finally:
            try:
                root.destroy()
            except tk.TclError:
                pass

    def test_existing_non_webui_http_service_reports_conflict(self):
        tk, root = _make_tk_root()
        root.withdraw()
        opened_urls = []
        server_factory_called = False

        def server_factory(_manager, _port):
            nonlocal server_factory_called
            server_factory_called = True
            raise AssertionError("non-WebUI port conflict should not start a server")

        try:
            launcher = LauncherApp(
                root,
                server_factory=server_factory,
                browser_open=opened_urls.append,
                readiness_checker=lambda _url: False,
                http_checker=lambda _url: True,
            )

            with patch("meters_tool_webui.launcher.messagebox.showerror") as showerror:
                launcher.start()
                _drain_tk_events(root)

            self.assertFalse(server_factory_called)
            self.assertEqual([], opened_urls)
            showerror.assert_called_once()
            title, message = showerror.call_args.args
            self.assertEqual("Start failed", title)
            self.assertIn("Port 8767 is already in use", message)
            self.assertEqual("normal", launcher._start_button.cget("state"))
        finally:
            try:
                root.destroy()
            except tk.TclError:
                pass


def _import_tkinter():
    try:
        import tkinter as tk
    except Exception as exc:  # pragma: no cover - environment dependent
        raise unittest.SkipTest(f"tkinter is unavailable: {exc}") from exc
    return tk


def _make_shutdown_launcher(
    *,
    manager=None,
    server=None,
    server_thread=None,
    events=None,
):
    class FakeControl:
        state = "normal"

        def configure(self, **_kwargs):
            if "state" in _kwargs:
                self.state = _kwargs["state"]

    class FakeStatus:
        value = ""

        def set(self, value):
            self.value = value

    class FakeRoot:
        def update_idletasks(self):
            return None

        def destroy(self):
            if events is not None:
                events.append("window.destroy")

    launcher = LauncherApp.__new__(LauncherApp)
    launcher._root = FakeRoot()
    launcher._manager = manager
    launcher._server = server
    launcher._server_thread = server_thread
    launcher._quitting = False
    launcher._start_button = FakeControl()
    launcher._default_checkbox = FakeControl()
    launcher._port_entry = FakeControl()
    launcher._quit_button = FakeControl()
    launcher._status_value = FakeStatus()
    return launcher


def _make_tk_root():
    tk = _import_tkinter()
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        raise unittest.SkipTest(f"tkinter display is unavailable: {exc}") from exc
    return tk, root


def _drain_tk_events(root, timeout_s: float = 1.0, condition=None):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        root.update()
        if condition is not None and condition():
            return
        time.sleep(0.01)


if __name__ == "__main__":
    unittest.main()
