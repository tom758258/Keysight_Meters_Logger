from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from meters_tool_cli.cli import main


class CliCapabilitiesCommandTests(unittest.TestCase):
    def run_json(self, *args: str) -> tuple[int, dict[str, object], str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            rc = main(["capabilities", *args, "--json"])
        lines = stdout.getvalue().splitlines()
        self.assertEqual(1, len(lines))
        return rc, json.loads(lines[0]), stderr.getvalue()

    @patch("meters_tool_cli.cli.run_start_session")
    @patch("meters_tool_cli.cli.VisaInstrument")
    def test_default_json_uses_fallback_profile_without_runtime_io(
        self,
        mock_visa,
        mock_run_start_session,
    ):
        rc, payload, stderr = self.run_json()

        self.assertEqual(0, rc)
        self.assertEqual("", stderr)
        self.assertEqual("capabilities", payload["event"])
        self.assertEqual(2, payload["schema_version"])
        self.assertEqual(
            {"requested_model": None, "source": "default_fallback"},
            payload["selection"],
        )
        self.assertEqual(
            {
                "detection_performed": False,
                "model": None,
                "model_id": None,
                "vendor": None,
            },
            payload["runtime_identity"],
        )
        profile = payload["capability_profile"]
        self.assertEqual("keysight-34461a", profile["model_id"])
        self.assertGreater(profile["reading_memory_limit"], 0)
        self.assertTrue(payload["available_profiles"])
        self.assertIn("current-dc", {item["measurement_name"] for item in payload["measurements"]})
        self.assertIn("software", payload["trigger_modes"])
        mock_visa.assert_not_called()
        mock_run_start_session.assert_not_called()

    def test_known_model_returns_canonical_profile(self):
        rc, payload, stderr = self.run_json("--model", "34461A")

        self.assertEqual(0, rc)
        self.assertEqual("", stderr)
        self.assertEqual(
            {"requested_model": "34461A", "source": "requested_model"},
            payload["selection"],
        )
        self.assertEqual("34461A", payload["capability_profile"]["model"])
        self.assertEqual("keysight-34461a", payload["capability_profile"]["model_id"])

    def test_34460a_serializes_validated_and_pending_live_scopes(self):
        rc, payload, stderr = self.run_json("--model", "34460A")

        self.assertEqual(0, rc)
        self.assertEqual("", stderr)
        self.assertEqual("keysight-34460a", payload["capability_profile"]["model_id"])
        live = payload["support"]["start-trigger-record"]["live"]
        scopes = {
            (scope["transport_scope"], scope["backend_scope"]): scope
            for scope in live["scopes"]
        }
        self.assertEqual(
            "live_validated_full_suite",
            scopes[("usb", "system_visa")]["validation_status"],
        )
        pending = scopes[("tcpip", "system_visa")]
        self.assertEqual("transport_pending", pending["validation_status"])
        self.assertIn(
            {
                "feature_kind": "measurement",
                "feature_value": "current_dc",
                "validation_status": "feature_pending",
            },
            pending["features"],
        )

    @patch("meters_tool_cli.cli.run_start_session")
    @patch("meters_tool_cli.cli.VisaInstrument")
    def test_invalid_model_uses_structured_validation_error_without_runtime_io(
        self,
        mock_visa,
        mock_run_start_session,
    ):
        rc, payload, stderr = self.run_json("--model", "BADMODEL")

        self.assertEqual(2, rc)
        self.assertEqual("", stderr)
        self.assertEqual("error", payload["event"])
        self.assertEqual(2, payload["schema_version"])
        self.assertEqual(2, payload["exit_code"])
        self.assertEqual("capabilities", payload["command"])
        self.assertIn("Unsupported instrument model", payload["message"])
        mock_visa.assert_not_called()
        mock_run_start_session.assert_not_called()


if __name__ == "__main__":
    unittest.main()
