from __future__ import annotations

import sys
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover - dependency-gated tests
    TestClient = None

if TestClient is not None:
    from meters_tool_core.models import KEYSIGHT_34461A_PROFILE, TriggerSource
    from meters_tool_webui._run_manager import _RunHandle, _WebControlPlane
    from meters_tool_webui.web_ui import (
        RunAlreadyActive,
        RunStartRequest,
        WebRunManager,
        create_app,
        create_uvicorn_server,
    )


from webui_test_helpers import (
    cleanup_tempdir,
    make_api_client,
    wait_until_inactive,
)

@unittest.skipIf(TestClient is None, "FastAPI test dependencies are not installed")
class WebUiRunControlApiTests(unittest.TestCase):
    def tearDown(self):
        cleanup_tempdir(self)

    def test_control_plane_delivers_pending_stop_when_start_registers_callbacks(self):
        ready_calls = []
        stop_calls = []

        class FakeRouter:
            def __init__(self):
                self.events = []

            def publish(self, event):
                self.events.append(event)
                return True

        router = FakeRouter()
        control_plane = _WebControlPlane(lambda: ready_calls.append("ready"))

        control_plane.stop_run()

        self.assertEqual([], router.events)
        self.assertEqual([], stop_calls)

        control_plane.start(
            router=router,
            port=0,
            min_interval_ms=0,
            queue_max=0,
            stop_cb=lambda: stop_calls.append("stop"),
            status_provider=lambda: {},
        )

        self.assertEqual(["ready"], ready_calls)
        self.assertEqual(["stop"], stop_calls)
        self.assertEqual(1, len(router.events))
        self.assertEqual(TriggerSource.SOFTWARE, router.events[0].source)
        self.assertEqual("stop", router.events[0].metadata.get("control"))

    def test_software_trigger_updates_status_and_captures(self):
        client, csv_path = make_api_client(self)
        response = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "instrument_model": "34461A",
                "csv": str(csv_path),
                "simulate": True,
                "trigger_mode": "software",
                "trigger_timeout_ms": 500,
                "max_samples": 1,
            },
        )
        self.assertEqual(200, response.status_code)

        triggered = client.post(
            "/api/runs/current/command",
            json={
                "metadata": {
                    "source": "web-ui",
                    "operator": "tom",
                    "batch": 2,
                },
            },
        )
        self.assertEqual(202, triggered.status_code)
        self.assertEqual(
            {
                "status": "accepted",
                "message": "software trigger queued",
            },
            triggered.json(),
        )
        self.assertEqual(
            404,
            client.post(
                "/api/runs/current/trigger",
                json={
                    "command": "software_trigger",
                    "arguments": {"metadata": {}},
                },
            ).status_code,
        )
        deadline = time.monotonic() + 1.0
        status = {}
        while time.monotonic() < deadline:
            status = client.get("/api/runs/current").json()
            if status["captured"] == 1 and not status["active"]:
                break
            time.sleep(0.02)

        self.assertEqual(1, status["captured"])
        self.assertFalse(status["active"])
        self.assertEqual("stopped", status["state"])
        self.assertEqual(5000, status["sample_capacity"])
        self.assertEqual(1, len(status["recent_samples"]))
        sample = status["latest_sample"]
        self.assertEqual(sample, status["recent_samples"][-1])
        self.assertEqual(1, sample["sequence"])
        self.assertEqual("current_dc", sample["measurement_type"])
        self.assertAlmostEqual(1.23, sample["value"])
        self.assertEqual("A", sample["unit"])
        self.assertEqual("ok", sample["status"])
        self.assertEqual("USB::FAKE", sample["resource_id"])
        self.assertEqual("software", sample["trigger_source"])
        self.assertEqual("2", sample["trigger_metadata"]["batch"])
        self.assertEqual("tom", sample["trigger_metadata"]["operator"])
        self.assertEqual("web-ui", sample["trigger_metadata"]["source"])
        self.assertRegex(sample["timestamp_utc_plus_8"], r"\+08:00$")
        self.assertIsInstance(sample["measurement_metadata"], dict)

    def test_command_endpoint_rejects_invalid_private_payload_without_triggering(self):
        client, csv_path = make_api_client(self)
        response = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "instrument_model": "34461A",
                "csv": str(csv_path),
                "simulate": True,
                "trigger_mode": "software",
                "trigger_timeout_ms": 500,
                "max_samples": 1,
            },
        )
        self.assertEqual(200, response.status_code)

        invalid_payloads = (
            [],
            {"metadata": []},
            {
                "schema_version": 2,
                "command": "software_trigger",
                "arguments": {"metadata": {}},
            },
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                rejected = client.post("/api/runs/current/command", json=payload)
                self.assertEqual(400, rejected.status_code)
                self.assertEqual("error", rejected.json()["status"])
                self.assertEqual("validation_error", rejected.json()["error"])
                status = client.get("/api/runs/current").json()
                self.assertEqual(0, status["captured"])
                self.assertNotEqual(
                    "software trigger queued",
                    status["latest_status"],
                )

        accepted = client.post("/api/runs/current/command", json={})
        self.assertEqual(202, accepted.status_code)
        status = wait_until_inactive(client)
        self.assertEqual(1, status["captured"])
        self.assertEqual({}, status["latest_sample"]["trigger_metadata"])

    def test_command_endpoint_preserves_rate_limit_status(self):
        client, csv_path = make_api_client(self)
        started = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "instrument_model": "34461A",
                "csv": str(csv_path),
                "simulate": True,
                "trigger_mode": "software-custom",
                "trigger_timeout_ms": 500,
                "trigger_count": 2,
                "sample_count": 1,
                "sw_min_interval_ms": 60_000,
            },
        )
        self.assertEqual(200, started.status_code)

        accepted = client.post("/api/runs/current/command", json={})
        rejected = client.post("/api/runs/current/command", json={})

        self.assertEqual(202, accepted.status_code)
        self.assertEqual(429, rejected.status_code)
        self.assertEqual(
            {"status": "rejected", "reason": "rate_limited"},
            rejected.json(),
        )
        client.post("/api/runs/current/stop")
        self.assertFalse(wait_until_inactive(client)["active"])

    def test_command_endpoint_returns_private_validation_and_no_active_errors(self):
        client, _ = make_api_client(self)

        no_active = client.post(
            "/api/runs/current/command",
            json={},
        )
        malformed = client.post(
            "/api/runs/current/command",
            content="{bad json",
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(409, no_active.status_code)
        self.assertEqual(
            {
                "status": "error",
                "error": "no_active_run",
                "message": "no active run",
            },
            no_active.json(),
        )
        self.assertEqual(400, malformed.status_code)
        self.assertEqual("error", malformed.json()["status"])
        self.assertEqual("validation_error", malformed.json()["error"])
        self.assertIn("malformed JSON", malformed.json()["message"])

    def test_webui_server_exit_gracefully_shuts_down_manager_first(self):
        events = []

        class FakeManager:
            def shutdown(self):
                events.append("manager.shutdown")
                return True

        class FakeConfig:
            def __init__(self, app, **kwargs):
                self.app = app
                self.kwargs = kwargs

        class FakeServer:
            def __init__(self, config):
                self.config = config

            def handle_exit(self, sig, frame):
                events.append("server.handle_exit")

        original_uvicorn = sys.modules.get("uvicorn")
        sys.modules["uvicorn"] = SimpleNamespace(Config=FakeConfig, Server=FakeServer)
        try:
            server = create_uvicorn_server(
                FakeManager(),
                host="127.0.0.1",
                port=8769,
            )
            server.handle_exit(None, None)
        finally:
            if original_uvicorn is None:
                sys.modules.pop("uvicorn", None)
            else:
                sys.modules["uvicorn"] = original_uvicorn

        self.assertEqual(["manager.shutdown", "server.handle_exit"], events)

    def test_manager_shutdown_stops_active_run_and_waits_for_worker(self):
        events = []

        class FakeControlPlane:
            def stop_run(self):
                events.append("stop")

        class FakeWorker:
            def __init__(self):
                self.alive = True

            def is_alive(self):
                return self.alive

            def join(self, timeout=None):
                events.append(("join", timeout))
                self.alive = False

        manager = WebRunManager()
        worker = FakeWorker()
        handle = _RunHandle(
            run_id="run-1",
            resource="SIM::34461A",
            csv_path=Path("out.csv"),
            measurement="voltage-dc",
            trigger_mode="immediate",
            control_plane=FakeControlPlane(),
            worker=worker,
            state="running",
        )
        with manager._lock:
            manager._active = handle

        self.assertTrue(manager.shutdown(timeout_s=0.01))

        self.assertEqual("stop", events[0])
        self.assertEqual("join", events[1][0])
        self.assertGreaterEqual(events[1][1], 0.0)
        self.assertLessEqual(events[1][1], 0.01)
        self.assertFalse(manager.status()["active"])
        self.assertTrue(manager._close_event_streams)

    def test_manager_shutdown_timeout_is_bounded_and_repeatable(self):
        stop_calls = []

        class FakeControlPlane:
            def stop_run(self):
                stop_calls.append("stop")

        class StuckWorker:
            def __init__(self):
                self.alive = True

            def is_alive(self):
                return self.alive

            def join(self, timeout=None):
                return None

        manager = WebRunManager()
        worker = StuckWorker()
        handle = _RunHandle(
            run_id="run-1",
            resource="SIM::34461A",
            csv_path=Path("out.csv"),
            measurement="voltage-dc",
            trigger_mode="immediate",
            control_plane=FakeControlPlane(),
            worker=worker,
            state="running",
        )
        with manager._lock:
            manager._active = handle

        started = time.monotonic()
        self.assertFalse(manager.shutdown(timeout_s=0.001))
        elapsed = time.monotonic() - started

        self.assertLess(elapsed, 0.2)
        self.assertEqual(["stop"], stop_calls)
        self.assertEqual("stopping", manager.status()["state"])
        self.assertFalse(manager._close_event_streams)

        worker.alive = False

        self.assertTrue(manager.shutdown(timeout_s=0.001))
        self.assertEqual(["stop"], stop_calls)
        self.assertTrue(manager._close_event_streams)

    def test_manager_rejects_new_start_after_shutdown_requested(self):
        manager = WebRunManager()
        request = RunStartRequest(
            resource="SIM::34461A",
            instrument_model="34461A",
            simulate=True,
            trigger_mode="immediate",
            max_samples=1,
        )

        self.assertTrue(manager.shutdown(timeout_s=0.0))

        with (
            patch("meters_tool_webui._run_manager.threading.Thread") as worker_factory,
            self.assertRaisesRegex(RunAlreadyActive, "shutting down"),
        ):
            manager.start(request)

        worker_factory.assert_not_called()
        with manager._lock:
            self.assertFalse(manager._starting)
            self.assertIsNone(manager._active)

    def test_shutdown_during_start_preflight_prevents_worker_start(self):
        manager = WebRunManager()
        request = RunStartRequest(
            resource="SIM::34461A",
            instrument_model="34461A",
            simulate=True,
            trigger_mode="immediate",
            max_samples=1,
        )
        preflight_entered = threading.Event()
        release_preflight = threading.Event()
        start_errors = []

        def blocking_resolve_start_profile(start_request):
            preflight_entered.set()
            if not release_preflight.wait(timeout=1.0):
                raise AssertionError("test did not release start preflight")
            return start_request, KEYSIGHT_34461A_PROFILE

        def run_start():
            try:
                manager.start(request)
            except Exception as exc:
                start_errors.append(exc)

        start_thread = threading.Thread(target=run_start)
        with (
            patch(
                "meters_tool_webui._run_manager.resolve_start_profile",
                side_effect=blocking_resolve_start_profile,
            ),
            patch("meters_tool_webui._run_manager.threading.Thread") as worker_factory,
        ):
            start_thread.start()
            self.assertTrue(preflight_entered.wait(timeout=1.0))
            self.assertFalse(manager.shutdown(timeout_s=0.001))
            release_preflight.set()
            start_thread.join(timeout=1.0)

        self.assertFalse(start_thread.is_alive())
        self.assertEqual(1, len(start_errors))
        self.assertIsInstance(start_errors[0], RunAlreadyActive)
        worker_factory.assert_not_called()
        with manager._lock:
            self.assertFalse(manager._starting)
            self.assertIsNone(manager._active)

    def test_current_run_events_returns_initial_status_snapshot(self):
        manager = WebRunManager()
        app = create_app(manager)
        route_fn = next(route.endpoint for route in app.routes if route.path == "/api/runs/current/events")
        response = route_fn()

        self.assertEqual("text/event-stream", response.media_type)

        import asyncio

        async def get_next(async_gen):
            async for item in async_gen:
                return item

        first_event = asyncio.run(get_next(response.body_iterator))
        self.assertTrue(first_event.startswith("event: run-status"))
        self.assertIn("id: 0", first_event)
        self.assertIn('"state":"idle"', first_event)
        self.assertIn('"active":false', first_event)

        manager.close_event_streams()
        self.assertIsNone(asyncio.run(get_next(response.body_iterator)))

    def test_status_event_stream_yields_published_status_updates(self):
        manager = WebRunManager()
        events = manager.iter_status_events()

        first_event = next(events)
        self.assertTrue(first_event.startswith("event: run-status"))
        self.assertIn("id: 0", first_event)
        self.assertIn('"state":"idle"', first_event)

        next_status = {
            **manager.status(),
            "state": "running",
            "active": True,
            "latest_status": "ready",
        }
        with manager._lock:
            manager._publish_status_locked(next_status)

        second_event = next(events)
        self.assertTrue(second_event.startswith("event: run-status"))
        self.assertIn("id: 1", second_event)
        self.assertIn('"state":"running"', second_event)
        self.assertIn('"latest_status":"ready"', second_event)

        manager.close_event_streams()
        with self.assertRaises(StopIteration):
            next(events)


if __name__ == "__main__":
    unittest.main()
