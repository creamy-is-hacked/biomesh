"""Calibration-gated deterministic reference run and reproduction for P1-WP07."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import tomllib
from pathlib import Path
from typing import Annotated, Literal, Self

import numpy as np
from pydantic import (
    AllowInfNan,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)

from biomesh.config import load_parameter_file
from biomesh.mass_balance import solute_amount_mol, top_boundary_input_rate_mol_s
from biomesh.outputs import MassBalanceEntry, OutputPaths, SimulationOutputWriter
from biomesh.provenance import collect_run_metadata
from biomesh.solutes import SoluteField, SoluteFields

DEFAULT_REFERENCE_PARAMETER_FILE = Path("parameters/phase1_reference.toml")
NonBlankText = Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]
FiniteFloat = Annotated[float, AllowInfNan(allow_inf_nan=False)]


class ReferenceValidationError(ValueError):
    """Raised when the software reference or reproduction contract is invalid."""


class ZeroStateFixture(BaseModel):
    """Explicit non-scientific state used only to prove deterministic replay."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    grid_rows: int = Field(ge=2)
    grid_columns: int = Field(ge=2)
    domain_width_m: FiniteFloat = Field(gt=0.0)
    domain_height_m: FiniteFloat = Field(gt=0.0)
    depth_m: FiniteFloat = Field(gt=0.0)
    carbon_concentration_mol_m3: FiniteFloat
    oxygen_concentration_mol_m3: FiniteFloat
    carbon_diffusivity_m2_s: FiniteFloat
    oxygen_diffusivity_m2_s: FiniteFloat
    carbon_top_bulk_concentration_mol_m3: FiniteFloat
    oxygen_top_bulk_concentration_mol_m3: FiniteFloat

    @model_validator(mode="after")
    def require_zero_state(self) -> Self:
        """Reject any attempt to turn the placeholder into numeric biology."""
        values = (
            self.carbon_concentration_mol_m3,
            self.oxygen_concentration_mol_m3,
            self.carbon_diffusivity_m2_s,
            self.oxygen_diffusivity_m2_s,
            self.carbon_top_bulk_concentration_mol_m3,
            self.oxygen_top_bulk_concentration_mol_m3,
        )
        if any(value != 0.0 for value in values):
            raise ValueError("zero-state fixture solute values must all be zero")
        return self


class ReferenceConfiguration(BaseModel):
    """Traceable configuration for the calibration-placeholder reference."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1]
    purpose: Literal["P1-WP07 deterministic software reproducibility reference"]
    calibration_status: Literal["CALIBRATION_REQUIRED"]
    biological_parameter_file: NonBlankText
    seed: int = Field(ge=0)
    output_directory: NonBlankText
    notes: NonBlankText
    zero_state_fixture: ZeroStateFixture

    @model_validator(mode="after")
    def reject_scientific_claims(self) -> Self:
        """Keep the placeholder reference explicitly non-scientific."""
        if "not a biological experiment" not in self.notes:
            raise ValueError(
                "reference notes must state that this is not a biological experiment"
            )
        return self


def load_reference_configuration(path: Path) -> ReferenceConfiguration:
    """Load the strict P1-WP07 software-reference document."""
    try:
        with path.open("rb") as parameter_file:
            contents = tomllib.load(parameter_file)
    except OSError as error:
        raise ReferenceValidationError(
            f"unable to read reference parameter file {path}: "
            f"{error.strerror or error}"
        ) from error
    except tomllib.TOMLDecodeError as error:
        raise ReferenceValidationError(
            f"invalid TOML in reference parameter file {path}: {error}"
        ) from error
    try:
        return ReferenceConfiguration.model_validate(contents)
    except ValidationError as error:
        raise ReferenceValidationError(
            f"invalid reference parameter file {path}: {error}"
        ) from error


def run_reference(
    *,
    parameter_file: Path,
    output_directory: Path | None = None,
    seed: int | None = None,
    repository_root: Path | None = None,
) -> OutputPaths:
    """Write the deterministic zero-state reference without resolving biology."""
    configuration = load_reference_configuration(parameter_file)
    biological_file = parameter_file.parent / configuration.biological_parameter_file
    biological_parameters = load_parameter_file(biological_file)
    unresolved = [
        parameter.name
        for parameter in biological_parameters.biological_parameters
        if parameter.value != "CALIBRATION_REQUIRED"
    ]
    if unresolved:
        raise ReferenceValidationError(
            "software reference requires an entirely CALIBRATION_REQUIRED "
            "biological manifest; numeric entries found: " + ", ".join(unresolved)
        )
    selected_seed = configuration.seed if seed is None else seed
    if (
        not isinstance(selected_seed, int)
        or isinstance(selected_seed, bool)
        or selected_seed < 0
    ):
        raise ReferenceValidationError("seed must be a nonnegative integer")
    run_directory = (
        _resolve_from_root(configuration.output_directory, repository_root)
        if output_directory is None
        else output_directory
    )
    parameter_label = _path_label(parameter_file, repository_root)
    parameters: dict[str, object] = {
        "biological_manifest": biological_parameters.model_dump(mode="json"),
        "biological_parameter_file_sha256": hashlib.sha256(
            biological_file.read_bytes()
        ).hexdigest(),
        "reference_configuration": configuration.model_dump(mode="json"),
        "effective_seed": selected_seed,
        "run_classification": "CALIBRATION_REQUIRED_NON_SCIENTIFIC_REFERENCE",
    }
    metadata = collect_run_metadata(
        parameter_file=parameter_file,
        parameter_file_label=parameter_label,
        parameters=parameters,
        seed=selected_seed,
        repository_root=repository_root,
    )
    fixture = configuration.zero_state_fixture
    shape = (fixture.grid_rows, fixture.grid_columns)
    fields = SoluteFields(
        carbon=SoluteField(
            name="carbon",
            shape=shape,
            width_m=fixture.domain_width_m,
            height_m=fixture.domain_height_m,
            diffusivity_m2_s=fixture.carbon_diffusivity_m2_s,
            top_bulk_concentration_mol_m3=(
                fixture.carbon_top_bulk_concentration_mol_m3
            ),
            concentration_mol_m3=np.full(
                shape,
                fixture.carbon_concentration_mol_m3,
                dtype=np.float64,
            ),
        ),
        oxygen=SoluteField(
            name="oxygen",
            shape=shape,
            width_m=fixture.domain_width_m,
            height_m=fixture.domain_height_m,
            diffusivity_m2_s=fixture.oxygen_diffusivity_m2_s,
            top_bulk_concentration_mol_m3=(
                fixture.oxygen_top_bulk_concentration_mol_m3
            ),
            concentration_mol_m3=np.full(
                shape,
                fixture.oxygen_concentration_mol_m3,
                dtype=np.float64,
            ),
        ),
    )
    writer = SimulationOutputWriter(run_directory, metadata)
    shutil.copyfile(parameter_file, run_directory / "reference_parameters.toml")
    shutil.copyfile(biological_file, run_directory / "biological_parameters.toml")
    zero_balance = (
        MassBalanceEntry(
            quantity="carbon_field",
            unit="mol",
            initial_amount=solute_amount_mol(fields.carbon, fixture.depth_m),
            final_amount=solute_amount_mol(fields.carbon, fixture.depth_m),
            net_input_amount=(
                top_boundary_input_rate_mol_s(fields.carbon, fixture.depth_m) * 0.0
            ),
            absolute_tolerance=0.0,
            relative_tolerance=0.0,
        ),
        MassBalanceEntry(
            quantity="dry_biomass",
            unit="kg",
            initial_amount=0.0,
            final_amount=0.0,
            net_input_amount=0.0,
            absolute_tolerance=0.0,
            relative_tolerance=0.0,
        ),
        MassBalanceEntry(
            quantity="oxygen_field",
            unit="mol",
            initial_amount=solute_amount_mol(fields.oxygen, fixture.depth_m),
            final_amount=solute_amount_mol(fields.oxygen, fixture.depth_m),
            net_input_amount=(
                top_boundary_input_rate_mol_s(fields.oxygen, fixture.depth_m) * 0.0
            ),
            absolute_tolerance=0.0,
            relative_tolerance=0.0,
        ),
    )
    writer.write_snapshot(
        time_s=0.0,
        cells=(),
        solute_fields=fields,
        division_events=(),
        mass_balance_entries=zero_balance,
    )
    return writer.finalize()


def reproduce_reference(
    *,
    run_directory: Path,
    repository_root: Path | None,
) -> tuple[Path, ...]:
    """Recreate a recorded reference run and return byte-mismatched paths."""
    metadata_file = run_directory / "run_metadata.json"
    try:
        metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReferenceValidationError(
            f"unable to read run metadata {metadata_file}: {error}"
        ) from error
    parameter_label = metadata.get("parameter_file")
    recorded_seed = metadata.get("seed")
    recorded_sha256 = metadata.get("parameter_file_sha256")
    if not isinstance(parameter_label, str) or not parameter_label:
        raise ReferenceValidationError("run metadata has no valid parameter_file")
    if (
        not isinstance(recorded_seed, int)
        or isinstance(recorded_seed, bool)
        or recorded_seed < 0
    ):
        raise ReferenceValidationError("run metadata has no valid seed")
    parameter_file = _resolve_from_root(parameter_label, repository_root)
    try:
        current_sha256 = hashlib.sha256(parameter_file.read_bytes()).hexdigest()
    except OSError as error:
        raise ReferenceValidationError(
            f"unable to read recorded parameter file {parameter_file}: {error}"
        ) from error
    if current_sha256 != recorded_sha256:
        raise ReferenceValidationError(
            "recorded parameter file hash does not match the current file"
        )
    with tempfile.TemporaryDirectory(prefix="biomesh-reproduce-") as temporary:
        reproduced_directory = Path(temporary) / "run"
        run_reference(
            parameter_file=parameter_file,
            output_directory=reproduced_directory,
            seed=recorded_seed,
            repository_root=repository_root,
        )
        return _compare_directories(run_directory, reproduced_directory)


def default_output_directory(
    *, parameter_file: Path, repository_root: Path | None
) -> Path:
    """Resolve the configured default reference output directory."""
    configuration = load_reference_configuration(parameter_file)
    return _resolve_from_root(configuration.output_directory, repository_root)


def _compare_directories(first: Path, second: Path) -> tuple[Path, ...]:
    first_files = {
        path.relative_to(first): path for path in first.rglob("*") if path.is_file()
    }
    second_files = {
        path.relative_to(second): path for path in second.rglob("*") if path.is_file()
    }
    mismatches = set(first_files) ^ set(second_files)
    for relative_path in set(first_files) & set(second_files):
        if first_files[relative_path].read_bytes() != second_files[
            relative_path
        ].read_bytes():
            mismatches.add(relative_path)
    return tuple(sorted(mismatches))


def _resolve_from_root(path: str, repository_root: Path | None) -> Path:
    candidate = Path(path)
    if candidate.is_absolute() or repository_root is None:
        return candidate
    return repository_root / candidate


def _path_label(path: Path, repository_root: Path | None) -> str:
    if repository_root is not None:
        try:
            return path.resolve().relative_to(repository_root.resolve()).as_posix()
        except ValueError:
            pass
    return path.as_posix()
