from __future__ import annotations

import ctypes
import signal
import sys

from meters_tool_core import StartRunEvent, StopController


class WindowsConsoleStopHandler:
    _CTRL_C_EVENT = 0
    _CTRL_BREAK_EVENT = 1
    _STD_INPUT_HANDLE = -10
    _ENABLE_PROCESSED_INPUT = 0x0001

    def __init__(self, stop_controller: StopController):
        self._stop_controller = stop_controller
        self._kernel32 = None
        self._handler = None
        self._stdin_handle = None
        self._previous_input_mode = None
        self.installed = False
        self.input_mode_configured = False

    def install(self) -> bool:
        if sys.platform != "win32":
            return False
        try:
            from ctypes import wintypes

            self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)
            self._kernel32.SetConsoleCtrlHandler.argtypes = (callback_type, wintypes.BOOL)
            self._kernel32.SetConsoleCtrlHandler.restype = wintypes.BOOL
            self._kernel32.GetStdHandle.argtypes = (wintypes.DWORD,)
            self._kernel32.GetStdHandle.restype = wintypes.HANDLE
            self._kernel32.GetConsoleMode.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
            self._kernel32.GetConsoleMode.restype = wintypes.BOOL
            self._kernel32.SetConsoleMode.argtypes = (wintypes.HANDLE, wintypes.DWORD)
            self._kernel32.SetConsoleMode.restype = wintypes.BOOL
            self._configure_input_mode(wintypes)
            self._handler = callback_type(self._handle)
            if not self._kernel32.SetConsoleCtrlHandler(self._handler, True):
                return False
        except (AttributeError, OSError):
            return False
        self.installed = True
        return True

    def uninstall(self) -> None:
        if not self.installed or self._kernel32 is None or self._handler is None:
            return
        self._restore_input_mode()
        self._kernel32.SetConsoleCtrlHandler(self._handler, False)
        self.installed = False

    def _handle(self, ctrl_type: int) -> bool:
        if ctrl_type not in (self._CTRL_C_EVENT, self._CTRL_BREAK_EVENT):
            return False
        self._stop_controller.request_signal_stop()
        return True

    def _configure_input_mode(self, wintypes) -> None:  # noqa: ANN001
        if self._kernel32 is None:
            return
        handle = self._kernel32.GetStdHandle(self._STD_INPUT_HANDLE)
        if not handle:
            return
        mode = wintypes.DWORD()
        if not self._kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return
        self._stdin_handle = handle
        self._previous_input_mode = int(mode.value)
        desired_mode = int(mode.value) | self._ENABLE_PROCESSED_INPUT
        if self._kernel32.SetConsoleMode(handle, desired_mode):
            self.input_mode_configured = True

    def _restore_input_mode(self) -> None:
        if (
            self._kernel32 is None
            or self._stdin_handle is None
            or self._previous_input_mode is None
            or not self.input_mode_configured
        ):
            return
        self._kernel32.SetConsoleMode(self._stdin_handle, self._previous_input_mode)
        self.input_mode_configured = False


class WindowsKeyboardStopPoller:
    def __init__(self):
        self._msvcrt = None
        if sys.platform == "win32":
            try:
                import msvcrt

                self._msvcrt = msvcrt
            except ImportError:
                self._msvcrt = None

    def poll_stop_requested(self) -> bool:
        if self._msvcrt is None:
            return False
        requested = False
        while self._msvcrt.kbhit():
            ch = self._msvcrt.getwch()
            if ch in ("\x00", "\xe0"):
                if self._msvcrt.kbhit():
                    self._msvcrt.getwch()
                continue
            if ch in ("\x03", "q", "Q"):
                requested = True
        return requested


class CliStartRunControls:
    def __init__(
        self,
        console_handler_factory=WindowsConsoleStopHandler,  # noqa: ANN001
        keyboard_poller_factory=WindowsKeyboardStopPoller,  # noqa: ANN001
    ) -> None:
        self._console_handler_factory = console_handler_factory
        self._keyboard_poller_factory = keyboard_poller_factory
        self._stop_controller: StopController | None = None
        self._previous_signal_handlers = []
        self._windows_console_stop_handler = None
        self._keyboard_stop_poller = None

    def install(self, stop_controller: StopController) -> None:
        self._stop_controller = stop_controller

        def handle_stop_signal(signum, frame):  # noqa: ARG001
            stop_controller.request_signal_stop()

        self._previous_signal_handlers.append(
            (signal.SIGINT, signal.signal(signal.SIGINT, handle_stop_signal))
        )
        if hasattr(signal, "SIGTERM"):
            self._previous_signal_handlers.append(
                (signal.SIGTERM, signal.signal(signal.SIGTERM, handle_stop_signal))
            )
        if hasattr(signal, "SIGBREAK"):
            self._previous_signal_handlers.append(
                (signal.SIGBREAK, signal.signal(signal.SIGBREAK, handle_stop_signal))
            )
        self._windows_console_stop_handler = self._console_handler_factory(stop_controller)
        self._keyboard_stop_poller = self._keyboard_poller_factory()

    def after_connect(self, event_sink, run_id: str) -> None:  # noqa: ANN001
        if self._windows_console_stop_handler is None:
            return
        if self._windows_console_stop_handler.install():
            event_sink.emit(
                StartRunEvent.message_event(
                    run_id,
                    "windows console stop handler: installed "
                    f"processed_input={self._windows_console_stop_handler.input_mode_configured}",
                )
            )
        elif sys.platform == "win32":
            event_sink.emit(
                StartRunEvent.error_event(run_id, "windows console stop handler: unavailable")
            )

    def poll_stop_requested(self) -> bool:
        if self._keyboard_stop_poller is None:
            return False
        return bool(self._keyboard_stop_poller.poll_stop_requested())

    def uninstall(self) -> None:
        if self._windows_console_stop_handler is not None:
            self._windows_console_stop_handler.uninstall()
        for sig, previous_handler in self._previous_signal_handlers:
            signal.signal(sig, previous_handler)
        self._previous_signal_handlers = []
