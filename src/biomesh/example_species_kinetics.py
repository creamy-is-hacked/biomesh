"""Packaged P4-WP03 species/kinetics plugin example.

The example delegates to the accepted dual-substrate Monod equation and has
no embedded biological constants.  Every executable value is supplied through
SI-labelled provenance records by the caller.
"""

from __future__ import annotations

from biomesh.config import BiologicalParameter
from biomesh.plugin_api import (
    KineticsRequest,
    KineticsResult,
    PluginMetadata,
    PluginSelfCheck,
    SpeciesDefinition,
    example_plugin_metadata,
)


class ExampleSpeciesKineticsPlugin:
    """Minimal reviewed example preserving the accepted kinetics equation."""

    def metadata(self) -> PluginMetadata:
        return example_plugin_metadata()

    def species_definition(self) -> SpeciesDefinition:
        return SpeciesDefinition(
            interface_version=1,
            species_id="example-species",
            display_name="Uncalibrated example species",
            calibration_status="CALIBRATION_REQUIRED",
            notes="Software extension example only; no taxonomic or biological claim.",
        )

    def evaluate_kinetics(self, request: KineticsRequest) -> KineticsResult:
        values = {item.name: item.value for item in request.biological_parameters}
        maximum_rate = values["maximum_specific_growth_rate"]
        carbon_half_saturation = values["carbon_half_saturation_constant"]
        oxygen_half_saturation = values["oxygen_half_saturation_constant"]
        assert isinstance(maximum_rate, float)
        assert isinstance(carbon_half_saturation, float)
        assert isinstance(oxygen_half_saturation, float)
        carbon_limitation = request.carbon_concentration_mol_m3 / (
            carbon_half_saturation + request.carbon_concentration_mol_m3
        )
        oxygen_limitation = request.oxygen_concentration_mol_m3 / (
            oxygen_half_saturation + request.oxygen_concentration_mol_m3
        )
        rate = maximum_rate * carbon_limitation * oxygen_limitation
        return KineticsResult(
            interface_version=1,
            specific_growth_rate_s=rate,
            unit="s^-1",
        )

    def self_check(self) -> PluginSelfCheck:
        metadata = self.metadata()
        species = self.species_definition()
        request = _software_verification_request()
        first = self.evaluate_kinetics(request)
        second = self.evaluate_kinetics(request)
        if first != second or first.specific_growth_rate_s != 0.0:
            raise RuntimeError("example kinetics zero-state self-check failed")
        return PluginSelfCheck(
            schema_version=1,
            plugin_id=metadata.plugin_id,
            plugin_version=metadata.plugin_version,
            passed=True,
            details=(
                f"{species.species_id} exposes version 1 species and kinetics "
                "interfaces; the manufactured zero-state probe is deterministic"
            ),
        )


def create_plugin() -> ExampleSpeciesKineticsPlugin:
    """Create the stateless packaged example plugin."""
    return ExampleSpeciesKineticsPlugin()


def _software_verification_request() -> KineticsRequest:
    parameters = [
        (
            "maximum_specific_growth_rate",
            "s^-1",
        ),
        (
            "carbon_half_saturation_constant",
            "mol m^-3",
        ),
        (
            "oxygen_half_saturation_constant",
            "mol m^-3",
        ),
    ]
    return KineticsRequest(
        interface_version=1,
        carbon_concentration_mol_m3=0.0,
        oxygen_concentration_mol_m3=0.0,
        biological_parameters=[
            BiologicalParameter(
                name=name,
                value=1.0,
                unit=unit,
                source="manufactured P4-WP03 software-verification fixture",
                uncertainty="not a biological uncertainty estimate",
                notes="Zero-state interface probe only; not calibration evidence.",
                calibration_status="CALIBRATION_REQUIRED",
            )
            for name, unit in parameters
        ],
    )
