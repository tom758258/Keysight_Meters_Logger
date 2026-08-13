from __future__ import annotations

import unittest
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover - dependency-gated tests
    TestClient = None

if TestClient is not None:
    from meters_tool_webui.web_ui import WebRunManager


from webui_test_helpers import (
    cleanup_tempdir,
    make_api_client,
    make_api_client_with_manager,
    wait_until_inactive,
)


@unittest.skipIf(TestClient is None, "FastAPI test dependencies are not installed")
class WebUiRunPlanValidationTests(unittest.TestCase):
    def tearDown(self):
        cleanup_tempdir(self)
    def test_plan_returns_start_plan_without_visa_runtime_or_active_run(self):
        manager = WebRunManager()
        client = make_api_client_with_manager(manager)

        with (
            patch(
                "meters_tool_core.instrument.pyvisa.ResourceManager",
                side_effect=AssertionError("dry-run must not create a VISA resource manager"),
            ) as resource_manager,
            patch(
                "meters_tool_core.start_resolution.VisaInstrument.preflight_idn",
                side_effect=AssertionError("dry-run must not query live IDN"),
            ) as preflight,
            patch("meters_tool_webui._run_manager.run_start_session") as runner,
            patch("meters_tool_webui._run_manager.threading.Thread") as worker,
        ):
            response = client.post(
                "/api/plan",
                json={
                    "resource": "SIM::34461A",
                    "instrument_model": "34461A",
                    "simulate": True,
                    "trigger_mode": "immediate",
                    "measurement": "voltage-dc",
                    "max_samples": 1,
                },
            )
            missing_model_response = client.post(
                "/api/plan",
                json={"resource": "SIM::34461A", "trigger_mode": "immediate"},
            )

        self.assertEqual(200, response.status_code)
        self.assertEqual(422, missing_model_response.status_code)
        plan = response.json()
        self.assertTrue(plan["dry_run"])
        self.assertFalse(plan["simulate"])
        self.assertEqual("SIM::34461A", plan["resource"])
        self.assertEqual("voltage_dc", plan["measurement_type"])
        self.assertTrue(plan["scpi_commands"])
        self.assertEqual("READ?", plan["read_path"])
        self.assertTrue(plan["cleanup_steps"])
        self.assertIn("auto_range", plan["option_summary"])
        resource_manager.assert_not_called()
        preflight.assert_not_called()
        runner.assert_not_called()
        worker.assert_not_called()
        self.assertEqual("idle", manager.status()["state"])
        self.assertFalse(manager.status()["active"])

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


if __name__ == "__main__":
    unittest.main()
