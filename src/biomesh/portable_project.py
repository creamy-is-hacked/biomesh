"""P4-WP06 deterministic, checksum-verified portable project exchange."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import ValidationError

from biomesh import __version__
from biomesh.portable_project_types import (
    PortableArchiveError,
    PortableArchiveResult,
    PortableFileRecord,
    PortableImportResult,
    PortableProjectManifest,
)
from biomesh.project_campaign import (
    COMPLETION_RECEIPT,
    PROJECT_MANIFEST,
    PROJECT_SCHEMA_VERSION,
    PROJECT_STATE,
    ArtifactRecord,
    CampaignRunStatus,
    CampaignService,
    ProjectDefinition,
    ProjectState,
    RunRecord,
)
from biomesh.runtime_resources import runtime_root

ARCHIVE_MANIFEST = "archive.json"
MAX_ARCHIVE_FILES = 100_000
MAX_ARCHIVE_BYTES = 64 * 1024**3
_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def export_project_archive(
    project_directory: Path, output: Path
) -> PortableArchiveResult:
    """Atomically export one stable project snapshot to a deterministic ZIP."""
    _require_new_output(output, label="portable archive")
    service = CampaignService(project_directory)
    temporary_path: Path | None = None
    with service.verified_snapshot() as (definition, state):
        if any(run.status is CampaignRunStatus.RUNNING for run in state.runs):
            raise PortableArchiveError("cannot export a project with running work")
        payload, manifest = _portable_payload(
            service.project_directory, definition, state
        )
        descriptor, name = tempfile.mkstemp(
            prefix=f".{output.name}.", dir=output.parent
        )
        os.close(descriptor)
        temporary_path = Path(name)
        try:
            with zipfile.ZipFile(
                temporary_path,
                mode="w",
                compression=zipfile.ZIP_STORED,
                allowZip64=True,
            ) as archive:
                _write_member(archive, ARCHIVE_MANIFEST, _manifest_bytes(manifest))
                for path in sorted(payload):
                    _write_member(archive, path, payload[path])
            _verify_archive_payload(temporary_path)
            os.replace(temporary_path, output)
            temporary_path = None
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
    return _result(output, manifest)


def verify_project_archive(path: Path) -> PortableArchiveResult:
    """Verify structure, strict manifests, file sizes, and every SHA-256."""
    manifest, _payload = _verify_archive_payload(path)
    return _result(path, manifest)


def import_project_archive(path: Path, project_directory: Path) -> PortableImportResult:
    """Verify and atomically import a portable project without granting trust."""
    _require_new_output(project_directory, label="project directory")
    manifest, payload = _verify_archive_payload(path)
    temporary = Path(
        tempfile.mkdtemp(
            prefix=f".{project_directory.name}.", dir=project_directory.parent
        )
    )
    try:
        (temporary / "artifacts").mkdir()
        for archive_path, contents in sorted(payload.items()):
            relative = PurePosixPath(archive_path).relative_to("project")
            target = temporary.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            _write_bytes(target, contents)
        (temporary / ".campaign.lock").touch()
        imported_definition, imported_state = CampaignService(
            temporary
        ).verified_records()
        if imported_definition.project.project_id != manifest.project_id:
            raise PortableArchiveError("imported project identity mismatch")
        if _sha256((temporary / PROJECT_MANIFEST).read_bytes()) != (
            manifest.portable_definition_sha256
        ):
            raise PortableArchiveError("imported project manifest identity mismatch")
        if _sha256((temporary / PROJECT_STATE).read_bytes()) != manifest.state_sha256:
            raise PortableArchiveError("imported project state identity mismatch")
        os.replace(temporary, project_directory)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return PortableImportResult(
        project_directory=str(project_directory),
        project_id=manifest.project_id,
        completed_run_count=_completed_count(imported_state),
        file_count=len(manifest.files),
    )


def _portable_payload(
    project_directory: Path,
    definition: ProjectDefinition,
    state: ProjectState,
) -> tuple[dict[str, bytes], PortableProjectManifest]:
    source_manifest = (project_directory / PROJECT_MANIFEST).read_bytes()
    source_hash = _sha256(source_manifest)
    if state.definition_sha256 != source_hash:
        raise PortableArchiveError("project state is not bound to its source manifest")

    fixtures: dict[str, bytes] = {}
    portable_experiments = []
    for experiment in definition.experiments:
        source = _resolve_project_fixture(project_directory, experiment.fixture_file)
        contents = source.read_bytes()
        if _sha256(contents) != experiment.fixture_sha256:
            raise PortableArchiveError(
                f"experiment fixture changed: {experiment.experiment_id}"
            )
        suffix = source.suffix.lower() if source.suffix else ".fixture"
        portable_label = (
            f"fixtures/{experiment.experiment_id}-{experiment.fixture_sha256[:12]}"
            f"{suffix}"
        )
        fixtures[f"project/{portable_label}"] = contents
        portable_experiments.append(
            experiment.model_copy(update={"fixture_file": portable_label})
        )

    portable_definition = definition.model_copy(
        update={"experiments": portable_experiments}
    )
    portable_manifest_bytes = _model_bytes(portable_definition)
    portable_hash = _sha256(portable_manifest_bytes)
    portable_state = state.model_copy(
        update={"definition_sha256": portable_hash}
    )
    state_bytes = _model_bytes(portable_state)

    payload: dict[str, bytes] = {
        "project/project.json": portable_manifest_bytes,
        "project/campaign_state.json": state_bytes,
        **fixtures,
    }
    roles: dict[
        str,
        Literal["configuration", "manifest", "fixture", "compact_result"],
    ] = {
        "project/project.json": "configuration",
        "project/campaign_state.json": "manifest",
        **{path: "fixture" for path in fixtures},
    }
    expected_run_directories: set[str] = set()
    for run in state.runs:
        if run.status is not CampaignRunStatus.COMPLETED:
            continue
        run_root = project_directory / "artifacts" / run.run_id
        expected_run_directories.add(run.run_id)
        paths = [artifact.path for artifact in run.artifacts] + [COMPLETION_RECEIPT]
        for relative in paths:
            source = run_root.joinpath(*PurePosixPath(relative).parts)
            if not source.is_file() or source.is_symlink():
                raise PortableArchiveError(
                    f"completed run file is unavailable: {run.run_id}/{relative}"
                )
            archive_path = f"project/artifacts/{run.run_id}/{relative}"
            payload[archive_path] = source.read_bytes()
            roles[archive_path] = (
                "manifest" if relative == COMPLETION_RECEIPT else "compact_result"
            )
    _reject_unexpected_artifact_paths(project_directory, expected_run_directories)

    records = [
        PortableFileRecord(
            path=path,
            role=roles[path],
            sha256=_sha256(contents),
            size_bytes=len(contents),
        )
        for path, contents in sorted(payload.items())
    ]
    manifest = PortableProjectManifest(
        schema_version=1,
        archive_format="biomesh-portable-project",
        biomesh_version=__version__,
        project_id=definition.project.project_id,
        project_schema_version=1,
        source_definition_sha256=source_hash,
        portable_definition_sha256=portable_hash,
        state_sha256=_sha256(state_bytes),
        calibration_status="CALIBRATION_REQUIRED",
        result_policy="all_hash_verified_completed_run_artifacts",
        plugin_policy="no_plugins_embedded_or_trusted",
        registry_policy="no_registry_embedded_or_reidentified",
        queue_policy="queue_state_not_embedded_reenqueue_after_import",
        files=records,
    )
    return payload, manifest


def _verify_archive_payload(
    path: Path,
) -> tuple[PortableProjectManifest, dict[str, bytes]]:
    if not path.is_file() or path.is_symlink():
        raise PortableArchiveError(f"portable archive is unavailable: {path}")
    try:
        with zipfile.ZipFile(path, mode="r") as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ARCHIVE_FILES + 1:
                raise PortableArchiveError("portable archive contains too many files")
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                raise PortableArchiveError("portable archive contains duplicate paths")
            for info in infos:
                _validate_zip_member(info)
            if ARCHIVE_MANIFEST not in names:
                raise PortableArchiveError("portable archive omits archive.json")
            total_size = sum(info.file_size for info in infos)
            if total_size > MAX_ARCHIVE_BYTES:
                raise PortableArchiveError("portable archive exceeds the size limit")
            try:
                manifest = PortableProjectManifest.model_validate_json(
                    archive.read(ARCHIVE_MANIFEST)
                )
            except (KeyError, ValidationError) as error:
                raise PortableArchiveError(
                    f"invalid portable archive manifest: {error}"
                ) from error
            expected = {record.path: record for record in manifest.files}
            actual = set(names) - {ARCHIVE_MANIFEST}
            if actual != set(expected):
                missing = sorted(set(expected) - actual)
                extra = sorted(actual - set(expected))
                raise PortableArchiveError(
                    "portable archive inventory mismatch; "
                    f"missing={missing}, extra={extra}"
                )
            payload: dict[str, bytes] = {}
            for name in sorted(actual):
                contents = archive.read(name)
                record = expected[name]
                if len(contents) != record.size_bytes:
                    raise PortableArchiveError(f"portable file size mismatch: {name}")
                if _sha256(contents) != record.sha256:
                    raise PortableArchiveError(
                        f"portable file checksum mismatch: {name}"
                    )
                payload[name] = contents
    except (OSError, zipfile.BadZipFile, RuntimeError) as error:
        raise PortableArchiveError(
            f"invalid portable archive {path}: {error}"
        ) from error
    _validate_embedded_project(manifest, payload)
    return manifest, payload


def _validate_embedded_project(
    manifest: PortableProjectManifest, payload: dict[str, bytes]
) -> None:
    try:
        definition = ProjectDefinition.model_validate_json(
            payload["project/project.json"]
        )
        state = ProjectState.model_validate_json(
            payload["project/campaign_state.json"]
        )
    except (KeyError, ValidationError) as error:
        raise PortableArchiveError(
            f"invalid embedded project records: {error}"
        ) from error
    definition_bytes = payload["project/project.json"]
    state_bytes = payload["project/campaign_state.json"]
    if definition.project.project_id != manifest.project_id:
        raise PortableArchiveError("archive project identity mismatch")
    if _sha256(definition_bytes) != manifest.portable_definition_sha256:
        raise PortableArchiveError("portable definition identity mismatch")
    if state.definition_sha256 != manifest.portable_definition_sha256:
        raise PortableArchiveError("portable state definition identity mismatch")
    if _sha256(state_bytes) != manifest.state_sha256:
        raise PortableArchiveError("portable state identity mismatch")

    expected_roles: dict[
        str,
        Literal["configuration", "manifest", "fixture", "compact_result"],
    ] = {
        "project/project.json": "configuration",
        "project/campaign_state.json": "manifest",
    }
    for experiment in definition.experiments:
        fixture_path = _contained_archive_path(
            f"project/{experiment.fixture_file}", label="portable fixture path"
        )
        contents = payload.get(fixture_path)
        if contents is None or _sha256(contents) != experiment.fixture_sha256:
            raise PortableArchiveError(
                f"portable fixture identity mismatch: {experiment.experiment_id}"
            )
        expected_roles[fixture_path] = "fixture"

    for run in state.runs:
        if run.status is not CampaignRunStatus.COMPLETED:
            continue
        run_root = f"project/artifacts/{run.run_id}"
        for artifact in run.artifacts:
            artifact_path = _contained_archive_path(
                f"{run_root}/{artifact.path}", label="portable artifact path"
            )
            contents = payload.get(artifact_path)
            if contents is None:
                raise PortableArchiveError(
                    f"portable completed artifact is missing: {run.run_id}/"
                    f"{artifact.path}"
                )
            if (
                len(contents) != artifact.size_bytes
                or _sha256(contents) != artifact.sha256
            ):
                raise PortableArchiveError(
                    f"portable completed artifact identity mismatch: {run.run_id}/"
                    f"{artifact.path}"
                )
            expected_roles[artifact_path] = "compact_result"

        receipt_path = f"{run_root}/{COMPLETION_RECEIPT}"
        receipt = payload.get(receipt_path)
        if receipt is None:
            raise PortableArchiveError(
                f"portable completion receipt is missing: {run.run_id}"
            )
        _validate_completion_receipt(receipt, run)
        expected_roles[receipt_path] = "manifest"

    actual_roles = {record.path: record.role for record in manifest.files}
    if actual_roles != expected_roles or set(payload) != set(expected_roles):
        raise PortableArchiveError(
            "portable project payload does not match project records"
        )


def _validate_completion_receipt(receipt: bytes, run: RunRecord) -> None:
    """Cross-check one carried receipt against its completed run record."""
    try:
        value = json.loads(receipt)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PortableArchiveError("invalid portable completion receipt") from error
    if not isinstance(value, dict) or set(value) != {
        "artifacts",
        "attempt",
        "run_id",
        "schema_version",
    }:
        raise PortableArchiveError("invalid portable completion receipt fields")
    try:
        artifacts = tuple(
            ArtifactRecord.model_validate(item) for item in value["artifacts"]
        )
    except (TypeError, ValidationError) as error:
        raise PortableArchiveError("invalid portable completion receipt") from error
    if (
        value["schema_version"] != PROJECT_SCHEMA_VERSION
        or value["run_id"] != run.run_id
        or value["attempt"] != run.attempt_count
        or artifacts != tuple(run.artifacts)
    ):
        raise PortableArchiveError("portable completion receipt identity mismatch")


def _reject_unexpected_artifact_paths(
    project_directory: Path, expected_run_directories: set[str]
) -> None:
    root = project_directory / "artifacts"
    actual = set()
    for child in root.iterdir():
        if child.is_symlink() or not child.is_dir():
            raise PortableArchiveError("project artifacts contain an unsafe path")
        actual.add(child.name)
    if actual != expected_run_directories:
        raise PortableArchiveError(
            "project contains unpublished or unexpected artifact directories"
        )


def _resolve_project_fixture(project_directory: Path, label: str) -> Path:
    path = Path(label)
    candidates = (
        [path]
        if path.is_absolute()
        else [project_directory / path, Path.cwd() / path]
    )
    if not path.is_absolute():
        try:
            candidates.append(runtime_root(Path.cwd()) / path)
        except (OSError, RuntimeError):
            pass
    for candidate in candidates:
        if candidate.is_file() and not candidate.is_symlink():
            return candidate.resolve()
    raise PortableArchiveError(f"project fixture is unavailable: {label}")


def _validate_zip_member(info: zipfile.ZipInfo) -> None:
    if info.filename != ARCHIVE_MANIFEST:
        _contained_archive_path(info.filename, label="archive member")
    if info.is_dir() or info.compress_type != zipfile.ZIP_STORED:
        raise PortableArchiveError(
            "portable archives contain stored regular files only"
        )
    if info.flag_bits & 0x1:
        raise PortableArchiveError("encrypted portable archive members are forbidden")
    mode = (info.external_attr >> 16) & 0o170000
    if mode not in {0, 0o100000}:
        raise PortableArchiveError("portable archive contains a non-regular member")


def _contained_archive_path(value: str, *, label: str) -> str:
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
        or path.parts[0] != "project"
    ):
        raise PortableArchiveError(f"{label} must be contained under project/")
    return path.as_posix()


def _write_member(archive: zipfile.ZipFile, name: str, contents: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=_ZIP_TIMESTAMP)
    info.create_system = 3
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, contents)


def _require_new_output(path: Path, *, label: str) -> None:
    if path.exists() or path.is_symlink():
        raise PortableArchiveError(f"{label} already exists: {path}")
    if not path.parent.is_dir():
        raise PortableArchiveError(f"{label} parent directory does not exist")


def _result(path: Path, manifest: PortableProjectManifest) -> PortableArchiveResult:
    return PortableArchiveResult(
        archive=str(path),
        archive_sha256=_sha256(path.read_bytes()),
        file_count=len(manifest.files),
        completed_run_count=sum(
            record.path.endswith(f"/{COMPLETION_RECEIPT}")
            for record in manifest.files
        ),
        project_id=manifest.project_id,
    )


def _completed_count(state: ProjectState) -> int:
    return sum(run.status is CampaignRunStatus.COMPLETED for run in state.runs)


def _manifest_bytes(manifest: PortableProjectManifest) -> bytes:
    return (manifest.model_dump_json(indent=2) + "\n").encode()


def _model_bytes(model: ProjectDefinition | ProjectState) -> bytes:
    return (model.model_dump_json(indent=2) + "\n").encode()


def _sha256(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()


def _write_bytes(path: Path, contents: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(contents)
        stream.flush()
        os.fsync(stream.fileno())
