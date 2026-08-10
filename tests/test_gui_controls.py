"""Focused headless acceptance tests for P3-WP05 controls and inspection."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from biomesh.gui.run_controls import EXACT_P2_FIXTURE_RUNS, EXACT_P2_SEEDS
from biomesh.p2_campaign import FIXTURE_SEEDS, PUBLISHED_FIXTURES


def test_gui_catalog_is_exactly_the_existing_p2_run_surface() -> None:
    """The GUI neither omits nor invents fixture, condition, or seed inputs."""
    actual = {
        (fixture_name, condition_id)
        for _title, fixture_name, condition_id in EXACT_P2_FIXTURE_RUNS
    }
    expected = {
        (fixture_name, condition_id)
        for fixture_name, (_kind, condition_ids) in PUBLISHED_FIXTURES.items()
        for condition_id in condition_ids
    }
    assert actual == expected
    assert len(actual) == len(EXACT_P2_FIXTURE_RUNS)
    assert EXACT_P2_SEEDS == FIXTURE_SEEDS


def test_controls_checkpoints_cancellation_and_inspection_headlessly(
    tmp_path: Path,
) -> None:
    """Exercise worker ordering and real widgets on Qt's offscreen backend."""
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    result = subprocess.run(
        [sys.executable, "tests/gui_controls_probe.py", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode == 0, result.stderr
