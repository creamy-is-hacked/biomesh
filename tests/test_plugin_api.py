"""Focused P4-WP03 plugin compatibility, isolation, and application tests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from biomesh.__main__ import main
from biomesh.config import BiologicalParameter
from biomesh.example_species_kinetics import create_plugin
from biomesh.plugin_api import (
    ExportResult,
    FieldStepRequest,
    KineticsRequest,
    PluginError,
    PluginSetManifest,
    PluginTrustPolicy,
    builtin_plugin_trust_policy,
    example_plugin_manifest,
    load_plugins,
    plugin_metadata_sha256,
    plugin_selection_sha256,
    verify_plugins,
)


def _parameter(name: str, value: float, unit: str) -> BiologicalParameter:
    return BiologicalParameter(
        name=name,
        value=value,
        unit=unit,
        source="manufactured software-verification input",
        uncertainty="not a biological uncertainty estimate",
        notes="Explicit SI plugin-interface probe; not calibration evidence.",
        calibration_status="CALIBRATION_REQUIRED",
    )


def test_core_plugin_boundary_accepts_an_empty_manifest_without_loading() -> None:
    empty = PluginSetManifest(schema_version=1, plugins=[])
    report = verify_plugins(
        empty,
        PluginTrustPolicy(
            approved_selection_sha256=frozenset(),
        ),
    )

    assert report.zero_plugins_compatible is True
    assert report.plugins == []


def test_example_species_and_kinetics_are_deterministic_and_si_explicit() -> None:
    plugin = create_plugin()
    request = KineticsRequest(
        interface_version=1,
        carbon_concentration_mol_m3=2.0,
        oxygen_concentration_mol_m3=3.0,
        biological_parameters=[
            _parameter("maximum_specific_growth_rate", 0.5, "s^-1"),
            _parameter("carbon_half_saturation_constant", 1.0, "mol m^-3"),
            _parameter("oxygen_half_saturation_constant", 1.0, "mol m^-3"),
        ],
    )

    first = plugin.evaluate_kinetics(request)
    second = plugin.evaluate_kinetics(request)
    assert first == second
    assert first.specific_growth_rate_s == pytest.approx(0.25)
    assert first.unit == "s^-1"
    assert plugin.species_definition().calibration_status == "CALIBRATION_REQUIRED"
    with pytest.raises(PluginError, match="row-major shape"):
        FieldStepRequest(1, "carbon", "mol m^-3", (2, 2), (1.0,), 1.0)
    with pytest.raises(PluginError, match="safe relative paths"):
        ExportResult(1, (("../raw.json", "0" * 64, 1),))


def test_unresolved_kinetics_parameter_fails_before_plugin_execution() -> None:
    records = [
        _parameter("maximum_specific_growth_rate", 0.5, "s^-1"),
        _parameter("carbon_half_saturation_constant", 1.0, "mol m^-3"),
        BiologicalParameter(
            name="oxygen_half_saturation_constant",
            value="CALIBRATION_REQUIRED",
            unit="mol m^-3",
            source="CALIBRATION_REQUIRED",
            uncertainty="CALIBRATION_REQUIRED",
            notes="Unknown biological value remains explicit.",
            calibration_status="CALIBRATION_REQUIRED",
        ),
    ]
    with pytest.raises(ValueError, match="unresolved kinetics parameters"):
        KineticsRequest(
            interface_version=1,
            carbon_concentration_mol_m3=1.0,
            oxygen_concentration_mol_m3=1.0,
            biological_parameters=records,
        )


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


def test_incompatible_set_is_rejected_before_any_entry_point_load() -> None:
    compatible = example_plugin_manifest().plugins[0]
    incompatible_metadata = compatible.metadata.model_copy(
        update={"plugin_api_version": 2}
    )
    incompatible = compatible.model_copy(
        update={
            "metadata": incompatible_metadata,
            "metadata_sha256": plugin_metadata_sha256(incompatible_metadata),
        }
    )
    manifest = PluginSetManifest(schema_version=1, plugins=[incompatible])
    policy = PluginTrustPolicy(
        approved_selection_sha256=frozenset(
            {plugin_selection_sha256(incompatible)}
        )
    )
    entry_point = _ProbeEntryPoint(
        name=incompatible.entry_point_name,
        value=incompatible.entry_point_value,
        distribution_name=incompatible.distribution_name,
        distribution_version=incompatible.distribution_version,
    )

    with pytest.raises(PluginError, match="incompatible plugin API"):
        load_plugins(manifest, policy, available_entry_points=[entry_point])
    assert entry_point.loads == 0


def test_unreviewed_plugin_is_rejected_before_entry_point_load() -> None:
    manifest = example_plugin_manifest()
    entry_point = _ProbeEntryPoint(
        name=manifest.plugins[0].entry_point_name,
        value=manifest.plugins[0].entry_point_value,
        distribution_name=manifest.plugins[0].distribution_name,
        distribution_version=manifest.plugins[0].distribution_version,
    )
    with pytest.raises(PluginError, match="explicit review policy"):
        load_plugins(
            manifest,
            PluginTrustPolicy(
                approved_selection_sha256=frozenset(),
            ),
            available_entry_points=[entry_point],
        )
    assert entry_point.loads == 0


def test_reviewed_example_provenance_and_limitations_are_manifest_complete() -> None:
    report = verify_plugins(example_plugin_manifest(), builtin_plugin_trust_policy())
    assert len(report.plugins) == 1
    provenance = report.plugins[0]
    assert provenance.metadata_sha256 == plugin_metadata_sha256(provenance.metadata)
    assert provenance.selection_sha256 == plugin_selection_sha256(
        example_plugin_manifest().plugins[0]
    )
    assert provenance.metadata.components == ["kinetics", "species"]
    assert provenance.metadata.calibration_status == "CALIBRATION_REQUIRED"
    assert provenance.metadata.limitations
    assert provenance.self_check.passed is True


def test_plugins_verify_cli_publishes_deterministic_manifest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"

    assert main(["plugins", "verify", "--output", str(first)]) == 0
    first_stdout = json.loads(capsys.readouterr().out)
    assert main(["plugins", "verify", "--output", str(second)]) == 0
    second_stdout = json.loads(capsys.readouterr().out)

    assert first_stdout == second_stdout
    assert (first / "plugin_manifest.json").read_bytes() == (
        second / "plugin_manifest.json"
    ).read_bytes()
    assert json.loads((first / "plugin_manifest.json").read_text()) == first_stdout

    assert main(["plugins", "verify", "--output", str(first)]) == 2
    assert "already exists" in capsys.readouterr().err
