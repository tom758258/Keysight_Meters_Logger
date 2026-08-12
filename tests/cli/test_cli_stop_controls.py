from __future__ import annotations

import unittest

from meters_tool_cli.cli import WindowsConsoleStopHandler, WindowsKeyboardStopPoller
from meters_tool_core.runner import StopController

from cli_command_helpers import FakeMsvcrt


class WindowsConsoleStopHandlerTests(unittest.TestCase):
    def test_ctrl_c_event_requests_stop(self):
        calls = []
        controller = StopController(lambda: calls.append("stop"))
        handler = WindowsConsoleStopHandler(controller)

        handled = handler._handle(0)

        self.assertTrue(handled)
        self.assertTrue(controller.stop)
        self.assertEqual(1, controller.interrupt_count)
        self.assertEqual(["stop"], calls)

    def test_ctrl_break_event_requests_stop(self):
        calls = []
        controller = StopController(lambda: calls.append("stop"))
        handler = WindowsConsoleStopHandler(controller)

        handled = handler._handle(1)

        self.assertTrue(handled)
        self.assertTrue(controller.stop)
        self.assertEqual(1, controller.interrupt_count)
        self.assertEqual(["stop"], calls)

    def test_non_interrupt_event_is_not_handled(self):
        calls = []
        controller = StopController(lambda: calls.append("stop"))
        handler = WindowsConsoleStopHandler(controller)

        handled = handler._handle(2)

        self.assertFalse(handled)
        self.assertFalse(controller.stop)
        self.assertEqual(0, controller.interrupt_count)
        self.assertEqual([], calls)



class WindowsKeyboardStopPollerTests(unittest.TestCase):
    def test_ctrl_c_character_requests_stop(self):
        poller = WindowsKeyboardStopPoller()
        poller._msvcrt = FakeMsvcrt(["\x03"])

        self.assertTrue(poller.poll_stop_requested())

    def test_q_requests_stop(self):
        poller = WindowsKeyboardStopPoller()
        poller._msvcrt = FakeMsvcrt(["q"])

        self.assertTrue(poller.poll_stop_requested())

    def test_other_key_does_not_request_stop(self):
        poller = WindowsKeyboardStopPoller()
        poller._msvcrt = FakeMsvcrt(["x"])

        self.assertFalse(poller.poll_stop_requested())




if __name__ == "__main__":
    unittest.main()
