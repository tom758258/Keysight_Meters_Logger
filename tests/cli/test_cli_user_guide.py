from __future__ import annotations

import io
from contextlib import redirect_stderr
from unittest.mock import Mock

import pytest

from meters_tool_cli.cli import _resolve_user_guide_path, main


@pytest.mark.parametrize(
    ("argv", "filename"),
    [
        (["user-guide"], "cli.html"),
        (["user-guide", "--lang", "zh-TW"], "cli.zh-TW.html"),
    ],
)
def test_user_guide_opens_expected_local_file(monkeypatch, argv, filename) -> None:
    expected_path = _resolve_user_guide_path("zh-TW" if "zh-TW" in argv else "en")
    assert expected_path.name == filename
    assert expected_path.is_file()

    opener = Mock(return_value=True)
    monkeypatch.setattr("meters_tool_cli.cli.webbrowser.open_new_tab", opener)

    stderr = io.StringIO()
    with redirect_stderr(stderr):
        rc = main(argv)

    assert rc == 0
    opener.assert_called_once()
    assert opener.call_args.args[0] == expected_path.as_uri()


def test_user_guide_browser_failure_returns_non_zero(monkeypatch) -> None:
    expected_path = _resolve_user_guide_path("en")
    assert expected_path.is_file()

    opener = Mock(return_value=False)
    monkeypatch.setattr("meters_tool_cli.cli.webbrowser.open_new_tab", opener)

    stderr = io.StringIO()
    with redirect_stderr(stderr):
        rc = main(["user-guide"])

    assert rc == 1
    opener.assert_called_once_with(expected_path.as_uri())
    assert str(expected_path) in stderr.getvalue()



