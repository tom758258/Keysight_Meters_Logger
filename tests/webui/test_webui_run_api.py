from __future__ import annotations

import tempfile
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
    from meters_tool_core.instrument import InstrumentError
    from meters_tool_core.models import KEYSIGHT_34461A_PROFILE
    from meters_tool_core.runner import StartRunnerDependencies
    from meters_tool_webui.web_ui import (
        RunAlreadyActive,
        RunStartRequest,
        WebRunManager,
    )


from webui_test_helpers import (
    cleanup_tempdir,
    make_api_client,
    make_api_client_with_manager,
    wait_until_inactive,
)

@unittest.skipIf(TestClient is None, "FastAPI test dependencies are not installed")
class WebUiRunApiTests(unittest.TestCase):
    def tearDown(self):
        cleanup_tempdir(self)

    def test_run_start_rejects_second_active_run_and_stop_releases_it(self):
        client, csv_path = make_api_client(self)
        request = {
            "resource": "USB::FAKE",
            "instrument_model": "34461A",
            "csv": str(csv_path),
            "simulate": True,
            "trigger_mode": "software-custom",
            "trigger_timeout_ms": 500,
            "trigger_count": 1,
            "sample_count": 1,
        }

        first = client.post("/api/runs", json=request)
        second = client.post("/api/runs", json=request)
        stopped = client.post("/api/runs/current/stop")

        self.assertEqual(200, first.status_code)
        self.assertEqual(409, second.status_code)
        self.assertEqual(202, stopped.status_code)
        self.assertIn(stopped.json()["state"], {"running", "stopping", "stopped"})
        self.assertFalse(wait_until_inactive(client)["active"])

    def test_run_start_rejects_second_run_while_active(self):
        tempdir = tempfile.TemporaryDirectory()
        self.tempdir = tempdir
        csv_path = Path(tempdir.name) / "out.csv"
        manager = WebRunManager()
        request = RunStartRequest(
            resource="USB::FAKE",
            instrument_model="34461A",
            csv=str(csv_path),
            simulate=True,
            trigger_mode="software-custom",
            trigger_timeout_ms=500,
            trigger_count=1,
            sample_count=1,
        )
        started = manager.start(request)
        self.assertTrue(started["active"])

        with self.assertRaises(RunAlreadyActive):
            manager.start(request)

        manager.stop()
        deadline = time.monotonic() + 1.0
        while manager.status()["active"] and time.monotonic() < deadline:
            time.sleep(0.02)

    def test_live_data_retains_latest_5000_samples_until_next_start(self):
        self.tempdir = tempfile.TemporaryDirectory()
        csv_path = Path(self.tempdir.name) / "out.csv"
        manager = WebRunManager()
        client = make_api_client_with_manager(manager)
        response = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "instrument_model": "34461A",
                "csv": str(csv_path),
                "simulate": True,
                "trigger_mode": "immediate",
                "max_samples": 1,
            },
        )
        self.assertEqual(200, response.status_code)
        initial_status = wait_until_inactive(client, timeout_s=1.0)
        self.assertEqual(1, initial_status["captured"])

        for sequence in range(2, 5006):
            manager._record_event(
                SimpleNamespace(
                    run_id=initial_status["run_id"],
                    event="sample",
                    message=None,
                    captured=sequence,
                    sample=SimpleNamespace(
                        timestamp_utc=None,
                        measurement_type="current_dc",
                        value=1.23,
                        unit="A",
                        trigger_id=None,
                        trigger_source="immediate",
                        trigger_metadata={},
                        measurement_metadata={},
                        resource_id="USB::FAKE",
                        status="ok",
                    ),
                )
            )

        status = client.get("/api/runs/current").json()

        self.assertEqual(5005, status["captured"])
        self.assertFalse(status["active"])
        self.assertEqual(5000, status["sample_capacity"])
        self.assertEqual(5000, len(status["recent_samples"]))
        self.assertEqual(6, status["recent_samples"][0]["sequence"])
        self.assertEqual(5005, status["recent_samples"][-1]["sequence"])
        self.assertEqual(status["recent_samples"][-1], status["latest_sample"])

        next_csv_path = csv_path.with_name("next.csv")
        restarted = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "instrument_model": "34461A",
                "csv": str(next_csv_path),
                "simulate": True,
                "trigger_mode": "immediate",
                "max_samples": 1,
            },
        )
        self.assertEqual(200, restarted.status_code)
        restarted_status = wait_until_inactive(client, timeout_s=1.0)

        self.assertEqual(1, restarted_status["captured"])
        self.assertEqual(1, len(restarted_status["recent_samples"]))
        self.assertEqual(1, restarted_status["latest_sample"]["sequence"])

    def test_start_validation_reuses_cli_constraints(self):
        client, csv_path = make_api_client(self)

        response = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "instrument_model": "34461A",
                "csv": str(csv_path),
                "simulate": True,
                "auto_range": False,
                "measurement": "voltage-dc",
            },
        )

        self.assertEqual(422, response.status_code)
        self.assertIn("--range is required when --auto-range off", response.json()["detail"])

    def test_start_validation_rejects_cli_limit_violations(self):
        client, csv_path = make_api_client(self)
        cases = [
            ({"timeout_ms": 99}, "--timeout-ms 99 is outside"),
            ({"timer_interval_s": 0.01}, "--timer-interval-s 0.01 is below"),
            ({"sw_queue_max": 10001}, "--sw-queue-max 10001 is outside"),
        ]

        for extra_payload, expected_detail in cases:
            with self.subTest(extra_payload=extra_payload):
                response = client.post(
                    "/api/runs",
                    json={
                        "resource": "USB::FAKE",
                        "instrument_model": "34461A",
                        "csv": str(csv_path),
                        "simulate": True,
                        **extra_payload,
                    },
                )

                self.assertEqual(422, response.status_code)
                self.assertIn(expected_detail, response.json()["detail"])

    def test_start_rejects_model_mode_payload_field(self):
        client, csv_path = make_api_client(self)

        response = client.post(
            "/api/runs",
            json={
                "resource": "SIM::34461A",
                "csv": str(csv_path),
                "simulate": True,
                "model_mode": "auto",
                "trigger_mode": "immediate",
                "max_samples": 1,
            },
        )

        self.assertEqual(422, response.status_code)
        self.assertEqual(
            "model_mode/modelMode is not supported; use instrument_model only",
            response.json()["detail"],
        )

    def test_start_simulate_omitted_non_deterministic_model_returns_clear_error(self):
        client, csv_path = make_api_client(self)

        response = client.post(
            "/api/runs",
            json={
                "resource": "SIM::INSTR",
                "csv": str(csv_path),
                "simulate": True,
                "trigger_mode": "immediate",
                "max_samples": 1,
            },
        )

        self.assertEqual(422, response.status_code)
        self.assertEqual(
            "simulate cannot auto-detect the instrument model unless the simulator resource encodes it; "
            "pass --model 34460A or --model 34461A, or use SIM::34460A / SIM::34461A.",
            response.json()["detail"],
        )

    def test_start_validation_uses_selected_34460a_profile(self):
        client, csv_path = make_api_client(self)

        range_response = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "csv": str(csv_path),
                "simulate": True,
                "instrument_model": "34460A",
                "measurement": "current-dc",
                "auto_range": False,
                "measurement_range": 10.0,
                "trigger_mode": "immediate",
                "max_samples": 1,
            },
        )
        overflow_response = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "csv": str(csv_path),
                "simulate": True,
                "instrument_model": "34460A",
                "measurement": "voltage-dc",
                "trigger_mode": "immediate-custom",
                "trigger_count": 1,
                "sample_count": 1001,
            },
        )
        external_response = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "csv": str(csv_path),
                "simulate": True,
                "instrument_model": "34460A",
                "measurement": "current-dc",
                "trigger_mode": "external",
                "max_samples": 1,
            },
        )
        current_terminal_response = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "csv": str(csv_path),
                "simulate": True,
                "instrument_model": "34460A",
                "measurement": "current-dc",
                "trigger_mode": "immediate",
                "max_samples": 1,
                "current_terminal": 3,
            },
        )
        allowed_response = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "csv": str(csv_path),
                "simulate": True,
                "instrument_model": "34460A",
                "measurement": "voltage-dc",
                "trigger_mode": "immediate-custom",
                "trigger_count": 1,
                "sample_count": 1001,
                "allow_buffer_overflow_risk": True,
            },
        )

        self.assertEqual(422, range_response.status_code)
        self.assertIn("--range 10 is not valid", range_response.json()["detail"])
        self.assertEqual(422, overflow_response.status_code)
        self.assertIn("34460A reading memory 1000", overflow_response.json()["detail"])
        self.assertEqual(422, external_response.status_code)
        self.assertIn(
            "--trigger-mode external is not supported by 34460A",
            external_response.json()["detail"],
        )
        self.assertEqual(422, current_terminal_response.status_code)
        self.assertIn(
            "--current-terminal can only be used with --measurement current-dc or current-ac",
            current_terminal_response.json()["detail"],
        )
        self.assertEqual(200, allowed_response.status_code)
        client.post("/api/runs/current/stop")
        wait_until_inactive(client)

    def test_start_with_34460a_passes_expected_model_to_runner(self):
        self.tempdir = tempfile.TemporaryDirectory()
        csv_path = Path(self.tempdir.name) / "out.csv"
        seen_expected_models: list[str | None] = []

        class FakeInstrument:
            resource_id = "USB::FAKE"

            def connect(self):
                return None

            def release_to_local(self):
                return "release:ok"

            def close(self):
                return None

            def cleanup_release_to_local(self):
                return "cleanup:ok"

        class FakeStorage:
            def __init__(self, _path):
                return None

        class FakeEngine:
            def __init__(self, **_kwargs):
                self.stats = SimpleNamespace(captured=0, errors=0)
                self.fatal_error = None

            def run(self, *, trigger_mode, hardware_trigger_slope):  # noqa: ARG002
                return None

            def stop(self):
                return None

        class CompletedThread:
            def __init__(self, *, target, kwargs, daemon):  # noqa: ARG002
                self._target = target
                self._kwargs = kwargs
                self._alive = False

            def start(self):
                self._alive = True
                self._target(**self._kwargs)
                self._alive = False

            def is_alive(self):
                return self._alive

            def join(self, timeout=None):  # noqa: ARG002
                self._alive = False

        def instrument_factory(config, *, simulate, measurement_type):  # noqa: ARG001
            seen_expected_models.append(config.expected_model)
            return FakeInstrument()

        manager = WebRunManager(
            runner_dependencies=StartRunnerDependencies(
                instrument_backend_factory=instrument_factory,
                storage_factory=FakeStorage,
                measurement_factory=lambda _measurement_type: object(),
                engine_factory=lambda **kwargs: FakeEngine(**kwargs),
                thread_factory=CompletedThread,
            )
        )
        client = make_api_client_with_manager(manager)

        response = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "csv": str(csv_path),
                "simulate": True,
                "instrument_model": "34460A",
                "trigger_mode": "immediate",
                "max_samples": 1,
            },
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual(["34460A"], seen_expected_models)

    def test_start_omitted_live_model_uses_resolved_34460a_for_trigger_validation(self):
        self.tempdir = tempfile.TemporaryDirectory()
        csv_path = Path(self.tempdir.name) / "out.csv"
        seen_expected_models: list[str | None] = []

        def instrument_factory(config, *, simulate, measurement_type):  # noqa: ARG001
            seen_expected_models.append(config.expected_model)
            raise AssertionError("runner should not start for invalid resolved profile")

        manager = WebRunManager(
            runner_dependencies=StartRunnerDependencies(
                instrument_backend_factory=instrument_factory,
            )
        )
        client = make_api_client_with_manager(manager)

        with patch(
            "meters_tool_core.start_resolution.VisaInstrument.preflight_idn",
            return_value="Keysight Technologies,34460A,MY123,1.0",
        ):
            response = client.post(
                "/api/runs",
                json={
                    "resource": "USB::FAKE",
                    "csv": str(csv_path),
                    "trigger_mode": "external",
                    "max_samples": 1,
                },
            )

        self.assertEqual(422, response.status_code)
        self.assertIn("trigger-mode external", response.json()["detail"])
        self.assertEqual([], seen_expected_models)

    def test_start_omitted_live_model_uses_resolved_34460a_for_current_terminal_validation(self):
        self.tempdir = tempfile.TemporaryDirectory()
        csv_path = Path(self.tempdir.name) / "out.csv"
        seen_expected_models: list[str | None] = []

        def instrument_factory(config, *, simulate, measurement_type):  # noqa: ARG001
            seen_expected_models.append(config.expected_model)
            raise AssertionError("runner should not start for invalid resolved profile")

        manager = WebRunManager(
            runner_dependencies=StartRunnerDependencies(
                instrument_backend_factory=instrument_factory,
            )
        )
        client = make_api_client_with_manager(manager)

        with patch(
            "meters_tool_core.start_resolution.VisaInstrument.preflight_idn",
            return_value="Keysight Technologies,34460A,MY123,1.0",
        ):
            response = client.post(
                "/api/runs",
                json={
                    "resource": "USB::FAKE",
                    "csv": str(csv_path),
                    "measurement": "current-dc",
                    "current_terminal": 10,
                    "trigger_mode": "immediate",
                    "max_samples": 1,
                },
            )

        self.assertEqual(422, response.status_code)
        self.assertIn("current", response.json()["detail"].lower())
        self.assertEqual([], seen_expected_models)

    def test_start_omitted_live_model_resolves_from_fresh_preflight(self):
        self.tempdir = tempfile.TemporaryDirectory()
        csv_path = Path(self.tempdir.name) / "out.csv"
        seen_expected_models: list[str | None] = []

        class FakeInstrument:
            resource_id = "USB::FAKE"

            def connect(self):
                return None

            def release_to_local(self):
                return "release:ok"

            def close(self):
                return None

            def cleanup_release_to_local(self):
                return "cleanup:ok"

        class FakeStorage:
            def __init__(self, _path):
                return None

        class FakeEngine:
            def __init__(self, **_kwargs):
                self.stats = SimpleNamespace(captured=0, errors=0)
                self.fatal_error = None

            def run(self, *, trigger_mode, hardware_trigger_slope):  # noqa: ARG002
                return None

            def stop(self):
                return None

        class CompletedThread:
            def __init__(self, *, target, kwargs, daemon):  # noqa: ARG002
                self._target = target
                self._kwargs = kwargs
                self._alive = False

            def start(self):
                self._alive = True
                self._target(**self._kwargs)
                self._alive = False

            def is_alive(self):
                return self._alive

            def join(self, timeout=None):  # noqa: ARG002
                self._alive = False

        def instrument_factory(config, *, simulate, measurement_type):  # noqa: ARG001
            seen_expected_models.append(config.expected_model)
            return FakeInstrument()

        manager = WebRunManager(
            runner_dependencies=StartRunnerDependencies(
                instrument_backend_factory=instrument_factory,
                storage_factory=FakeStorage,
                measurement_factory=lambda _measurement_type: object(),
                engine_factory=lambda **kwargs: FakeEngine(**kwargs),
                thread_factory=CompletedThread,
            )
        )
        client = make_api_client_with_manager(manager)

        with patch(
            "meters_tool_core.start_resolution.VisaInstrument.preflight_idn",
            return_value="Keysight Technologies,34460A,MY123,1.0",
        ) as preflight:
            response = client.post(
                "/api/runs",
                json={
                    "resource": "USB::FAKE",
                    "csv": str(csv_path),
                    "simulate": False,
                    "trigger_mode": "immediate",
                    "max_samples": 1,
                },
            )

        self.assertEqual(200, response.status_code)
        self.assertEqual(["34460A"], seen_expected_models)
        self.assertEqual(2, preflight.call_count)

    def test_live_preflight_instrument_error_returns_503_and_resets_starting(self):
        self.tempdir = tempfile.TemporaryDirectory()
        csv_path = Path(self.tempdir.name) / "out.csv"
        manager = WebRunManager()
        client = make_api_client_with_manager(manager)

        with patch(
            "meters_tool_core.start_resolution.VisaInstrument.preflight_idn",
            side_effect=InstrumentError("failed to query instrument identity: boom"),
        ):
            response = client.post(
                "/api/runs",
                json={
                    "resource": "USB::BAD",
                    "csv": str(csv_path),
                    "trigger_mode": "immediate",
                    "max_samples": 1,
                },
            )

        follow_up = client.post(
            "/api/runs",
            json={
                "resource": " ",
                "csv": str(csv_path),
                "trigger_mode": "immediate",
                "max_samples": 1,
            },
        )

        self.assertEqual(503, response.status_code)
        self.assertIn("failed to query instrument identity", response.json()["detail"])
        self.assertEqual(422, follow_up.status_code)

    def test_runtime_connect_error_returns_503_and_resets_starting(self):
        self.tempdir = tempfile.TemporaryDirectory()
        csv_path = Path(self.tempdir.name) / "out.csv"

        class FakeInstrument:
            resource_id = "USB::FAKE"

            def connect(self):
                raise InstrumentError("failed to validate instrument identity: boom")

            def release_to_local(self):
                return "release:ok"

            def close(self):
                return None

            def cleanup_release_to_local(self):
                return "cleanup:ok"

        class FakeStorage:
            def __init__(self, _path):
                return None

        class FakeEngine:
            def __init__(self, **_kwargs):
                self.stats = SimpleNamespace(captured=0, errors=0)
                self.fatal_error = None

            def run(self, *, trigger_mode, hardware_trigger_slope):  # noqa: ARG002
                return None

            def stop(self):
                return None

        class CompletedThread:
            def __init__(self, *, target, kwargs, daemon):  # noqa: ARG002
                self._target = target
                self._kwargs = kwargs
                self._alive = False

            def start(self):
                self._alive = True
                self._target(**self._kwargs)
                self._alive = False

            def is_alive(self):
                return self._alive

            def join(self, timeout=None):  # noqa: ARG002
                self._alive = False

        def instrument_factory(config, *, simulate, measurement_type):  # noqa: ARG001
            return FakeInstrument()

        manager = WebRunManager(
            runner_dependencies=StartRunnerDependencies(
                instrument_backend_factory=instrument_factory,
                storage_factory=FakeStorage,
                measurement_factory=lambda _measurement_type: object(),
                engine_factory=lambda **kwargs: FakeEngine(**kwargs),
                thread_factory=CompletedThread,
            )
        )
        client = make_api_client_with_manager(manager)

        with patch(
            "meters_tool_core.start_resolution.VisaInstrument.preflight_idn",
            return_value="Keysight Technologies,34461A,MY123,1.0",
        ):
            response = client.post(
                "/api/runs",
                json={
                    "resource": "USB::FAKE",
                    "csv": str(csv_path),
                    "trigger_mode": "immediate",
                    "max_samples": 1,
                },
            )

        follow_up = client.post(
            "/api/runs",
            json={
                "resource": " ",
                "csv": str(csv_path),
                "trigger_mode": "immediate",
                "max_samples": 1,
            },
        )

        self.assertEqual(503, response.status_code)
        self.assertIn("boom", response.json()["detail"])
        self.assertEqual(422, follow_up.status_code)

    def test_model_idn_mismatch_returns_webui_action_message(self):
        self.tempdir = tempfile.TemporaryDirectory()
        csv_path = Path(self.tempdir.name) / "out.csv"

        manager = WebRunManager()
        client = make_api_client_with_manager(manager)

        with patch(
            "meters_tool_core.start_resolution.VisaInstrument.preflight_idn",
            return_value="Keysight Technologies,34460A,MY123,1.0",
        ):
            response = client.post(
                "/api/runs",
                json={
                    "resource": "USB::FAKE",
                    "instrument_model": "34461A",
                    "csv": str(csv_path),
                    "simulate": False,
                    "trigger_mode": "immediate",
                    "max_samples": 1,
                },
            )

        self.assertEqual(422, response.status_code)
        self.assertEqual(
            "Selected model 34461A does not match the connected instrument IDN 34460A. "
            "Select 34460A or omit --model to auto-detect.",
            response.json()["detail"],
        )

    def test_direct_live_post_34460a_allowed_workflow_reaches_runner(self):
        self.tempdir = tempfile.TemporaryDirectory()
        csv_path = Path(self.tempdir.name) / "out.csv"
        manager = WebRunManager()
        client = make_api_client_with_manager(manager)
        fake_result = SimpleNamespace(
            ok=True,
            reason="completed",
            captured=1,
            errors=0,
            fatal_error=None,
            csv_path=csv_path,
        )

        with (
            patch(
                "meters_tool_core.start_resolution.VisaInstrument.preflight_idn",
                return_value="Keysight Technologies,34460A,MY123,1.0",
            ),
            patch(
                "meters_tool_webui._run_manager.run_start_session",
                return_value=fake_result,
            ) as runner,
        ):
            response = client.post(
                "/api/runs",
                json={
                    "resource": "USB0::FAKE::INSTR",
                    "instrument_model": "34460A",
                    "csv": str(csv_path),
                    "simulate": False,
                    "measurement": "voltage-dc-ratio",
                    "trigger_mode": "immediate",
                    "max_samples": 1,
                },
            )

        self.assertEqual(200, response.status_code)
        runner.assert_called_once()
        request_arg, trigger_mode, profile = runner.call_args.args[:3]
        self.assertEqual("34460A", request_arg.instrument_model)
        self.assertEqual("voltage-dc-ratio", request_arg.measurement)
        self.assertEqual("immediate", trigger_mode)
        self.assertEqual("34460A", profile.model)

    def test_direct_live_post_34460a_policy_closed_workflow_fails_before_runner(self):
        self.tempdir = tempfile.TemporaryDirectory()
        csv_path = Path(self.tempdir.name) / "out.csv"
        manager = WebRunManager()
        client = make_api_client_with_manager(manager)
        cases = [
            (
                {
                    "resource": "TCPIP0::host::inst0::INSTR",
                    "instrument_model": "34460A",
                    "csv": str(csv_path),
                    "simulate": False,
                    "measurement": "voltage-dc-ratio",
                    "trigger_mode": "immediate",
                    "max_samples": 1,
                },
                "start-trigger-record is pending for transport=tcpip, backend=system_visa",
            ),
            (
                {
                    "resource": "TCPIP0::host::inst0::INSTR",
                    "instrument_model": "34460A",
                    "csv": str(csv_path),
                    "simulate": False,
                    "measurement": "voltage-dc",
                    "trigger_mode": "immediate",
                    "max_samples": 1,
                    "validation_allow_pending_live_support": True,
                },
                "start-trigger-record is pending for transport=tcpip, backend=system_visa",
            ),
        ]

        for payload, expected in cases:
            with self.subTest(expected=expected):
                with (
                    patch(
                        "meters_tool_core.start_resolution.VisaInstrument.preflight_idn",
                        return_value="Keysight Technologies,34460A,MY123,1.0",
                    ),
                    patch("meters_tool_webui._run_manager.run_start_session") as runner,
                ):
                    response = client.post("/api/runs", json=payload)

                self.assertEqual(422, response.status_code)
                self.assertIn(expected, response.json()["detail"])
                runner.assert_not_called()

    def test_selected_model_does_not_unlock_against_detected_live_model(self):
        self.tempdir = tempfile.TemporaryDirectory()
        csv_path = Path(self.tempdir.name) / "out.csv"
        manager = WebRunManager()
        client = make_api_client_with_manager(manager)

        with (
            patch(
                "meters_tool_core.start_resolution.VisaInstrument.preflight_idn",
                return_value="Keysight Technologies,34460A,MY123,1.0",
            ),
            patch("meters_tool_webui._run_manager.run_start_session") as runner,
        ):
            response = client.post(
                "/api/runs",
                json={
                    "resource": "USB0::FAKE::INSTR",
                    "instrument_model": "34461A",
                    "csv": str(csv_path),
                    "simulate": False,
                    "measurement": "voltage-dc-ratio",
                    "trigger_mode": "immediate",
                    "max_samples": 1,
                },
            )

        self.assertEqual(422, response.status_code)
        self.assertIn(
            "Selected model 34461A does not match the connected instrument IDN 34460A",
            response.json()["detail"],
        )
        runner.assert_not_called()

    def test_direct_post_runner_final_gate_rejects_if_adapter_resolution_is_wrong(self):
        self.tempdir = tempfile.TemporaryDirectory()
        csv_path = Path(self.tempdir.name) / "out.csv"
        manager = WebRunManager()
        client = make_api_client_with_manager(manager)

        def wrong_adapter_resolution(request_model):  # noqa: ANN001
            return request_model, KEYSIGHT_34461A_PROFILE

        with (
            patch(
                "meters_tool_webui._run_manager.resolve_start_profile",
                side_effect=wrong_adapter_resolution,
            ),
            patch("meters_tool_webui._run_manager.validate_start_request"),
            patch("meters_tool_webui._run_manager.validate_start_workflow_support"),
            patch(
                "meters_tool_core.start_resolution.VisaInstrument.preflight_idn",
                return_value="Keysight Technologies,34460A,MY123,1.0",
            ),
        ):
            response = client.post(
                "/api/runs",
                json={
                    "resource": "TCPIP0::host::inst0::INSTR",
                    "csv": str(csv_path),
                    "simulate": False,
                    "measurement": "voltage-dc",
                    "trigger_mode": "immediate",
                    "max_samples": 1,
                },
            )

        self.assertEqual(422, response.status_code)
        self.assertIn(
            "start-trigger-record is pending for transport=tcpip, backend=system_visa",
            response.json()["detail"],
        )

    def test_manager_can_build_default_request_model(self):
        request = RunStartRequest(resource="USB::FAKE")
        request_fields = getattr(RunStartRequest, "model_fields", None)
        if request_fields is None:
            request_fields = RunStartRequest.__fields__

        self.assertEqual("current-dc", request.measurement)
        self.assertTrue(request.csv_enabled)
        self.assertEqual("on", request.auto_zero)
        self.assertIsNone(request.ac_bandwidth_hz)
        self.assertIsNone(request.gate_time_s)
        self.assertIsNone(request.freq_period_timeout)
        self.assertIsNone(request.current_terminal)
        self.assertNotIn("validation_allow_pending_live_support", request_fields)
        self.assertNotIn("support_policy_mode", request_fields)

        normalized = WebRunManager()._normalize_request_payload(request)
        self.assertTrue(normalized.csv_enabled)

    def test_manager_normalizes_legacy_auto_zero_booleans(self):
        manager = WebRunManager()

        on_request = manager._normalize_request_payload(
            RunStartRequest(resource="USB::FAKE", auto_zero=True)
        )
        off_request = manager._normalize_request_payload(
            RunStartRequest(resource="USB::FAKE", auto_zero=False)
        )

        self.assertEqual("on", on_request.auto_zero)
        self.assertEqual("off", off_request.auto_zero)

    def test_api_normalizes_web_request_values_before_core_resolution(self):
        client, csv_path = make_api_client(self)
        captured_requests = []

        def capture_request(request):
            captured_requests.append(request)
            raise ValueError("normalization captured")

        with patch(
            "meters_tool_webui._run_manager.resolve_start_profile",
            side_effect=capture_request,
        ):
            response = client.post(
                "/api/runs",
                json={
                    "resource": "  USB::FAKE  ",
                    "csv": f"  {csv_path}  ",
                    "instrument_model": "  34461A  ",
                    "trigger_mode": "  IMMEDIATE  ",
                    "hw_trigger_slope": "  POS  ",
                    "vm_comp_slope": "  NEG  ",
                    "dcv_input_impedance": "  AUTO  ",
                    "auto_zero": "  TRUE  ",
                },
            )

        self.assertEqual(422, response.status_code)
        self.assertEqual("normalization captured", response.json()["detail"])
        self.assertEqual(1, len(captured_requests))
        normalized = captured_requests[0]
        self.assertEqual("USB::FAKE", normalized.resource)
        self.assertEqual(str(csv_path), normalized.csv)
        self.assertEqual("34461A", normalized.instrument_model)
        self.assertEqual("immediate", normalized.trigger_mode)
        self.assertEqual("pos", normalized.hw_trigger_slope)
        self.assertEqual("neg", normalized.vm_comp_slope)
        self.assertEqual("auto", normalized.dcv_input_impedance)
        self.assertEqual("on", normalized.auto_zero)

    def test_api_runs_validation_core_v1_1_0_contracts(self):
        client, csv_path = make_api_client(self)

        response = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "instrument_model": "34461A",
                "csv": str(csv_path),
                "simulate": True,
                "measurement": "current-dc",
                "auto_zero": "once",
                "trigger_mode": "software-custom",
                "trigger_timeout_ms": 500,
                "trigger_count": 1,
                "sample_count": 1,
            },
        )
        self.assertEqual(200, response.status_code)
        client.post("/api/runs/current/stop")
        wait_until_inactive(client)

        response = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "instrument_model": "34461A",
                "csv": str(csv_path),
                "simulate": True,
                "measurement": "period",
                "freq_period_timeout": "auto",
                "trigger_mode": "software-custom",
                "trigger_timeout_ms": 500,
                "trigger_count": 1,
                "sample_count": 1,
            },
        )
        self.assertEqual(422, response.status_code)
        self.assertIn(
            "--freq-period-timeout is not supported for --measurement period",
            response.json()["detail"],
        )

        response = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "instrument_model": "34461A",
                "csv": str(csv_path),
                "simulate": True,
                "measurement": "frequency",
                "ac_bandwidth_hz": 20.0,
                "gate_time_s": 0.1,
                "freq_period_timeout": "auto",
                "trigger_mode": "software-custom",
                "trigger_timeout_ms": 500,
                "trigger_count": 1,
                "sample_count": 1,
            },
        )
        self.assertEqual(200, response.status_code)
        client.post("/api/runs/current/stop")
        wait_until_inactive(client)

        response = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "instrument_model": "34461A",
                "csv": str(csv_path),
                "simulate": True,
                "measurement": "voltage-ac",
                "ac_bandwidth_hz": 200.0,
                "trigger_mode": "software-custom",
                "trigger_timeout_ms": 500,
                "trigger_count": 1,
                "sample_count": 1,
            },
        )
        self.assertEqual(200, response.status_code)
        client.post("/api/runs/current/stop")
        wait_until_inactive(client)

        response = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "instrument_model": "34461A",
                "csv": str(csv_path),
                "simulate": True,
                "measurement": "current-dc",
                "auto_range": False,
                "measurement_range": 10.0,
                "current_terminal": 10,
                "trigger_mode": "software-custom",
                "trigger_timeout_ms": 500,
                "trigger_count": 1,
                "sample_count": 1,
            },
        )
        self.assertEqual(200, response.status_code)
        client.post("/api/runs/current/stop")
        wait_until_inactive(client)

        response = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "instrument_model": "34461A",
                "csv": str(csv_path),
                "simulate": True,
                "measurement": "voltage-dc-ratio",
                "dcv_input_impedance": "10m",
                "trigger_mode": "software-custom",
                "trigger_timeout_ms": 500,
                "trigger_count": 1,
                "sample_count": 1,
            },
        )
        self.assertEqual(200, response.status_code)
        client.post("/api/runs/current/stop")
        wait_until_inactive(client)

        response = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "instrument_model": "34461A",
                "csv": str(csv_path),
                "simulate": True,
                "measurement": "current-dc",
                "auto_range": False,
                "measurement_range": 10.0,
                "current_terminal": 3,
                "trigger_mode": "software-custom",
                "trigger_timeout_ms": 500,
                "trigger_count": 1,
                "sample_count": 1,
            },
        )
        self.assertEqual(422, response.status_code)
        self.assertIn("cannot be used with the 10 A current range", response.json()["detail"])

    def test_api_rejects_frequency_period_fields_for_other_measurements(self):
        client, csv_path = make_api_client(self)

        response = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "instrument_model": "34461A",
                "csv": str(csv_path),
                "simulate": True,
                "measurement": "voltage-dc",
                "gate_time_s": 0.1,
                "trigger_mode": "immediate",
                "max_samples": 1,
            },
        )

        self.assertEqual(422, response.status_code)
        self.assertIn(
            "gate-time-s can only be used with --measurement frequency or period",
            response.json()["detail"],
        )

    def test_immediate_run_publishes_final_inactive_status_without_polling(self):
        self.tempdir = tempfile.TemporaryDirectory()
        csv_path = Path(self.tempdir.name) / "csv-only-parent" / "out.csv"

        def fail_storage_factory(*args, **kwargs):  # noqa: ARG001
            self.fail("no-CSV WebUI run must not create CSV storage")

        manager = WebRunManager(
            runner_dependencies=StartRunnerDependencies(
                storage_factory=fail_storage_factory,
            )
        )
        client = make_api_client_with_manager(manager)
        version_before = manager._status_version

        response = client.post(
            "/api/runs",
            json={
                "resource": "USB::FAKE",
                "instrument_model": "34461A",
                "csv": str(csv_path),
                "csv_enabled": False,
                "simulate": True,
                "trigger_mode": "immediate",
                "max_samples": 1,
            },
        )
        self.assertEqual(200, response.status_code)

        with manager._lock:
            handle = manager._active
        self.assertIsNotNone(handle)
        self.assertIsNotNone(handle.worker)
        handle.worker.join(timeout=1.0)

        with manager._lock:
            status = dict(manager._last_status)
            version_after = manager._status_version

        self.assertFalse(handle.worker.is_alive())
        self.assertTrue(handle.worker_done)
        self.assertFalse(handle.csv_enabled)
        self.assertIsNone(handle.csv_path)
        self.assertGreater(version_after, version_before)
        self.assertEqual("stopped", status["state"])
        self.assertFalse(status["active"])
        self.assertEqual(1, status["captured"])
        self.assertEqual(0, status["errors"])
        self.assertFalse(status["csv_enabled"])
        self.assertIsNone(status["csv_path"])
        self.assertIsNone(status["fatal_error"])
        self.assertEqual(1, len(status["recent_samples"]))
        self.assertEqual(status["recent_samples"][-1], status["latest_sample"])
        self.assertFalse(csv_path.exists())
        self.assertFalse(csv_path.parent.exists())

        open_response = client.post("/api/runs/current/open-csv")
        self.assertEqual(409, open_response.status_code)
        self.assertEqual("no completed CSV available", open_response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
