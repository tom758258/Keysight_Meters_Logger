from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout

from meters_tool_cli._constants import CLI_EVENT_SCHEMA_VERSION
from meters_tool_cli.cli import main

from cli_command_helpers import CliCommandHarnessMixin


class CliClientContractsTests(CliCommandHarnessMixin, unittest.TestCase):
    def test_machine_schema_constant_is_v2(self):
        self.assertEqual(2, CLI_EVENT_SCHEMA_VERSION)

    def test_invalid_port_json_validation_contract(self):
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = main(["status", "--port", "0", "--json"])

        self.assertEqual(2, rc)
        event = json.loads(stdout.getvalue())
        self._assert_error_contract(
            event,
            client_command="status",
            error_phase="validation",
            exit_code=2,
            port=0,
        )

    def test_invalid_timeout_json_validation_contract(self):
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            rc = main(["wait-ready", "--timeout-ms", "99", "--json"])

        self.assertEqual(2, rc)
        event = json.loads(stdout.getvalue())
        self._assert_error_contract(
            event,
            client_command="wait-ready",
            error_phase="validation",
            exit_code=2,
        )


if __name__ == "__main__":
    unittest.main()
