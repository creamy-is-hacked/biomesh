"""Declared SI scalar sources available to P4-WP02 reports."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReportMetric:
    """One exact scalar column already stored by the accepted engine."""

    name: str
    title: str
    unit: str
    artifact_path: str
    column: str


REPORT_METRICS: tuple[ReportMetric, ...] = (
    ReportMetric(
        "total_dry_biomass_kg",
        "Total dry biomass",
        "kg",
        "raw/summary.parquet",
        "total_dry_biomass_kg",
    ),
    ReportMetric("cell_count", "Cell count", "1", "raw/summary.parquet", "cell_count"),
    ReportMetric(
        "division_event_count",
        "Division event count",
        "1",
        "raw/summary.parquet",
        "division_event_count",
    ),
    ReportMetric(
        "biofilm_height_m",
        "Biofilm height",
        "m",
        "raw/summary.parquet",
        "biofilm_height_m",
    ),
    ReportMetric(
        "biofilm_roughness_m",
        "Biofilm roughness",
        "m",
        "raw/summary.parquet",
        "biofilm_roughness_m",
    ),
    ReportMetric(
        "total_eps_kg",
        "Total EPS",
        "kg",
        "raw/eps_summary.parquet",
        "total_eps_kg",
    ),
    ReportMetric(
        "producer_cell_frequency",
        "Producer cell frequency",
        "1",
        "raw/competition_summary.parquet",
        "producer_cell_frequency",
    ),
    ReportMetric(
        "producer_biomass_frequency",
        "Producer biomass frequency",
        "1",
        "raw/competition_summary.parquet",
        "producer_biomass_frequency",
    ),
    ReportMetric(
        "nearest_neighbor_segregation_fraction",
        "Nearest-neighbor segregation fraction",
        "1",
        "raw/competition_summary.parquet",
        "nearest_neighbor_segregation_fraction",
    ),
    ReportMetric(
        "active_biomass_kg",
        "Active biomass",
        "kg",
        "raw/physiology_summary.parquet",
        "active_biomass_kg",
    ),
    ReportMetric(
        "slow_biomass_kg",
        "Slow biomass",
        "kg",
        "raw/physiology_summary.parquet",
        "slow_biomass_kg",
    ),
    ReportMetric(
        "dormant_biomass_kg",
        "Dormant biomass",
        "kg",
        "raw/physiology_summary.parquet",
        "dormant_biomass_kg",
    ),
    ReportMetric(
        "dead_biomass_kg",
        "Dead biomass",
        "kg",
        "raw/physiology_summary.parquet",
        "dead_biomass_kg",
    ),
    ReportMetric(
        "detached_biomass_kg",
        "Detached biomass",
        "kg",
        "raw/physiology_summary.parquet",
        "detached_biomass_kg",
    ),
    ReportMetric(
        "surface_parallel_shear_stress_pa",
        "Surface-parallel shear stress",
        "Pa",
        "raw/shear_summary.parquet",
        "surface_parallel_shear_stress_pa",
    ),
    ReportMetric(
        "detachment_rate_s",
        "Detachment rate",
        "s^-1",
        "raw/shear_summary.parquet",
        "detachment_rate_s",
    ),
)
