# Changelog

All notable repository changes are documented here.

## Unreleased

### Added

- M0 – Repository Bootstrap package shell, development tooling, tests, CI
  workflow, and documentation contracts.
- Standards alignment: Python 3.14 compatibility policy, canonical phase
  names, branch names, commit prefixes, and version tags.
- P1-WP01 – Versioned TOML biological-parameter records with strict Pydantic
  validation, explicit `CALIBRATION_REQUIRED` handling, and a provenance-only
  P1 starter parameter file.
- P1-WP02 – Configurable carbon and oxygen finite-volume diffusion fields with
  explicit stability validation, prescribed transport boundaries, and
  conservative cell exchange mapping.
- P1-WP03 – Configurable, deterministic 2D capsule-cell state with dry
  biomass-driven elongation, lineage-preserving division, and explicit
  validation of geometry and inputs.
- P1-WP04 – Deterministic dual-substrate Monod metabolism with exact biomass
  ODE integration, explicit carbon and oxygen yields, maintenance/death loss
  accounting, conservative local solute coupling, and closed-system balance
  verification.
- P1-WP05 – Deterministic 2D capsule collision relaxation with periodic sides,
  solid-bottom enforcement, configurable initial surface attachment, explicit
  convergence failure, and a residual-overlap error metric.
- P1-WP06 – Deterministic, write-only exports of existing cell and solute
  state: SI-labelled Parquet snapshots and summaries, division and
  unit-aware mass-balance tables, compressed NumPy fields, and canonical run
  provenance metadata.
