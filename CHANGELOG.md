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
- P1-WP07 – Deterministic Phase 1 orchestration across metabolism, solute
  transport, seeded division, mechanics, global accounting, and outputs;
  executable diffusion, growth, mass-balance, run, and reproduce paths;
  environment-complete provenance; and a calibration-gated software reference.
- P2-WP01 – Deterministic quorum-signal production with optional positive
  feedback, finite-volume diffusion, first-order degradation, cell-local Hill
  sensing, immutable exposure/activation history, discrete signal accounting,
  and optional signal/history outputs. All seven biological inputs remain
  configurable and `CALIBRATION_REQUIRED`.
- P2-WP02 – Deterministic quorum-controlled EPS allocation and immobile local
  accumulation with explicit producer growth cost, biomass-equivalent and
  substrate accounting, monotone cohesion/attachment modifiers, optional EPS
  outputs, and three configurable `CALIBRATION_REQUIRED` parameters.
- P2-WP03 – Deterministic producer/nonproducer competition over shared carbon
  and oxygen, producer-only quorum-scaled EPS cost, shared local matrix benefit,
  frequency, segregation, lineage, and local-fitness tracking, plus canonical
  optional competition outputs. No new numeric biological parameter was added.
- P2-WP04 – Centralized active, slow, dormant, dead, and detached physiological
  states with explicit nutrient/oxygen exposure thresholds and delays,
  configurable metabolic activity, dead-biomass persistence or recycling,
  reconciled population ledgers, and deterministic optional outputs. All 13
  numeric biological inputs remain configurable and `CALIBRATION_REQUIRED`.
- P2-WP05 – Diffusing whole-cell waste production with configurable first-order
  removal and discrete molar accounting; deterministic uniform
  surface-parallel shear exposure whose detachment threshold scales with
  caller-declared attachment and existing local EPS attachment strength; and
  optional waste-map and detachment-rate outputs. All seven new inputs remain
  configurable and `CALIBRATION_REQUIRED`.
- P2-WP06 – A strict replicated-experiment harness covering monocultures,
  50:50 competition, inoculation patterns, EPS control modes, and quorum,
  resource, EPS-cost, and shear sweeps. It records condition/seed manifests,
  parameter and raw-artifact hashes, complete SI result metrics and maps, and
  deterministic replicate means, sample variances, confidence intervals, and
  descriptive rankings limited to the observed sweep-result ranges.

### Audit findings

- P2A – Independent audit of `d0c80c5` failed (`P2A-001`): the P2 production
  campaign runner and all documented experiment, sweep, and report CLI paths
  were absent. This P2-WP06 remediation adds the deterministic runner and the
  required command paths with manufactured SI software-validation fixtures;
  P2A must be rerun independently before any Phase 2 acceptance claim.

### Fixed

- P2-WP06 – Added the executable P2 update adapter, strict artifact checks,
  raw Parquet/NumPy run outputs, provenance manifests, replicate statistics,
  descriptive observed-range sensitivity rankings, and PNG reports. Verified
  locally with all required CLI paths, `ruff check .`, `mypy src`, and 144
  tests, then reproduced from a fresh Python 3.14 editable-install clone.
  Fixtures are manufactured software validation only, not calibration.

### Fixed

- P1A – Corrected physical bottom-to-grid indexing so cell exchange uses the
  same vertical convention as the diffusion boundaries and mechanics domain.
- P1A – Made coupled carbon/oxygen updates atomic when either solute step fails.
- P1A – Corrected periodic capsule contact search to consider neighboring
  segment images, preventing missed overlaps for long angled cells.
- P1A – Enforced known P1 SI units, physical numeric domains, a complete P1
  biological-parameter manifest, and provenance for cell radius.
- P1A – Reject output snapshots whose supplied mass-balance residual exceeds
  its declared tolerance.

### Audit

- P1A – Phase 1 Audit executed on 2026-08-02 with result `FAIL`. Component
  defects above were repaired and 66 tests pass, but Phase 1 is not accepted:
  it must be rerun after the subsequent P1-WP07 orchestration and reproducibility
  remediation. P2 remains blocked until that independent audit completes.
- P1A – Independent audit rerun completed on 2026-08-02 with result
  `PASS WITH RECORDED LIMITATIONS`. A fresh Python 3.14.4 environment, 71 tests,
  lint, strict typing, CLI help, diffusion, growth, boundary-aware mass balance,
  reference generation, and zero-mismatch reproduction all passed. Phase 1 is
  accepted; calibration and the user-owned Git handoff remain documented.
