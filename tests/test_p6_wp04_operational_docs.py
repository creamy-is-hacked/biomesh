"""P6-WP04 operational documentation, help, and version drift guards."""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

from biomesh import __version__
from biomesh.local_queue_types import QUEUE_SCHEMA_VERSION
from biomesh.portable_queue_import_types import PORTABLE_QUEUE_IMPORT_SCHEMA_VERSION
from biomesh.portable_queue_intent_types import PORTABLE_QUEUE_INTENT_SCHEMA_VERSION

ROOT = Path(__file__).parents[1]
OPERATIONS = ROOT / "docs" / "P6_WP04_OPERATIONAL_MIGRATION.md"


def _help(*arguments: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "biomesh", *arguments, "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stderr == ""
    return result.stdout


def test_migration_matrix_tracks_runtime_and_supported_schema_versions() -> None:
    document = OPERATIONS.read_text(encoding="utf-8")
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert __version__ == metadata["project"]["version"] == "0.6.0"
    assert QUEUE_SCHEMA_VERSION == 1
    assert PORTABLE_QUEUE_INTENT_SCHEMA_VERSION == 1
    assert PORTABLE_QUEUE_IMPORT_SCHEMA_VERSION == 1
    for exact_claim in (
        "P4 local queue | queue schema 1",
        "`biomesh-portable-queue-intent`, schema 1, BioMesh 0.6.0",
        "`biomesh-portable-queue-import`, schema 1",
        "`biomesh-portable-queue-local-binding`, schema 1",
        "`biomesh-portable-queue-activation`, schema 1",
        "archive/project schema 2",
        "Historical P4 archive/project | schema 1",
        "envelope schema 1",
    ):
        assert exact_claim in document


def test_operator_commands_and_help_expose_status_and_read_only_dry_run() -> None:
    document = OPERATIONS.read_text(encoding="utf-8")
    queue_help = _help("queue")
    assert "migration-status" in queue_help
    assert "read-only verify a portable record or activated queue" in queue_help
    for command in (
        "export-intent",
        "import-intent",
        "bind-intent",
        "activate-intent",
    ):
        command_help = _help("queue", command)
        assert "--dry-run" in command_help
        assert f"queue {command}" in document
    for command in (
        "queue status",
        "queue run",
        "queue cancel",
        "queue retry",
        "campaign status",
        "campaign report",
        "project verify-archive",
        "project verify-secure-archive",
    ):
        assert command in document


def test_operator_contract_keeps_required_failures_and_boundaries_explicit() -> None:
    document = OPERATIONS.read_text(encoding="utf-8")
    for heading in (
        "## Supported migration matrix",
        "## Clean destination import, bind, and activate",
        "## Execute, cancel, retry, and recover",
        "## Report trace comparison",
        "## Explicit failure examples",
        "## Atomicity, artifact separation, and limitations",
    ):
        assert heading in document
    for required_failure in (
        "Schema incompatibility",
        "Changed inputs",
        "Path/resource conflict",
        "Incomplete binding",
        "Duplicate activation",
        "Trust/authorization non-transfer",
        "Calibration non-promotion",
        "Unsupported downgrade/migration",
    ):
        assert required_failure in document
    for boundary in (
        "`NOT_GRANTED`",
        "`CALIBRATION_REQUIRED`",
        "no remote/cloud scheduler",
        "credential transfer",
        "automatic transfer/path guessing",
        "P6A is a separate independent audit",
    ):
        assert boundary in document
