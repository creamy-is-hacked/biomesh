"""Strict, UI-only desktop preference persistence.

This store is deliberately independent of the biological parameter and
experiment schemas. It contains only window layout and recent-path state.
"""

from __future__ import annotations

import base64
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PREFERENCES_SCHEMA_VERSION = 1
MAX_RECENT_PROJECTS = 10


class UiPreferencesError(ValueError):
    """Raised when UI preferences cannot be read, validated, or written."""


@dataclass(frozen=True, slots=True)
class UiPreferences:
    """Persisted desktop state that cannot influence simulation science."""

    recent_projects: tuple[str, ...] = ()
    window_geometry: str | None = None
    window_state: str | None = None

    def __post_init__(self) -> None:
        if len(self.recent_projects) > MAX_RECENT_PROJECTS:
            raise UiPreferencesError(
                f"recent_projects may contain at most {MAX_RECENT_PROJECTS} paths"
            )
        if len(set(self.recent_projects)) != len(self.recent_projects):
            raise UiPreferencesError("recent_projects must not contain duplicates")
        for project in self.recent_projects:
            if not project or not Path(project).is_absolute():
                raise UiPreferencesError(
                    "recent_projects entries must be nonblank absolute paths"
                )
        _validate_base64("window_geometry", self.window_geometry)
        _validate_base64("window_state", self.window_state)

    def with_recent_project(self, project_file: Path) -> UiPreferences:
        """Return preferences with one resolved project reference first."""
        project = str(project_file)
        recent = (project,) + tuple(
            item for item in self.recent_projects if item != project
        )
        return UiPreferences(
            recent_projects=recent[:MAX_RECENT_PROJECTS],
            window_geometry=self.window_geometry,
            window_state=self.window_state,
        )

    def with_window_state(self, *, geometry: str, state: str) -> UiPreferences:
        """Return preferences with updated Qt window-layout bytes."""
        return UiPreferences(
            recent_projects=self.recent_projects,
            window_geometry=geometry,
            window_state=state,
        )


class UiPreferencesStore:
    """Read and atomically write one versioned UI-preferences JSON file."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path if path is not None else default_preferences_path()

    def load(self) -> UiPreferences:
        """Load strict preferences; a missing file means first-run defaults."""
        if not self.path.exists():
            return UiPreferences()
        if not self.path.is_file():
            raise UiPreferencesError(
                f"UI preferences path is not a file: {self.path}"
            )
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise UiPreferencesError(
                f"unable to read UI preferences {self.path}: {error}"
            ) from error
        return _preferences_from_payload(payload)

    def save(self, preferences: UiPreferences) -> None:
        """Atomically save validated preferences outside scientific inputs."""
        if not isinstance(preferences, UiPreferences):
            raise UiPreferencesError("preferences must be a UiPreferences record")
        payload = {
            "recent_projects": list(preferences.recent_projects),
            "schema_version": PREFERENCES_SCHEMA_VERSION,
            "window_geometry": preferences.window_geometry,
            "window_state": preferences.window_state,
        }
        contents = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        temporary_path: Path | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                delete=False,
            ) as temporary:
                temporary.write(contents)
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_path = Path(temporary.name)
            os.replace(temporary_path, self.path)
        except OSError as error:
            raise UiPreferencesError(
                f"unable to write UI preferences {self.path}: {error}"
            ) from error
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()


def default_preferences_path() -> Path:
    """Return the XDG-compliant UI preference path."""
    config_home = os.environ.get("XDG_CONFIG_HOME")
    root = Path(config_home) if config_home else Path.home() / ".config"
    return root / "biomesh" / "ui-preferences.json"


def _preferences_from_payload(payload: Any) -> UiPreferences:
    if not isinstance(payload, dict):
        raise UiPreferencesError("UI preferences root must be a JSON object")
    expected_keys = {
        "recent_projects",
        "schema_version",
        "window_geometry",
        "window_state",
    }
    if set(payload) != expected_keys:
        raise UiPreferencesError(
            "UI preferences must contain exactly: "
            + ", ".join(sorted(expected_keys))
        )
    if payload["schema_version"] != PREFERENCES_SCHEMA_VERSION:
        raise UiPreferencesError(
            "unsupported UI preferences schema_version: "
            f"{payload['schema_version']!r}"
        )
    recent = payload["recent_projects"]
    if not isinstance(recent, list) or not all(
        isinstance(item, str) for item in recent
    ):
        raise UiPreferencesError("recent_projects must be a JSON string array")
    geometry = _optional_string(payload, "window_geometry")
    state = _optional_string(payload, "window_state")
    return UiPreferences(tuple(recent), geometry, state)


def _optional_string(payload: dict[str, Any], key: str) -> str | None:
    value = payload[key]
    if value is not None and not isinstance(value, str):
        raise UiPreferencesError(f"{key} must be a string or null")
    return value


def _validate_base64(name: str, value: str | None) -> None:
    if value is None:
        return
    if not value:
        raise UiPreferencesError(f"{name} must be nonblank when present")
    try:
        base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as error:
        raise UiPreferencesError(f"{name} must contain valid base64") from error
