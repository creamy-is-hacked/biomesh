# BioMesh Phase Status

This is the authoritative progress tracker for all BioMesh work packages and
audits. Execute the first `INCOMPLETE` work package in phase order; do not
start an audit until every work package in its phase is complete.

Status values: `COMPLETE`, `INCOMPLETE`, or `BLOCKED`.

## M0 – Repository Bootstrap

All M0 implementation items are complete. The recorded `M0: Repository
Bootstrap` commit (`95e9ab5`) and `v0.0.0-m0` tag satisfy the M0 handoff gate.

| ID | Work package | Status |
| --- | --- | --- |
| M0-WP01 | Package metadata and typed non-simulation CLI shell | COMPLETE |
| M0-WP02 | Package version and module-help tests | COMPLETE |
| M0-WP03 | Linux CI for install, lint, typing, and tests on Python 3.14 | COMPLETE |
| M0-WP04 | Repository rules and scientific provenance documentation contracts | COMPLETE |
| M0-WP05 | Future-use parameter, experiment, validation, and output directories | COMPLETE |
| M0-WP06 | Dependency and required-check validation | COMPLETE |

M0 validation evidence:

- Python 3.14.4; fresh virtual environment and editable development install passed.
- `python -m biomesh --help`, `ruff check .`, `mypy src`, and `pytest -q`
  passed (2 tests).

## P1 – Phase 1 – Core Model

Source: `docs/01_PHASE_ONE_CORE_MODEL.md`.

| ID | Work package | Status |
| --- | --- | --- |
| P1-WP01 | Repository and configuration | COMPLETE |
| P1-WP02 | Solute fields | COMPLETE |
| P1-WP03 | Cell model | COMPLETE |
| P1-WP04 | Metabolism | COMPLETE |
| P1-WP05 | Mechanics and attachment | COMPLETE |
| P1-WP06 | Outputs | COMPLETE |
| P1-WP07 | Simulation Orchestration & Reproducibility | COMPLETE |
| P1A | Phase 1 Audit | COMPLETE |

P1 work-package evidence before audit:

- WP01: editable Python 3.14 installation, strict TOML/Pydantic provenance, CLI
  help, lint, typing, and 6 tests passed.
- WP02: manufactured diffusion, refinement, nonnegativity, stability rejection,
  no-flux behavior, and conservative cell exchange passed (13 tests total).
- WP03: SI capsule state, biomass-conserving seeded division, lineage, and
  daughter geometry passed (21 tests total).
- WP04: dual-substrate Monod limits, analytical growth, yield/death accounting,
  closed-system coupling, replay, and atomic failure passed (39 tests total).
- WP05: periodic capsule relaxation, bottom attachment, boundary enforcement,
  convergence errors, and overlap metrics passed (56 tests total).
- WP06: deterministic Parquet/NumPy output, provenance, geometry summaries,
  mass-balance records, immutability, and byte replay passed (59 tests total).

P1A independent audit evidence (2026-08-02):

- Audit result: `PASS WITH RECORDED LIMITATIONS`; Phase 1 is accepted.
- Fresh Python 3.14.4 editable `.[dev]` install passed. `pytest -q` passed
  (71 tests); Ruff, mypy, `git diff --check`, and module help passed.
- All five required CLI paths passed. Diffusion error was
  `6.655336877159357e-07` versus `2e-3`; refinement ratio was
  `0.23887522547268525`; growth error was `0.0 kg`; reference replay had zero
  byte mismatches.
- Full-pipeline mass balance had maximum residual `3.8033812210791496e-16`,
  relative error `7.52623300477429e-17`, and overlap `0.0 m`. An independent
  25-step probe closed within `5.342948306008566e-16`.
- Independent periodic geometry, boundary transfer, time refinement, public
  typing, module-boundary, documentation, and work-package acceptance reviews
  found no Critical or Major defect.

P1-WP07 validation evidence:

- Deterministic orchestration now composes metabolism, solutes, seeded
  division, mechanics, boundary-aware accounting, and output. Run metadata
  records commit, package/dependency versions, parameter file/hash, seed,
  platform, and Python version.
- The `CALIBRATION_REQUIRED` reference replay produced zero byte mismatches.
- All required checks and five CLI paths passed (71 tests). Mass-balance maximum
  residual was `3.8033812210791496e-16`, relative error `7.52623300477429e-17`,
  and overlap `0.0 m`.

## P2 – Phase 2 – Colony System

Source: `docs/03_PHASE_TWO_COLONY_SYSTEM.md`.

| ID | Work package | Status |
| --- | --- | --- |
| P2-WP01 | Quorum signal | COMPLETE |
| P2-WP02 | EPS model | COMPLETE |
| P2-WP03 | Competition | COMPLETE |
| P2-WP04 | Physiological states | COMPLETE |
| P2-WP05 | Waste and shear | COMPLETE |
| P2-WP06 | Experiments | COMPLETE |
| P2A | Phase 2 Audit | INCOMPLETE |

P2-WP01 validation evidence:

- Quorum production supports configurable basal and Hill-scaled induced
  whole-cell rates; signal transport reuses the audited finite-volume geometry
  with first-order degradation and a combined stability gate.
- Manufactured diffusion-decay, analytical Hill response, equal-count geometry,
  degradation, signal accounting, validation-failure, history, output, and
  byte-replay tests passed.
- All seven quorum biological parameters remain configurable and
  `CALIBRATION_REQUIRED`. The full required gate passed: 87 tests, Ruff, mypy,
  `git diff --check`, and module help.

P2-WP02 validation evidence:

- Quorum-scaled EPS allocation splits gross anabolic production between
  retained producer biomass and an immobile local EPS density field while
  charging carbon and oxygen for the full biomass-equivalent production.
- Controlled production, accumulation, isolated growth-cost, substrate-yield,
  biomass-equivalent conservation, monotone cohesion/attachment, validation,
  optional output, and byte-replay tests passed.
- All three EPS biological parameters remain configurable and
  `CALIBRATION_REQUIRED`. The full required gate passed: 102
  tests, Ruff, mypy, `git diff --check`, and module help.

P2-WP03 validation evidence:

- Producer and nonproducer roles share the existing simultaneous carbon and
  oxygen update; only producers pay quorum-scaled EPS allocation, while both
  roles receive the same local matrix modifiers.
- Neutral, well-mixed cost, resource competition, quorum/EPS interaction,
  conservation, frequency, segregation, lineage, local-fitness, input-order,
  fixed-seed, validation-failure, optional-output, and byte-replay tests passed.
- P2-WP03 adds no numeric biological parameter. The full required gate passed:
  112 tests, Ruff, mypy, `git diff --check`, and module help.

P2-WP04 validation evidence:

- A centralized explicit state model implements active, slow, dormant, dead,
  and detached states using configurable carbon/oxygen thresholds, continuous
  delays, immutable exposure history, and deterministic recovery.
- Dormant activity is lower than active activity by explicit configuration and
  flows through metabolism, EPS, and competition. Dead biomass either persists
  or follows an explicit first-order recycled-biomass ledger; all state counts
  and retained biomass reconcile with the population.
- All 13 numeric biological parameters remain configurable and
  `CALIBRATION_REQUIRED`. The full required gate passed: 127 tests, Ruff, mypy,
  `git diff --check`, and module help.

P2-WP05 validation evidence:

- Waste transport reuses the audited finite-volume geometry with configurable
  whole-cell sources, optional physiological activity scaling, first-order
  removal, stability validation, top-boundary transfer, and a discrete molar
  accounting record.
- Simplified deterministic surface-parallel shear accumulates exposure and
  selects terminal detached-state IDs only under positive stress. The
  configured threshold is scaled by caller-declared attachment and existing
  local EPS attachment strength; population reconciliation remains owned by
  the P2-WP04 ledger.
- Controlled zero-shear, increasing-shear, EPS-resistance,
  attachment-resistance, waste accounting, validation-failure, output, and
  byte-replay tests passed. All seven new parameters remain configurable and
  `CALIBRATION_REQUIRED`. The full required gate passed: 138 tests, Ruff,
  mypy, `git diff --check`, and module help.

P2-WP06 validation evidence:

- A strict campaign schema covers producer and nonproducer monocultures, 50:50
  competition, two inoculation patterns, constitutive and quorum-controlled
  EPS, and two or more levels for every required quorum, nutrient/oxygen,
  EPS-cost, and shear sweep. Every condition has three fixed seeds in the
  repository's unresolved campaign definition.
- The harness records biological-parameter hashes and one immutable raw
  condition/seed manifest per run, validates the complete P2 scalar/map output
  contract, preserves raw output hashes, and reports per-time replicate mean,
  sample variance, Student's t confidence intervals, and descriptive rankings
  limited to observed between-condition mean ranges. It adds no coupled
  biological update order or global sensitivity model.
- Unknown sweep values remain configurable, SI-labelled, provenance-complete,
  and `CALIBRATION_REQUIRED`. Synthetic matrix, replay, statistics,
  preservation, and explicit-failure tests passed. The full required gate
  passed: 142 tests, Ruff, mypy, `git diff --check`, and module help.

## P3 – Phase 3 – Desktop GUI

Source: `docs/06_PHASE_THREE_DESKTOP_GUI.md`.

| ID | Work package | Status |
| --- | --- | --- |
| P3-WP01 | Stable application API | INCOMPLETE |
| P3-WP02 | Desktop shell | INCOMPLETE |
| P3-WP03 | Simulation viewer | INCOMPLETE |
| P3-WP04 | Experiment editor | INCOMPLETE |
| P3-WP05 | Controls, checkpoints, and inspection | INCOMPLETE |
| P3-WP06 | Analytics and export | INCOMPLETE |
| P3A | Phase 3 Audit | INCOMPLETE |

## P4 – Phase 4 – Research Platform

Source: `docs/08_PHASE_FOUR_RESEARCH_PLATFORM.md`.

| ID | Work package | Status |
| --- | --- | --- |
| P4-WP01 | Project and campaign model | INCOMPLETE |
| P4-WP02 | Comparison and reports | INCOMPLETE |
| P4-WP03 | Plugin API | INCOMPLETE |
| P4-WP04 | Model and parameter registry | INCOMPLETE |
| P4-WP05 | Local run queue | INCOMPLETE |
| P4-WP06 | Portable projects and packaging | INCOMPLETE |
| P4-WP07 | Experimental acceleration boundary | INCOMPLETE |
| P4A | Phase 4 Audit | INCOMPLETE |

## Next Work Package

`P2A – Phase 2 Audit`.

## Remaining Issues

- All biological values remain `CALIBRATION_REQUIRED`; the reference is a
  non-scientific software/replay fixture.
- P2A remains incomplete; Phase 2 is not accepted until that audit passes.
- The current `phase/2-colony-system` branch is noncanonical; align it with
  `phase-2-colony-system` before an accepted-phase handoff without rewriting
  history.
