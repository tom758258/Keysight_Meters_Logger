from __future__ import annotations

import tempfile
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
    from meters_tool_webui.web_ui import WebRunManager


from webui_test_helpers import (
    cleanup_tempdir,
    make_api_client,
    make_api_client_with_manager,
    wait_until_inactive,
)


@unittest.skipIf(TestClient is None, "FastAPI test dependencies are not installed")
class WebUiRunResolutionApiTests(unittest.TestCase):
    def tearDown(self):
        cleanup_tempdir(self)
    def test_simulate_uses_no_real_visa_and_publishes_sample_status(self):
        client, csv_path = make_api_client(self)

        with (
            patch(
                "meters_tool_core.instrument.pyvisa.ResourceManager",
                side_effect=AssertionError("simulate must not create a VISA resource manager"),
            ) as resource_manager,
            patch(
                "meters_tool_core.start_resolution.VisaInstrument.preflight_idn",
                side_effect=AssertionError("simulate must not query live IDN"),
            ) as preflight,
        ):
            response = client.post(
                "/api/runs",
                json={
                    "resource": "SIM::34460A",
                    "instrument_model": "34460A",
                    "simulate": True,
                    "csv": str(csv_path),
                    "trigger_mode": "immediate",
                    "max_samples": 1,
                },
            )
            status = wait_until_inactive(client)

        self.assertEqual(200, response.status_code)
        resource_manager.assert_not_called()
        preflight.assert_not_called()
        self.assertFalse(status["active"])
        self.assertEqual(1, status["captured"])
        self.assertEqual(1, len(status["recent_samples"]))
        self.assertEqual(status["latest_sample"], status["recent_samples"][-1])
        self.assertEqual("SIM::34460A", status["latest_sample"]["resource_id"])

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


if __name__ == "__main__":
    unittest.main()
