"""Focused headless tests for the P3-WP02 desktop shell."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from biomesh.gui.preferences import (
    UiPreferences,
    UiPreferencesError,
    UiPreferencesStore,
)


def test_preferences_round_trip_ui_only_state(tmp_path: Path) -> None:
    """UI preferences round-trip in their own strict versioned file."""
    preferences_file = tmp_path / "config" / "ui-preferences.json"
    project_file = (tmp_path / "project.toml").resolve()
    project_file.write_text("title = 'opaque UI reference'\n", encoding="utf-8")
    preferences = UiPreferences(
        recent_projects=(str(project_file),),
        window_geometry="YWJj",
        window_state="ZGVm",
    )
    store = UiPreferencesStore(preferences_file)

    store.save(preferences)

    assert store.load() == preferences
    payload = json.loads(preferences_file.read_text(encoding="utf-8"))
    assert set(payload) == {
        "recent_projects",
        "schema_version",
        "window_geometry",
        "window_state",
    }


@pytest.mark.parametrize(
    "contents, message",
    [
        ("not JSON\n", "unable to read UI preferences"),
        ('{"schema_version": 99}\n', "must contain exactly"),
        (
            json.dumps(
                {
                    "recent_projects": [],
                    "schema_version": 1,
                    "window_geometry": "not base64",
                    "window_state": None,
                }
            ),
            "valid base64",
        ),
    ],
)
def test_invalid_preferences_fail_clearly(
    tmp_path: Path, contents: str, message: str
) -> None:
    """Malformed UI state raises an explicit validation error."""
    preferences_file = tmp_path / "ui-preferences.json"
    preferences_file.write_text(contents, encoding="utf-8")

    with pytest.raises(UiPreferencesError, match=message):
        UiPreferencesStore(preferences_file).load()


def test_shell_chrome_errors_and_science_isolation(tmp_path: Path) -> None:
    """Exercise real widgets offscreen without loading Qt into this process."""
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    result = subprocess.run(
        [sys.executable, "tests/gui_shell_probe.py", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode == 0, result.stderr


def test_gui_module_starts_headlessly(tmp_path: Path) -> None:
    """The executable shell constructs and closes on the offscreen backend."""
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "biomesh.gui",
            "--smoke-test",
            "--preferences-file",
            str(tmp_path / "preferences.json"),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "preferences.json").is_file()
