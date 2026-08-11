"""Focused P4-WP04 registry, provenance, compatibility, and CLI tests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest
from pydantic import ValidationError

from biomesh.__main__ import main
from biomesh.example_species_kinetics import create_plugin
from biomesh.model_registry import (
    RegistryError,
    import_registry,
    load_registry,
    preflight_launch,
    required_plugin_from_selection,
    verify_registry,
)
from biomesh.plugin_api import (
    PluginSetManifest,
    PluginTrustPolicy,
    builtin_plugin_trust_policy,
    example_plugin_manifest,
    plugin_set_sha256,
)
from biomesh.registry_catalog import builtin_registry
from biomesh.registry_types import (
    ModelEntry,
    ModelRecord,
    ParameterSetEntry,
    ParameterSetRecord,
    RegistryBundle,
    RegistryCitation,
    RegistryParameter,
    RequiredParameter,
    canonical_bytes,
    canonical_model_sha256,
    canonical_parameter_set_sha256,
)


def _citation(identifier: str) -> RegistryCitation:
    return RegistryCitation(
        citation_id=identifier,
        title="Manufactured software-verification record",
        source="BioMesh P4-WP04 focused test",
        locator=f"tests/test_model_registry.py#{identifier}",
        notes="Software contract evidence only; not biological evidence.",
    )


def _numeric_parameter(
    name: str,
    unit: str,
    value: float,
    *,
    provenance_kind: str = "ASSUMED",
    calibration_status: str = "CALIBRATION_REQUIRED",
) -> RegistryParameter:
    return RegistryParameter.model_validate(
        {
            "name": name,
            "value": value,
            "unit": unit,
            "provenance_kind": provenance_kind,
            "source": "manufactured software-verification input",
            "citations": [_citation(f"citation-{name}").model_dump(mode="json")],
            "uncertainty": "exact manufactured input; biological uncertainty unknown",
            "notes": "SI-labelled interface probe; not calibration evidence.",
            "calibration_status": calibration_status,
        }
    )


def _custom_registry(
    parameters: list[RegistryParameter],
    *,
    required_units: dict[str, str] | None = None,
    require_example_plugin: bool = False,
) -> RegistryBundle:
    units = required_units or {
        parameter.name: parameter.unit for parameter in parameters
    }
    required_plugins = []
    if require_example_plugin:
        required_plugins = [
            required_plugin_from_selection(example_plugin_manifest().plugins[0])
        ]
    model = ModelRecord(
        schema_version=1,
        model_id="org.biomesh.software-probe",
        model_version="1.0.0",
        display_name="Registry software probe",
        parameter_schema_id="software-probe",
        required_parameters=[
            RequiredParameter(name=name, unit=unit)
            for name, unit in sorted(units.items())
        ],
        plugin_api_version=1,
        required_plugins=required_plugins,
        source="P4-WP04 manufactured software test",
        compatibility_reference="tests/test_model_registry.py",
        calibration_status="CALIBRATION_REQUIRED",
        limitations=["Software-verification record only; no biological claim"],
    )
    parameter_set = ParameterSetRecord(
        schema_version=1,
        parameter_set_id="org.biomesh.software-probe.parameters",
        parameter_set_version="1.0.0",
        display_name="Registry software-probe parameters",
        model_id=model.model_id,
        model_version=model.model_version,
        parameter_schema_id=model.parameter_schema_id,
        audited=False,
        immutable=False,
        source="P4-WP04 manufactured software test",
        source_sha256="0" * 64,
        parameters=sorted(parameters, key=lambda parameter: parameter.name),
    )
    return RegistryBundle(
        schema_version=1,
        source="P4-WP04 focused test registry",
        models=[
            ModelEntry(record=model, record_sha256=canonical_model_sha256(model))
        ],
        parameter_sets=[
            ParameterSetEntry(
                record=parameter_set,
                record_sha256=canonical_parameter_set_sha256(parameter_set),
            )
        ],
    )


def test_builtin_registry_is_deterministic_si_explicit_and_audit_bound() -> None:
    first = builtin_registry(Path.cwd())
    second = builtin_registry(Path.cwd())
    report = verify_registry(first, Path.cwd())

    assert first == second
    assert canonical_bytes(first) == canonical_bytes(second)
    assert report.model_count == 5
    assert report.parameter_set_count == 5
    assert report.audited_parameter_set_count == 5
    assert report.compatibility_checks == 45
    assert report.unresolved_parameter_count == 45
    assert report.audited_presets_immutable
    assert report.citations_and_uncertainty_preserved
    assert all(entry.record.immutable for entry in first.parameter_sets)
    assert all(entry.record.audited for entry in first.parameter_sets)
    for entry in first.parameter_sets:
        assert all(parameter.unit for parameter in entry.record.parameters)
        assert all(
            parameter.provenance_kind == "CALIBRATION_REQUIRED"
            for parameter in entry.record.parameters
        )


def test_modified_or_relabelled_audited_parameter_set_fails_closed() -> None:
    original = builtin_registry(Path.cwd())
    accepted = original.parameter_sets[0].record
    changed_parameter = accepted.parameters[0].model_copy(
        update={"notes": "changed after accepted audit"}
    )
    changed_record = accepted.model_copy(
        update={
            "parameters": [changed_parameter, *accepted.parameters[1:]],
        }
    )
    changed_entry = ParameterSetEntry(
        record=changed_record,
        record_sha256=canonical_parameter_set_sha256(changed_record),
    )
    changed_bundle = original.model_copy(
        update={"parameter_sets": [changed_entry, *original.parameter_sets[1:]]}
    )

    with pytest.raises(RegistryError, match="not an immutable built-in identity"):
        verify_registry(changed_bundle, Path.cwd())

    relabelled = changed_record.model_copy(
        update={
            "parameter_set_id": "org.example.false-audited-preset",
        }
    )
    relabelled_entry = ParameterSetEntry(
        record=relabelled,
        record_sha256=canonical_parameter_set_sha256(relabelled),
    )
    relabelled_bundle = RegistryBundle(
        schema_version=1,
        source="untrusted",
        models=original.models,
        parameter_sets=sorted(
            [relabelled_entry, *original.parameter_sets[1:]],
            key=lambda entry: (
                entry.record.parameter_set_id,
                entry.record.parameter_set_version,
            ),
        ),
    )
    with pytest.raises(RegistryError, match="not an immutable built-in identity"):
        verify_registry(relabelled_bundle, Path.cwd())


def test_all_provenance_kinds_citations_and_uncertainty_survive_import_export(
    tmp_path: Path,
) -> None:
    parameters = [
        _numeric_parameter(
            "assumed_value", "1", 4.0, provenance_kind="ASSUMED"
        ),
        _numeric_parameter(
            "fitted_value",
            "s^-1",
            3.0,
            provenance_kind="FITTED",
        ),
        _numeric_parameter(
            "literature_value",
            "mol m^-3",
            2.0,
            provenance_kind="LITERATURE_DERIVED",
        ),
        _numeric_parameter(
            "measured_value",
            "m",
            1.0,
            provenance_kind="MEASURED",
        ),
        RegistryParameter(
            name="unknown_value",
            value="CALIBRATION_REQUIRED",
            unit="kg",
            provenance_kind="CALIBRATION_REQUIRED",
            source="CALIBRATION_REQUIRED",
            citations=[],
            uncertainty="CALIBRATION_REQUIRED",
            notes="No approved value; remains explicit.",
            calibration_status="CALIBRATION_REQUIRED",
        ),
    ]
    bundle = _custom_registry(parameters)
    source = tmp_path / "source.json"
    source.write_bytes(canonical_bytes(bundle))
    imported = tmp_path / "imported"

    report = import_registry(source, imported, Path.cwd())
    reloaded = load_registry(imported, Path.cwd())

    assert reloaded == bundle
    assert (imported / "registry.json").read_bytes() == source.read_bytes()
    assert report.citations_and_uncertainty_preserved
    assert {
        parameter.provenance_kind
        for parameter in reloaded.parameter_sets[0].record.parameters
    } == {
        "MEASURED",
        "LITERATURE_DERIVED",
        "FITTED",
        "ASSUMED",
        "CALIBRATION_REQUIRED",
    }
    for expected, actual in zip(
        bundle.parameter_sets[0].record.parameters,
        reloaded.parameter_sets[0].record.parameters,
        strict=True,
    ):
        assert actual.citations == expected.citations
        assert actual.uncertainty == expected.uncertainty


def test_numeric_registry_values_require_explicit_citation_and_classification() -> None:
    payload = _numeric_parameter("probe", "1", 1.0).model_dump(mode="json")
    payload["citations"] = []
    with pytest.raises(ValidationError, match="at least one citation"):
        RegistryParameter.model_validate(payload)

    payload["provenance_kind"] = "CALIBRATION_REQUIRED"
    with pytest.raises(ValidationError, match="non-placeholder provenance_kind"):
        RegistryParameter.model_validate(payload)


@dataclass
class _ProbeEntryPoint:
    name: str
    value: str
    distribution_name: str
    distribution_version: str
    loads: int = 0

    def load(self) -> object:
        self.loads += 1
        return create_plugin


def test_unit_mismatch_fails_before_reviewed_plugin_code_loads() -> None:
    parameter = _numeric_parameter("growth_rate", "s^-1", 1.0)
    bundle = _custom_registry(
        [parameter],
        required_units={"growth_rate": "mol m^-3"},
        require_example_plugin=True,
    )
    selection = example_plugin_manifest().plugins[0]
    entry_point = _ProbeEntryPoint(
        name=selection.entry_point_name,
        value=selection.entry_point_value,
        distribution_name=selection.distribution_name,
        distribution_version=selection.distribution_version,
    )

    with pytest.raises(RegistryError, match="parameter unit mismatch"):
        preflight_launch(
            bundle,
            repository_root=Path.cwd(),
            model_id="org.biomesh.software-probe",
            model_version="1.0.0",
            parameter_set_id="org.biomesh.software-probe.parameters",
            parameter_set_version="1.0.0",
            plugin_manifest=example_plugin_manifest(),
            trust_policy=builtin_plugin_trust_policy(),
            available_entry_points=[entry_point],
        )
    assert entry_point.loads == 0


def test_preflight_requires_exact_plugins_and_returns_traceable_hashes() -> None:
    parameters = [
        _numeric_parameter("carbon_half_saturation_constant", "mol m^-3", 1.0),
        _numeric_parameter("maximum_specific_growth_rate", "s^-1", 0.5),
        _numeric_parameter("oxygen_half_saturation_constant", "mol m^-3", 1.0),
    ]
    bundle = _custom_registry(parameters, require_example_plugin=True)

    with pytest.raises(RegistryError, match="exactly match"):
        preflight_launch(
            bundle,
            repository_root=Path.cwd(),
            model_id="org.biomesh.software-probe",
            model_version="1.0.0",
            parameter_set_id="org.biomesh.software-probe.parameters",
            parameter_set_version="1.0.0",
            plugin_manifest=PluginSetManifest(schema_version=1, plugins=[]),
            trust_policy=PluginTrustPolicy(approved_selection_sha256=frozenset()),
        )

    report = preflight_launch(
        bundle,
        repository_root=Path.cwd(),
        model_id="org.biomesh.software-probe",
        model_version="1.0.0",
        parameter_set_id="org.biomesh.software-probe.parameters",
        parameter_set_version="1.0.0",
        plugin_manifest=example_plugin_manifest(),
        trust_policy=builtin_plugin_trust_policy(),
    )
    assert report.passed
    assert report.parameter_count == 3
    assert len(report.plugin_selection_sha256) == 1
    assert report.plugin_set_sha256 == plugin_set_sha256(
        example_plugin_manifest()
    )
    assert report.model_record_sha256 == bundle.models[0].record_sha256
    assert (
        report.parameter_set_record_sha256
        == bundle.parameter_sets[0].record_sha256
    )


def test_unresolved_value_blocks_launch_without_erasing_calibration_status() -> None:
    unknown = RegistryParameter(
        name="unknown",
        value="CALIBRATION_REQUIRED",
        unit="1",
        provenance_kind="CALIBRATION_REQUIRED",
        source="CALIBRATION_REQUIRED",
        citations=[],
        uncertainty="CALIBRATION_REQUIRED",
        notes="Unknown remains explicit.",
        calibration_status="CALIBRATION_REQUIRED",
    )
    bundle = _custom_registry([unknown])
    with pytest.raises(RegistryError, match="launch blocked"):
        preflight_launch(
            bundle,
            repository_root=Path.cwd(),
            model_id="org.biomesh.software-probe",
            model_version="1.0.0",
            parameter_set_id="org.biomesh.software-probe.parameters",
            parameter_set_version="1.0.0",
            plugin_manifest=PluginSetManifest(schema_version=1, plugins=[]),
            trust_policy=PluginTrustPolicy(approved_selection_sha256=frozenset()),
        )


def test_registry_cli_verify_export_import_and_preflight_paths(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["registry", "verify"]) == 0
    verified = json.loads(capsys.readouterr().out)
    assert verified["audited_presets_immutable"] is True
    assert verified["unresolved_parameter_count"] == 45

    exported = tmp_path / "exported"
    imported = tmp_path / "imported"
    assert main(["registry", "export", "--output", str(exported)]) == 0
    export_report = json.loads(capsys.readouterr().out)
    assert main(
        [
            "registry",
            "import",
            str(exported),
            "--output",
            str(imported),
        ]
    ) == 0
    import_report = json.loads(capsys.readouterr().out)
    assert export_report == import_report
    assert (exported / "registry.json").read_bytes() == (
        imported / "registry.json"
    ).read_bytes()

    parameters = [
        _numeric_parameter("carbon_half_saturation_constant", "mol m^-3", 1.0),
        _numeric_parameter("maximum_specific_growth_rate", "s^-1", 0.5),
        _numeric_parameter("oxygen_half_saturation_constant", "mol m^-3", 1.0),
    ]
    custom_path = tmp_path / "custom.json"
    custom_path.write_bytes(
        canonical_bytes(_custom_registry(parameters, require_example_plugin=True))
    )
    assert main(
        [
            "registry",
            "preflight",
            "--registry",
            str(custom_path),
            "--model-id",
            "org.biomesh.software-probe",
            "--model-version",
            "1.0.0",
            "--parameter-set-id",
            "org.biomesh.software-probe.parameters",
            "--parameter-set-version",
            "1.0.0",
            "--plugins",
            "example",
        ]
    ) == 0
    preflight = json.loads(capsys.readouterr().out)
    assert preflight["passed"] is True
    assert preflight["parameter_count"] == 3

    assert main(["registry", "export", "--output", str(exported)]) == 2
    assert "already exists" in capsys.readouterr().err

    dangling = tmp_path / "dangling-output"
    dangling.symlink_to(tmp_path / "absent-target", target_is_directory=True)
    assert main(["registry", "export", "--output", str(dangling)]) == 2
    assert "already exists" in capsys.readouterr().err
    assert not (tmp_path / "absent-target").exists()
