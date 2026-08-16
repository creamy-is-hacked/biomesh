"""Read-only P6-WP04 verification and lifecycle status for migration records."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from biomesh import __version__
from biomesh.local_queue_storage import LocalQueueStore
from biomesh.portable_queue_activation import (
    _load_binding,
    load_portable_queue_activation,
    validate_portable_queue_state,
)
from biomesh.portable_queue_activation_types import portable_queue_activation_bytes
from biomesh.portable_queue_import import (
    _load_import_record,
    _load_manifest,
    _safe_input_file,
)
from biomesh.portable_queue_intent import (
    _read_stable_regular_file,
    _safe_directory,
)

MigrationRecordType = Literal[
    "PORTABLE_INTENT",
    "UNBOUND_IMPORT",
    "BOUND_NONRUNNABLE",
    "ACTIVATED_LOCAL_QUEUE",
]


@dataclass(frozen=True, slots=True)
class PortableMigrationStatus:
    """Canonical identity and lifecycle status of one P6 migration record."""

    record_type: MigrationRecordType
    schema_version: int
    biomesh_version: str
    record_sha256: str
    item_count: int
    project_count: int

    def as_dict(self) -> dict[str, int | str]:
        return {
            "biomesh_version": self.biomesh_version,
            "item_count": self.item_count,
            "project_count": self.project_count,
            "record_sha256": self.record_sha256,
            "record_type": self.record_type,
            "schema_version": self.schema_version,
        }


def portable_migration_status(path: Path) -> PortableMigrationStatus:
    """Canonical-verify one portable record or activated queue without mutation."""
    if path.is_dir() and not path.is_symlink():
        return _activated_queue_status(path)
    source = _safe_input_file(path, label="portable migration record")
    contents = _read_stable_regular_file(source, label="portable migration record")
    try:
        payload = json.loads(contents)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(
            f"portable migration record is not valid JSON: {error}"
        ) from error
    if not isinstance(payload, dict):
        raise ValueError("portable migration record must be a JSON object")
    formats = {
        "manifest_format": "biomesh-portable-queue-intent",
        "import_format": "biomesh-portable-queue-import",
        "binding_format": "biomesh-portable-queue-local-binding",
    }
    matched = [key for key, value in formats.items() if payload.get(key) == value]
    if len(matched) != 1:
        raise ValueError("portable migration record format is unsupported or ambiguous")
    record_sha256 = hashlib.sha256(contents).hexdigest()
    if matched[0] == "manifest_format":
        _, manifest = _load_manifest(source)
        project_count = len({item.project_id for item in manifest.items})
        return PortableMigrationStatus(
            record_type="PORTABLE_INTENT",
            schema_version=manifest.schema_version,
            biomesh_version=manifest.biomesh_version,
            record_sha256=record_sha256,
            item_count=len(manifest.items),
            project_count=project_count,
        )
    if matched[0] == "import_format":
        _, import_record = _load_import_record(source)
        project_count = len(
            {item.intent.project_id for item in import_record.items}
        )
        return PortableMigrationStatus(
            record_type="UNBOUND_IMPORT",
            schema_version=import_record.schema_version,
            biomesh_version=import_record.source_manifest.biomesh_version,
            record_sha256=record_sha256,
            item_count=len(import_record.items),
            project_count=project_count,
        )
    _, binding = _load_binding(source)
    return PortableMigrationStatus(
        record_type="BOUND_NONRUNNABLE",
        schema_version=binding.schema_version,
        biomesh_version=binding.source_manifest.biomesh_version,
        record_sha256=record_sha256,
        item_count=len(binding.items),
        project_count=len(binding.projects),
    )


def _activated_queue_status(path: Path) -> PortableMigrationStatus:
    root = _safe_directory(path, label="activated portable queue")
    store = LocalQueueStore(root)
    with store.lock():
        state = store.load()
        activation = load_portable_queue_activation(root)
        if activation is None:
            raise ValueError("directory is not an activated portable queue")
        if activation.source_binding.source_manifest.biomesh_version != __version__:
            raise ValueError(
                "portable queue activation BioMesh version is incompatible with "
                "this runtime"
            )
        validate_portable_queue_state(state, activation)
    contents = portable_queue_activation_bytes(activation)
    return PortableMigrationStatus(
        record_type="ACTIVATED_LOCAL_QUEUE",
        schema_version=activation.schema_version,
        biomesh_version=activation.source_binding.source_manifest.biomesh_version,
        record_sha256=hashlib.sha256(contents).hexdigest(),
        item_count=len(activation.items),
        project_count=len(activation.source_binding.projects),
    )
