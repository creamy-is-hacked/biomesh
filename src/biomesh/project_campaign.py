"""Persistent P4-WP01 project and campaign records over the accepted P3 API.

This module plans and executes deterministic local campaigns synchronously.
P4-WP05 may schedule this accepted execution boundary from a separate local
queue, but this module does not introduce reporting, plugins, parameter
registry, archive format, or a new scientific execution path.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import tempfile
from collections import Counter
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)

from biomesh.application import ApplicationService
from biomesh.application_types import RunRequest
from biomesh.application_types import RunStatus as ApplicationRunStatus
from biomesh.experiments import SweepParameter
from biomesh.p2_campaign import resolve_application_run
from biomesh.plugin_api import PluginSetManifest, plugin_set_sha256
from biomesh.registry_catalog import builtin_registry
from biomesh.registry_types import canonical_registry_sha256
from biomesh.runtime_resources import runtime_root

PROJECT_SCHEMA_VERSION = 2
LEGACY_PROJECT_SCHEMA_VERSION = 1
COMPLETION_RECEIPT_SCHEMA_VERSION = 2
PROJECT_MANIFEST = "project.json"
PROJECT_STATE = "campaign_state.json"
COMPLETION_RECEIPT = ".biomesh-completion.json"

Identifier = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    ),
]
NonBlankText = Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class ProjectCampaignError(ValueError):
    """Raised when a project or campaign operation cannot be completed safely."""


class ProjectRecord(BaseModel):
    """Immutable project identity and user-supplied purpose."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1]
    project_id: Identifier
    title: NonBlankText
    description: NonBlankText


class ExperimentRecord(BaseModel):
    """One accepted application fixture available to project campaigns."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1]
    experiment_id: Identifier
    title: NonBlankText
    fixture_file: NonBlankText
    fixture_sha256: Sha256
    calibration_status: Literal["CALIBRATION_REQUIRED"]
    notes: NonBlankText


class SeedPolicy(BaseModel):
    """Deterministic explicit or arithmetic replicate-seed policy."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    kind: Literal["explicit", "sequence"]
    seeds: list[int] = Field(default_factory=list)
    start: int | None = None
    step: int | None = None

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        values = self.seeds
        if any(isinstance(seed, bool) or seed < 0 for seed in values):
            raise ValueError("explicit seeds must be nonnegative integers")
        if len(values) != len(set(values)):
            raise ValueError("explicit seeds must be unique")
        if self.kind == "explicit":
            if not values or self.start is not None or self.step is not None:
                raise ValueError(
                    "explicit seed policy requires seeds and forbids start/step"
                )
        elif values or self.start is None or self.step is None:
            raise ValueError(
                "sequence seed policy requires start/step and forbids seeds"
            )
        elif (
            isinstance(self.start, bool)
            or isinstance(self.step, bool)
            or self.start < 0
            or self.step <= 0
        ):
            raise ValueError("sequence start must be nonnegative and step positive")
        return self

    def expand(self, replicate_count: int) -> tuple[int, ...]:
        """Return exactly one deterministic seed for every replicate."""
        if isinstance(replicate_count, bool) or replicate_count < 1:
            raise ProjectCampaignError("replicate_count must be a positive integer")
        if self.kind == "explicit":
            if len(self.seeds) != replicate_count:
                raise ProjectCampaignError(
                    "explicit seed count must equal campaign replicate_count"
                )
            return tuple(self.seeds)
        assert self.start is not None and self.step is not None
        return tuple(self.start + index * self.step for index in range(replicate_count))


class SweepPoint(BaseModel):
    """One explicit point in a provenance-complete SI sweep matrix."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    point_id: Identifier
    condition_id: NonBlankText
    parameters: list[SweepParameter] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_parameters(self) -> Self:
        names = [parameter.name for parameter in self.parameters]
        if len(names) != len(set(names)):
            raise ValueError("sweep point parameter names must be unique")
        return self


class CampaignRecord(BaseModel):
    """Immutable campaign plan before its run matrix is expanded."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1]
    campaign_id: Identifier
    experiment_id: Identifier
    title: NonBlankText
    replicate_count: int = Field(ge=1)
    seed_policy: SeedPolicy
    sweep_matrix: list[SweepPoint] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_matrix(self) -> Self:
        if isinstance(self.replicate_count, bool):
            raise ValueError("replicate_count must be a positive integer")
        point_ids = [point.point_id for point in self.sweep_matrix]
        if len(point_ids) != len(set(point_ids)):
            raise ValueError("sweep point IDs must be unique")
        self.seed_policy.expand(self.replicate_count)
        return self


class ExecutionModelIdentity(BaseModel):
    """One exact named/versioned built-in model and parameter-set selection."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    model_id: Identifier
    model_version: NonBlankText
    model_record_sha256: Sha256
    parameter_set_id: Identifier
    parameter_set_version: NonBlankText
    parameter_set_record_sha256: Sha256
    parameter_source: NonBlankText
    parameter_source_sha256: Sha256

    @model_validator(mode="after")
    def validate_parameter_source(self) -> Self:
        _safe_relative_path(self.parameter_source, label="parameter source")
        return self


class ExecutionIdentity(BaseModel):
    """Prospective registry and zero-plugin identity for accepted execution."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1]
    executor_id: Literal["org.biomesh.accepted-p2-fixture"]
    executor_version: Literal["1.0.0"]
    registry_schema_version: Literal[1]
    registry_sha256: Sha256
    models: list[ExecutionModelIdentity] = Field(min_length=1)
    plugin_api_version: Literal[1]
    plugin_set_kind: Literal["zero_plugin_core"]
    plugin_set_sha256: Sha256
    plugin_selection_sha256: list[Sha256] = Field(default_factory=list)
    calibration_status: Literal["CALIBRATION_REQUIRED"]

    @model_validator(mode="after")
    def validate_selection(self) -> Self:
        model_keys = [(item.model_id, item.model_version) for item in self.models]
        parameter_keys = [
            (item.parameter_set_id, item.parameter_set_version)
            for item in self.models
        ]
        if model_keys != sorted(model_keys) or len(model_keys) != len(set(model_keys)):
            raise ValueError("execution models must be unique and identity-sorted")
        if len(parameter_keys) != len(set(parameter_keys)):
            raise ValueError("execution parameter-set identities must be unique")
        if self.plugin_selection_sha256:
            raise ValueError(
                "accepted campaign execution requires exactly zero plugins"
            )
        return self


class ProjectDefinition(BaseModel):
    """Complete immutable project, experiment, and campaign definition."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1, 2]
    project: ProjectRecord
    experiments: list[ExperimentRecord] = Field(min_length=1)
    campaigns: list[CampaignRecord] = Field(min_length=1)
    execution_identity: ExecutionIdentity | None = None

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        experiment_ids = [item.experiment_id for item in self.experiments]
        campaign_ids = [item.campaign_id for item in self.campaigns]
        if len(experiment_ids) != len(set(experiment_ids)):
            raise ValueError("experiment IDs must be unique")
        if len(campaign_ids) != len(set(campaign_ids)):
            raise ValueError("campaign IDs must be unique")
        missing = sorted(
            {item.experiment_id for item in self.campaigns} - set(experiment_ids)
        )
        if missing:
            raise ValueError(
                "campaigns reference missing experiments: " + ", ".join(missing)
            )
        if self.schema_version == LEGACY_PROJECT_SCHEMA_VERSION:
            if self.execution_identity is not None:
                raise ValueError(
                    "schema-version 1 projects cannot declare execution_identity"
                )
        elif self.execution_identity is None:
            raise ValueError("schema-version 2 projects require execution_identity")
        return self


class CampaignRunStatus(StrEnum):
    """Persisted lifecycle for one campaign run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ArtifactRecord(BaseModel):
    """Hash and size identity for one immutable completed-run artifact."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    path: NonBlankText
    sha256: Sha256
    size_bytes: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_path(self) -> Self:
        _safe_relative_path(self.path, label="artifact path")
        if isinstance(self.size_bytes, bool):
            raise ValueError("artifact size_bytes must be an integer")
        return self


class RunFailureRecord(BaseModel):
    """Explicit retryable failure retained in campaign state."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    kind: Identifier
    message: NonBlankText
    retryable: Literal[True] = True


class RunRecord(BaseModel):
    """Immutable plan identity plus controlled mutable lifecycle fields."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    run_id: Identifier
    campaign_id: Identifier
    experiment_id: Identifier
    point_id: Identifier
    condition_id: NonBlankText
    replicate_index: int = Field(ge=0)
    seed: int = Field(ge=0)
    status: CampaignRunStatus
    attempt_count: int = Field(ge=0)
    artifacts: list[ArtifactRecord] = Field(default_factory=list)
    failure: RunFailureRecord | None = None

    @model_validator(mode="after")
    def validate_lifecycle(self) -> Self:
        if any(
            isinstance(value, bool)
            for value in (self.replicate_index, self.seed, self.attempt_count)
        ):
            raise ValueError("run indexes, seeds, and attempts must be integers")
        if self.status is CampaignRunStatus.COMPLETED:
            if not self.artifacts or self.failure is not None:
                raise ValueError("completed runs require artifacts and no failure")
        elif self.status is CampaignRunStatus.FAILED:
            if self.artifacts or self.failure is None:
                raise ValueError("failed runs require a failure and no artifacts")
        elif self.artifacts or self.failure is not None:
            raise ValueError("pending/running runs cannot contain results")
        return self


class AuditRecord(BaseModel):
    """Deterministically ordered immutable campaign-state transition record."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    sequence: int = Field(ge=0)
    action: Literal[
        "campaign_initialized",
        "run_started",
        "run_completed",
        "run_failed",
        "run_recovered",
        "run_retry_scheduled",
    ]
    campaign_id: Identifier
    run_id: Identifier | None = None
    attempt: int = Field(ge=0)
    detail: NonBlankText


class ProjectState(BaseModel):
    """Atomically replaced mutable state bound to one manifest hash."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1]
    definition_sha256: Sha256
    generation: int = Field(ge=0)
    runs: list[RunRecord]
    audit: list[AuditRecord]

    @model_validator(mode="after")
    def validate_state(self) -> Self:
        if isinstance(self.generation, bool):
            raise ValueError("state generation must be an integer")
        run_ids = [run.run_id for run in self.runs]
        if len(run_ids) != len(set(run_ids)):
            raise ValueError("state run IDs must be unique")
        if [record.sequence for record in self.audit] != list(range(len(self.audit))):
            raise ValueError("audit sequences must be contiguous from zero")
        return self


@dataclass(frozen=True, slots=True)
class RunExecutionRequest:
    """Resolved immutable request passed to one synchronous executor."""

    project_id: str
    experiment: ExperimentRecord
    campaign: CampaignRecord
    point: SweepPoint
    run: RunRecord
    fixture_file: Path
    execution_identity: ExecutionIdentity


RunExecutor = Callable[[RunExecutionRequest, Path], None]


@dataclass(frozen=True, slots=True)
class CampaignStatus:
    """Compact status returned by public campaign operations."""

    campaign_id: str
    total: int
    pending: int
    running: int
    completed: int
    failed: int

    def as_dict(self) -> dict[str, int | str]:
        return {
            "campaign_id": self.campaign_id,
            "completed": self.completed,
            "failed": self.failed,
            "pending": self.pending,
            "running": self.running,
            "total": self.total,
        }


def load_project_definition(path: Path) -> ProjectDefinition:
    """Load one strict versioned JSON project definition."""
    payload = _read_json(path, label="project definition")
    try:
        return ProjectDefinition.model_validate(payload)
    except ValidationError as error:
        raise ProjectCampaignError(
            f"invalid project definition {path}: {error}"
        ) from error


@lru_cache(maxsize=4)
def accepted_core_execution_identity(repository_root: Path) -> ExecutionIdentity:
    """Return the code-owned registry and empty-plugin identity for new runs."""
    registry = builtin_registry(repository_root)
    parameter_sets = {
        (entry.record.model_id, entry.record.model_version): entry
        for entry in registry.parameter_sets
    }
    models: list[ExecutionModelIdentity] = []
    for model_entry in registry.models:
        model = model_entry.record
        parameter_entry = parameter_sets[(model.model_id, model.model_version)]
        parameter_set = parameter_entry.record
        models.append(
            ExecutionModelIdentity(
                model_id=model.model_id,
                model_version=model.model_version,
                model_record_sha256=model_entry.record_sha256,
                parameter_set_id=parameter_set.parameter_set_id,
                parameter_set_version=parameter_set.parameter_set_version,
                parameter_set_record_sha256=parameter_entry.record_sha256,
                parameter_source=parameter_set.source,
                parameter_source_sha256=parameter_set.source_sha256,
            )
        )
    empty_plugins = PluginSetManifest(schema_version=1, plugins=[])
    return ExecutionIdentity(
        schema_version=1,
        executor_id="org.biomesh.accepted-p2-fixture",
        executor_version="1.0.0",
        registry_schema_version=registry.schema_version,
        registry_sha256=canonical_registry_sha256(registry),
        models=models,
        plugin_api_version=1,
        plugin_set_kind="zero_plugin_core",
        plugin_set_sha256=plugin_set_sha256(empty_plugins),
        plugin_selection_sha256=[],
        calibration_status="CALIBRATION_REQUIRED",
    )


def execution_identity_sha256(identity: ExecutionIdentity) -> str:
    """Return the canonical SHA-256 for one complete execution selection."""
    return hashlib.sha256(_model_bytes(identity)).hexdigest()


def create_project(definition_file: Path, project_directory: Path) -> Path:
    """Atomically create a local project from a strict immutable definition."""
    definition = load_project_definition(definition_file)
    definition = _normalize_and_validate_definition(
        definition, definition_file.parent.resolve()
    )
    if project_directory.exists() or project_directory.is_symlink():
        raise ProjectCampaignError(
            f"project directory already exists: {project_directory}"
        )
    if not project_directory.parent.is_dir():
        raise ProjectCampaignError("project directory parent must exist")
    manifest_bytes = _model_bytes(definition)
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    runs = _planned_runs(definition)
    audit = [
        AuditRecord(
            sequence=index,
            action="campaign_initialized",
            campaign_id=campaign.campaign_id,
            attempt=0,
            detail=(
                "planned "
                f"{sum(run.campaign_id == campaign.campaign_id for run in runs)} runs"
            ),
        )
        for index, campaign in enumerate(definition.campaigns)
    ]
    state = ProjectState(
        schema_version=1,
        definition_sha256=manifest_hash,
        generation=0,
        runs=runs,
        audit=audit,
    )
    temporary = Path(
        tempfile.mkdtemp(
            prefix=f".{project_directory.name}.", dir=project_directory.parent
        )
    )
    try:
        (temporary / "artifacts").mkdir()
        _write_bytes(temporary / PROJECT_MANIFEST, manifest_bytes)
        _write_bytes(temporary / PROJECT_STATE, _model_bytes(state))
        (temporary / ".campaign.lock").touch()
        os.replace(temporary, project_directory)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return project_directory


class CampaignService:
    """Synchronous, lock-protected campaign lifecycle service."""

    def __init__(
        self, project_directory: Path, *, executor: RunExecutor | None = None
    ) -> None:
        self.project_directory = project_directory.resolve()
        self._executor = executor or execute_application_run

    def status(self, campaign_id: str) -> CampaignStatus:
        """Validate the project and return explicit counts without mutation."""
        with self._lock():
            definition, state = self._load()
            _campaign(definition, campaign_id)
            return _campaign_status(state, campaign_id)

    def progress(self, campaign_id: str) -> CampaignStatus:
        """Return one atomic run-count snapshot without waiting for execution.

        The queue uses this read-only path while a campaign process owns the
        project lock. Final queue transitions still use :meth:`status`, which
        verifies every completed artifact.
        """
        definition, state = self._load(verify_artifacts=False)
        _campaign(definition, campaign_id)
        return _campaign_status(state, campaign_id)

    def preflight_execution(self, campaign_id: str) -> ExecutionIdentity:
        """Verify prospective execution identity without changing campaign state."""
        with self._lock():
            definition, state = self._load()
            _campaign(definition, campaign_id)
            return _require_execution_identity(definition, state, campaign_id)

    def verified_records(self) -> tuple[ProjectDefinition, ProjectState]:
        """Return validated records after verifying all project artifacts."""
        with self.verified_snapshot() as records:
            return records

    @contextmanager
    def verified_snapshot(
        self, *, blocking: bool = True
    ) -> Iterator[tuple[ProjectDefinition, ProjectState]]:
        """Hold the project lock while a caller reads one verified snapshot."""
        with self._lock(blocking=blocking):
            yield self._load()

    def resume(self, campaign_id: str) -> CampaignStatus:
        """Reconcile interrupted work and execute only pending campaign runs."""
        with self._lock():
            definition, state = self._load()
            _campaign(definition, campaign_id)
            _require_execution_identity(definition, state, campaign_id)
            state = self._reconcile_interrupted(definition, state, campaign_id)
            return self._execute_pending(definition, state, campaign_id)

    def retry(
        self, campaign_id: str, run_ids: Sequence[str] | None = None
    ) -> CampaignStatus:
        """Explicitly schedule failed runs, preserving completed-run immutability."""
        with self._lock():
            definition, state = self._load()
            _campaign(definition, campaign_id)
            _require_execution_identity(definition, state, campaign_id)
            state = self._reconcile_interrupted(definition, state, campaign_id)
            failed = {
                run.run_id: run
                for run in state.runs
                if run.campaign_id == campaign_id
                and run.status is CampaignRunStatus.FAILED
            }
            selected = list(failed) if run_ids is None else list(run_ids)
            if not selected:
                raise ProjectCampaignError("campaign has no failed runs to retry")
            if len(selected) != len(set(selected)):
                raise ProjectCampaignError("retry run IDs must be unique")
            invalid = sorted(set(selected) - set(failed))
            if invalid:
                raise ProjectCampaignError(
                    "retry requires failed run IDs from this campaign: "
                    + ", ".join(invalid)
                )
            replacements: dict[str, RunRecord] = {}
            audit = list(state.audit)
            for run_id in selected:
                run = failed[run_id]
                replacements[run_id] = run.model_copy(
                    update={
                        "status": CampaignRunStatus.PENDING,
                        "failure": None,
                    }
                )
                audit.append(
                    _audit(
                        audit,
                        "run_retry_scheduled",
                        run,
                        detail="explicit retry scheduled",
                    )
                )
            state = state.model_copy(
                update={
                    "generation": state.generation + 1,
                    "runs": [replacements.get(run.run_id, run) for run in state.runs],
                    "audit": audit,
                }
            )
            self._write_state(state)
            return self._execute_pending(definition, state, campaign_id)

    def recover_interrupted(
        self, campaign_id: str, *, cancellation_requested: bool = False
    ) -> CampaignStatus:
        """Reconcile a dead local worker without scheduling additional runs."""
        with self._lock():
            definition, state = self._load()
            _campaign(definition, campaign_id)
            state = self._reconcile_interrupted(
                definition,
                state,
                campaign_id,
                cancellation_requested=cancellation_requested,
            )
            return _campaign_status(state, campaign_id)

    @contextmanager
    def _lock(self, *, blocking: bool = True) -> Any:
        lock_path = self.project_directory / ".campaign.lock"
        if (
            not self.project_directory.is_dir()
            or not lock_path.is_file()
            or lock_path.is_symlink()
        ):
            raise ProjectCampaignError(
                f"not a BioMesh project directory: {self.project_directory}"
            )
        try:
            with lock_path.open("r+") as lock_file:
                operation = fcntl.LOCK_EX
                if not blocking:
                    operation |= fcntl.LOCK_NB
                try:
                    fcntl.flock(lock_file.fileno(), operation)
                except BlockingIOError as error:
                    raise ProjectCampaignError(
                        "project has an active campaign operation"
                    ) from error
                yield
        except OSError as error:
            raise ProjectCampaignError(f"unable to lock project: {error}") from error

    def _load(
        self, *, verify_artifacts: bool = True
    ) -> tuple[ProjectDefinition, ProjectState]:
        manifest_path = self.project_directory / PROJECT_MANIFEST
        state_path = self.project_directory / PROJECT_STATE
        artifact_root = self.project_directory / "artifacts"
        if (
            not manifest_path.is_file()
            or manifest_path.is_symlink()
            or not state_path.is_file()
            or state_path.is_symlink()
            or not artifact_root.is_dir()
            or artifact_root.is_symlink()
        ):
            raise ProjectCampaignError(
                "project layout is incomplete or contains symlinks"
            )
        definition = load_project_definition(manifest_path)
        manifest_bytes = manifest_path.read_bytes()
        expected_hash = hashlib.sha256(manifest_bytes).hexdigest()
        try:
            state_contents = state_path.read_text(encoding="utf-8")
            state = ProjectState.model_validate_json(state_contents)
        except (OSError, ValidationError) as error:
            raise ProjectCampaignError(f"invalid project state: {error}") from error
        if state.definition_sha256 != expected_hash:
            raise ProjectCampaignError("project definition hash does not match state")
        planned = _planned_runs(definition)
        if [_plan_identity(run) for run in state.runs] != [
            _plan_identity(run) for run in planned
        ]:
            raise ProjectCampaignError("project state run plan does not match manifest")
        if verify_artifacts:
            self._verify_artifact_layout(definition, state)
        return definition, state

    def _write_state(self, state: ProjectState) -> None:
        _atomic_write_bytes(self.project_directory / PROJECT_STATE, _model_bytes(state))

    def _reconcile_interrupted(
        self,
        definition: ProjectDefinition,
        state: ProjectState,
        campaign_id: str,
        *,
        cancellation_requested: bool = False,
    ) -> ProjectState:
        replacements: dict[str, RunRecord] = {}
        audit = list(state.audit)
        for run in state.runs:
            if (
                run.campaign_id != campaign_id
                or run.status is not CampaignRunStatus.RUNNING
            ):
                continue
            recovered = self._recover_published_run(
                run, definition.execution_identity
            )
            if recovered is not None:
                replacements[run.run_id] = recovered
                audit.append(
                    _audit(
                        audit,
                        "run_recovered",
                        recovered,
                        detail="recovered hash-verified published artifacts",
                    )
                )
            else:
                failure_kind = "cancelled" if cancellation_requested else "interrupted"
                failure_message = (
                    "local queue cancellation stopped execution before artifact "
                    "publication"
                    if cancellation_requested
                    else "previous execution ended before artifact publication"
                )
                failed = run.model_copy(
                    update={
                        "status": CampaignRunStatus.FAILED,
                        "failure": RunFailureRecord(
                            kind=failure_kind,
                            message=failure_message,
                        ),
                    }
                )
                replacements[run.run_id] = failed
                assert failed.failure is not None
                audit.append(
                    _audit(
                        audit,
                        "run_failed",
                        failed,
                        detail=failed.failure.message,
                    )
                )
        if not replacements:
            return state
        updated = state.model_copy(
            update={
                "generation": state.generation + 1,
                "runs": [replacements.get(run.run_id, run) for run in state.runs],
                "audit": audit,
            }
        )
        self._write_state(updated)
        return updated

    def _execute_pending(
        self,
        definition: ProjectDefinition,
        state: ProjectState,
        campaign_id: str,
    ) -> CampaignStatus:
        campaign = _campaign(definition, campaign_id)
        execution_identity = _require_execution_identity(
            definition, state, campaign_id
        )
        experiment = _experiment(definition, campaign.experiment_id)
        point_by_id = {point.point_id: point for point in campaign.sweep_matrix}
        fixture = _resolve_fixture_file(experiment.fixture_file, self.project_directory)
        for planned in tuple(state.runs):
            current = next(run for run in state.runs if run.run_id == planned.run_id)
            if (
                current.campaign_id != campaign_id
                or current.status is not CampaignRunStatus.PENDING
            ):
                continue
            running = current.model_copy(
                update={
                    "status": CampaignRunStatus.RUNNING,
                    "attempt_count": current.attempt_count + 1,
                }
            )
            state = _replace_run_with_audit(
                state, running, "run_started", "synchronous run started"
            )
            self._write_state(state)
            request = RunExecutionRequest(
                project_id=definition.project.project_id,
                experiment=experiment,
                campaign=campaign,
                point=point_by_id[running.point_id],
                run=running,
                fixture_file=fixture,
                execution_identity=execution_identity,
            )
            try:
                artifacts = self._run_and_publish(request)
            except Exception as error:
                failed = running.model_copy(
                    update={
                        "status": CampaignRunStatus.FAILED,
                        "failure": RunFailureRecord(
                            kind=_failure_kind(error),
                            message=str(error) or error.__class__.__name__,
                        ),
                    }
                )
                assert failed.failure is not None
                state = _replace_run_with_audit(
                    state, failed, "run_failed", failed.failure.message
                )
                self._write_state(state)
                continue
            completed = running.model_copy(
                update={
                    "status": CampaignRunStatus.COMPLETED,
                    "artifacts": list(artifacts),
                }
            )
            state = _replace_run_with_audit(
                state,
                completed,
                "run_completed",
                f"published {len(artifacts)} hash-verified artifacts",
            )
            self._write_state(state)
        return _campaign_status(state, campaign_id)

    def _run_and_publish(
        self, request: RunExecutionRequest
    ) -> tuple[ArtifactRecord, ...]:
        artifact_root = self.project_directory / "artifacts"
        final = artifact_root / request.run.run_id
        if final.exists() or final.is_symlink():
            raise ProjectCampaignError(
                f"run artifact directory already exists: {request.run.run_id}"
            )
        staging = Path(
            tempfile.mkdtemp(prefix=f".{request.run.run_id}.", dir=artifact_root)
        )
        try:
            self._executor(request, staging)
            artifacts = _collect_artifacts(staging)
            if not artifacts:
                raise ProjectCampaignError("run executor produced no artifacts")
            receipt = {
                "artifacts": [item.model_dump(mode="json") for item in artifacts],
                "attempt": request.run.attempt_count,
                "execution_identity": request.execution_identity.model_dump(
                    mode="json"
                ),
                "execution_identity_sha256": execution_identity_sha256(
                    request.execution_identity
                ),
                "run_id": request.run.run_id,
                "schema_version": COMPLETION_RECEIPT_SCHEMA_VERSION,
            }
            _write_bytes(
                staging / COMPLETION_RECEIPT,
                (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode(),
            )
            os.replace(staging, final)
            return artifacts
        finally:
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)

    def _recover_published_run(
        self,
        run: RunRecord,
        execution_identity: ExecutionIdentity | None,
    ) -> RunRecord | None:
        directory = self.project_directory / "artifacts" / run.run_id
        if not directory.exists():
            return None
        artifacts = self._completion_artifacts(run, directory, execution_identity)
        _verify_artifact_directory(directory, artifacts)
        return run.model_copy(
            update={
                "status": CampaignRunStatus.COMPLETED,
                "artifacts": list(artifacts),
            }
        )

    def _completion_artifacts(
        self,
        run: RunRecord,
        directory: Path,
        execution_identity: ExecutionIdentity | None,
    ) -> tuple[ArtifactRecord, ...]:
        receipt_path = directory / COMPLETION_RECEIPT
        if not receipt_path.is_file() or receipt_path.is_symlink():
            raise ProjectCampaignError("completion receipt is missing or is a symlink")
        payload = _read_json(receipt_path, label="completion receipt")
        if not isinstance(payload, dict):
            raise ProjectCampaignError("invalid completion receipt fields")
        receipt_version = payload.get("schema_version")
        legacy_fields = {"artifacts", "attempt", "run_id", "schema_version"}
        current_fields = legacy_fields | {
            "execution_identity",
            "execution_identity_sha256",
        }
        if receipt_version == LEGACY_PROJECT_SCHEMA_VERSION:
            if set(payload) != legacy_fields or execution_identity is not None:
                raise ProjectCampaignError("invalid legacy completion receipt fields")
        elif receipt_version == COMPLETION_RECEIPT_SCHEMA_VERSION:
            if set(payload) != current_fields or execution_identity is None:
                raise ProjectCampaignError("invalid completion receipt fields")
            try:
                receipt_identity = ExecutionIdentity.model_validate(
                    payload["execution_identity"]
                )
            except ValidationError as error:
                raise ProjectCampaignError(
                    f"invalid completion execution identity: {error}"
                ) from error
            if (
                receipt_identity != execution_identity
                or payload["execution_identity_sha256"]
                != execution_identity_sha256(execution_identity)
            ):
                raise ProjectCampaignError("completion execution identity mismatch")
        else:
            raise ProjectCampaignError("unsupported completion receipt schema_version")
        if payload["run_id"] != run.run_id or payload["attempt"] != run.attempt_count:
            raise ProjectCampaignError("completion receipt identity mismatch")
        try:
            artifacts = tuple(
                ArtifactRecord.model_validate(item) for item in payload["artifacts"]
            )
        except (TypeError, ValidationError) as error:
            raise ProjectCampaignError(
                f"invalid completion receipt: {error}"
            ) from error
        return artifacts

    def _verify_artifact_layout(
        self, definition: ProjectDefinition, state: ProjectState
    ) -> None:
        artifact_root = self.project_directory / "artifacts"
        run_by_id = {run.run_id: run for run in state.runs}
        for path in artifact_root.iterdir():
            if path.name.startswith("."):
                if path.is_symlink():
                    raise ProjectCampaignError(
                        "artifact staging path must not be a symlink"
                    )
                continue
            run = run_by_id.get(path.name)
            if run is None:
                raise ProjectCampaignError(
                    f"project contains artifacts for unknown run {path.name}"
                )
            if run.status not in {
                CampaignRunStatus.RUNNING,
                CampaignRunStatus.COMPLETED,
            }:
                raise ProjectCampaignError(
                    f"non-running run has unexpected artifacts: {run.run_id}"
                )
        for run in state.runs:
            if run.status is CampaignRunStatus.COMPLETED:
                directory = self.project_directory / "artifacts" / run.run_id
                receipt_artifacts = self._completion_artifacts(
                    run, directory, definition.execution_identity
                )
                if receipt_artifacts != tuple(run.artifacts):
                    raise ProjectCampaignError(
                        "completed run receipt does not match project state"
                    )
                _verify_artifact_directory(directory, tuple(run.artifacts))


def execute_application_run(request: RunExecutionRequest, output: Path) -> None:
    """Execute one planned run solely through the accepted P3 application API."""
    resolved = resolve_application_run(
        fixture_file=request.fixture_file,
        condition_id=request.run.condition_id,
        seed=request.run.seed,
    )
    if resolved.fixture_sha256 != request.experiment.fixture_sha256:
        raise ProjectCampaignError("experiment fixture hash changed before execution")
    actual_parameters = [
        item.model_dump(mode="json")
        for item in resolved.request.condition.parameter_overrides
    ]
    expected_parameters = [
        item.model_dump(mode="json") for item in request.point.parameters
    ]
    if actual_parameters != expected_parameters:
        raise ProjectCampaignError(
            "sweep point parameters do not match the accepted fixture condition"
        )
    actual_parameter_sources = {
        Path(record.label).name: record.sha256
        for record in resolved.request.parameter_files
    }
    expected_parameter_sources = {
        Path(model.parameter_source).name: model.parameter_source_sha256
        for model in request.execution_identity.models
    }
    if actual_parameter_sources != expected_parameter_sources:
        raise ProjectCampaignError(
            "execution parameter resources do not match the selected registry "
            "identity"
        )
    request_record = {
        "calibration_status": request.experiment.calibration_status,
        "campaign_id": request.campaign.campaign_id,
        "condition_id": request.run.condition_id,
        "execution_identity": request.execution_identity.model_dump(mode="json"),
        "execution_identity_sha256": execution_identity_sha256(
            request.execution_identity
        ),
        "experiment_id": request.experiment.experiment_id,
        "fixture_sha256": request.experiment.fixture_sha256,
        "point": request.point.model_dump(mode="json"),
        "project_id": request.project_id,
        "replicate_index": request.run.replicate_index,
        "run_id": request.run.run_id,
        "schema_version": PROJECT_SCHEMA_VERSION,
        "seed": request.run.seed,
    }
    _write_bytes(
        output / "run_request.json",
        (json.dumps(request_record, indent=2, sort_keys=True) + "\n").encode(),
    )
    with ApplicationService() as service:
        snapshot = service.run(
            RunRequest(
                fixture_file=request.fixture_file,
                condition_id=request.run.condition_id,
                seed=request.run.seed,
            )
        )
        while snapshot.status is not ApplicationRunStatus.COMPLETED:
            snapshot = service.step()
        service.export(output / "raw")


def _normalize_and_validate_definition(
    definition: ProjectDefinition, definition_parent: Path
) -> ProjectDefinition:
    if definition.execution_identity is not None:
        expected_identity = accepted_core_execution_identity(
            runtime_root(Path.cwd())
        )
        if definition.execution_identity != expected_identity:
            raise ProjectCampaignError(
                "project execution_identity does not match the accepted built-in "
                "model registry and zero-plugin core selection"
            )
    experiments: list[ExperimentRecord] = []
    for experiment in definition.experiments:
        fixture = _resolve_fixture_file(experiment.fixture_file, definition_parent)
        actual_hash = hashlib.sha256(fixture.read_bytes()).hexdigest()
        if actual_hash != experiment.fixture_sha256:
            raise ProjectCampaignError(
                f"fixture hash mismatch for experiment {experiment.experiment_id}"
            )
        fixture_label = experiment.fixture_file
        candidate = Path(fixture_label)
        if not candidate.is_absolute():
            try:
                packaged = runtime_root(Path.cwd()) / candidate
            except OSError, RuntimeError:
                packaged = Path()
            if not packaged.is_file():
                fixture_label = str(fixture)
        experiments.append(
            experiment.model_copy(update={"fixture_file": fixture_label})
        )
    normalized = definition.model_copy(update={"experiments": experiments})
    for campaign in normalized.campaigns:
        experiment = _experiment(normalized, campaign.experiment_id)
        fixture = _resolve_fixture_file(experiment.fixture_file, definition_parent)
        for point in campaign.sweep_matrix:
            resolved = resolve_application_run(
                fixture_file=fixture,
                condition_id=point.condition_id,
                seed=campaign.seed_policy.expand(campaign.replicate_count)[0],
            )
            actual = [
                item.model_dump(mode="json")
                for item in resolved.request.condition.parameter_overrides
            ]
            expected = [item.model_dump(mode="json") for item in point.parameters]
            if actual != expected:
                raise ProjectCampaignError(
                    f"sweep point {point.point_id} parameters do not match "
                    f"condition {point.condition_id}"
                )
    return normalized


def _require_execution_identity(
    definition: ProjectDefinition,
    state: ProjectState,
    campaign_id: str,
) -> ExecutionIdentity:
    identity = definition.execution_identity
    if identity is None:
        unfinished = any(
            run.campaign_id == campaign_id
            and run.status is not CampaignRunStatus.COMPLETED
            for run in state.runs
        )
        detail = "unfinished" if unfinished else "completed"
        raise ProjectCampaignError(
            f"legacy schema-version 1 {detail} campaign has no explicit execution "
            "identity; historical results remain readable, but execution and "
            "provenance backfilling are forbidden"
        )
    expected = accepted_core_execution_identity(runtime_root(Path.cwd()))
    if identity != expected:
        raise ProjectCampaignError(
            "project execution_identity does not match the accepted built-in model "
            "registry and zero-plugin core selection"
        )
    return identity


def _planned_runs(definition: ProjectDefinition) -> list[RunRecord]:
    runs: list[RunRecord] = []
    for campaign in definition.campaigns:
        seeds = campaign.seed_policy.expand(campaign.replicate_count)
        for point in campaign.sweep_matrix:
            for replicate_index, seed in enumerate(seeds):
                descriptor = (
                    f"{definition.project.project_id}\0{campaign.campaign_id}\0"
                    f"{point.point_id}\0{replicate_index}\0{seed}"
                ).encode()
                suffix = hashlib.sha256(descriptor).hexdigest()[:12]
                run_id = f"{campaign.campaign_id}-{point.point_id}-{suffix}"
                runs.append(
                    RunRecord(
                        run_id=run_id,
                        campaign_id=campaign.campaign_id,
                        experiment_id=campaign.experiment_id,
                        point_id=point.point_id,
                        condition_id=point.condition_id,
                        replicate_index=replicate_index,
                        seed=seed,
                        status=CampaignRunStatus.PENDING,
                        attempt_count=0,
                    )
                )
    return runs


def _campaign(definition: ProjectDefinition, campaign_id: str) -> CampaignRecord:
    try:
        return next(
            item for item in definition.campaigns if item.campaign_id == campaign_id
        )
    except StopIteration as error:
        raise ProjectCampaignError(
            f"project has no campaign {campaign_id!r}"
        ) from error


def _experiment(definition: ProjectDefinition, experiment_id: str) -> ExperimentRecord:
    return next(
        item for item in definition.experiments if item.experiment_id == experiment_id
    )


def _campaign_status(state: ProjectState, campaign_id: str) -> CampaignStatus:
    statuses = Counter(
        run.status for run in state.runs if run.campaign_id == campaign_id
    )
    total = sum(statuses.values())
    return CampaignStatus(
        campaign_id=campaign_id,
        total=total,
        pending=statuses[CampaignRunStatus.PENDING],
        running=statuses[CampaignRunStatus.RUNNING],
        completed=statuses[CampaignRunStatus.COMPLETED],
        failed=statuses[CampaignRunStatus.FAILED],
    )


def _replace_run_with_audit(
    state: ProjectState,
    run: RunRecord,
    action: Literal["run_started", "run_completed", "run_failed"],
    detail: str,
) -> ProjectState:
    audit = list(state.audit)
    audit.append(_audit(audit, action, run, detail=detail))
    return state.model_copy(
        update={
            "generation": state.generation + 1,
            "runs": [run if item.run_id == run.run_id else item for item in state.runs],
            "audit": audit,
        }
    )


def _audit(
    audit: Sequence[AuditRecord],
    action: Literal[
        "run_started",
        "run_completed",
        "run_failed",
        "run_recovered",
        "run_retry_scheduled",
    ],
    run: RunRecord,
    *,
    detail: str,
) -> AuditRecord:
    return AuditRecord(
        sequence=len(audit),
        action=action,
        campaign_id=run.campaign_id,
        run_id=run.run_id,
        attempt=run.attempt_count,
        detail=detail,
    )


def _failure_kind(error: Exception) -> str:
    name = error.__class__.__name__.replace("Error", "").lower()
    return name if name and name[0].isalnum() else "execution"


def _collect_artifacts(directory: Path) -> tuple[ArtifactRecord, ...]:
    records: list[ArtifactRecord] = []
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ProjectCampaignError(
                f"run artifacts must not contain symlinks: {path}"
            )
        if path.is_file():
            relative = path.relative_to(directory).as_posix()
            if relative == COMPLETION_RECEIPT:
                raise ProjectCampaignError(
                    f"run executor must not create reserved {COMPLETION_RECEIPT}"
                )
            contents = path.read_bytes()
            records.append(
                ArtifactRecord(
                    path=relative,
                    sha256=hashlib.sha256(contents).hexdigest(),
                    size_bytes=len(contents),
                )
            )
    return tuple(records)


def _verify_artifact_directory(
    directory: Path, artifacts: tuple[ArtifactRecord, ...]
) -> None:
    if not directory.is_dir() or directory.is_symlink():
        raise ProjectCampaignError(
            f"completed run artifact directory is missing: {directory}"
        )
    expected = {artifact.path: artifact for artifact in artifacts}
    actual: set[str] = set()
    for path in directory.rglob("*"):
        if path.is_symlink():
            raise ProjectCampaignError(
                "completed run artifacts must not contain symlinks"
            )
        if not path.is_file():
            continue
        relative = path.relative_to(directory).as_posix()
        if relative == COMPLETION_RECEIPT:
            continue
        actual.add(relative)
        record = expected.get(relative)
        if record is None:
            raise ProjectCampaignError(
                f"completed run has unrecorded artifact {relative}"
            )
        contents = path.read_bytes()
        if (
            len(contents) != record.size_bytes
            or hashlib.sha256(contents).hexdigest() != record.sha256
        ):
            raise ProjectCampaignError(f"completed run artifact changed: {relative}")
    if actual != set(expected):
        missing = sorted(set(expected) - actual)
        raise ProjectCampaignError(
            "completed run artifacts are missing: " + ", ".join(missing)
        )


def _resolve_fixture_file(label: str, base: Path) -> Path:
    path = Path(label)
    candidates = [path] if path.is_absolute() else [base / path, Path.cwd() / path]
    if not path.is_absolute():
        try:
            candidates.append(runtime_root(Path.cwd()) / path)
        except OSError, RuntimeError:
            pass
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise ProjectCampaignError(f"experiment fixture is unavailable: {label}")


def _safe_relative_path(value: str, *, label: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError(f"{label} must be a contained relative POSIX path")
    return path


def _plan_identity(run: RunRecord) -> tuple[object, ...]:
    return (
        run.run_id,
        run.campaign_id,
        run.experiment_id,
        run.point_id,
        run.condition_id,
        run.replicate_index,
        run.seed,
    )


def _read_json(path: Path, *, label: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ProjectCampaignError(f"unable to read {label} {path}: {error}") from error


def _model_bytes(model: BaseModel) -> bytes:
    return (model.model_dump_json(indent=2) + "\n").encode()


def _write_bytes(path: Path, contents: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(contents)
        stream.flush()
        os.fsync(stream.fileno())


def _atomic_write_bytes(path: Path, contents: bytes) -> None:
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
