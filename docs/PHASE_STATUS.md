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
| P2A | Phase 2 Audit | COMPLETE |

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
- P2A independently audited `d0c80c5` on 2026-08-03 and found the prior
  harness had no production P2 runner or CLI path. P2-WP06 remediation adds a
  deterministic documented update order, root-level required command fixtures,
  actual Parquet/NumPy artifacts, run metadata, raw manifests, aggregate
  statistics, accounting tables, observed-range descriptive rankings, and a
  report plot. The fixtures are SI-labelled manufactured software validation,
  not biological calibration. Local evidence: 144 tests, Ruff, mypy,
  `git diff --check`, module help, `validate all`, all six required command
  paths, and report passed on 2026-08-03. A clean clone created a fresh Python
  3.14 environment, installed `.[dev]`, passed `validate all`, ran the
  competition fixture and report, and passed all 144 tests. P2A must now rerun
  independently.
- P2A follow-up finding `P2A-002` identified that the six published fixtures
  still omitted root-level CLI coverage for the two inoculation patterns, both
  EPS-control modes, and the nutrient/oxygen sweep. The remediation now
  publishes 11 strict fixtures covering all 15 executable conditions exactly
  once, each at fixed seeds 101, 202, and 303, and keeps manufactured fixture
  configuration hashes separate from the five `CALIBRATION_REQUIRED`
  biological-parameter records.
- Pre-commit application-path evidence passed all 11 experiment/sweep commands
  and all 11 report paths twice with byte-identical directory trees: 45 runs,
  675 verified raw artifact hashes, 630 mean/sample-variance/Student-t rows,
  168 applicable observed-range ranking rows, and maximum absolute accounting
  residual `4.199134257027165e-30`. Strict report validation and focused tests
  reject missing Parquet and malformed NumPy artifacts. The full required gate
  passed with 145 tests. P2A must rerun independently; no audit, P3, mutation,
  evolution, or biological-calibration claim is included.
- `P2A-003` documentation remediation updates README status and the complete
  11-fixture CLI surface, and extends `docs/ARCHITECTURE.md` through P2-WP06
  with waste/shear, campaign update order, artifacts, statistics, reports, and
  calibration boundaries. Module help, `validate all`, Ruff, mypy,
  `git diff --check`, and all 145 tests passed. At that remediation checkpoint,
  P2A remained `INCOMPLETE` pending the fresh audit recorded below.

P2A independent audit evidence (2026-08-08):

- Audit result: `PASS WITH RECORDED LIMITATIONS`; Phase 2 is accepted at
  implementation commit `6adb5def6f094762cb79ba3a2eddeede6007a2f5`.
- A fresh clone of `origin/phase-2-colony-system` and fresh Python 3.14.4
  `.[dev]` environment passed module help, Ruff, strict mypy,
  `git diff --check`, 145 tests, all P1 validators and zero-mismatch reference
  replay, and `validate all`. A focused P2 rerun passed 64 tests.
- All 11 published fixture and report paths ran twice in separate trees. The
  764 files replayed byte-identically across 45 fixed-seed runs. Independent
  inspection verified 675 raw SHA-256/size records, 495 Parquet files, 135
  NumPy archives, 630 recomputed mean/sample-variance/Student-t rows, and 168
  applicable observed-range ranking rows. Maximum absolute accounting residual
  was `4.199134257027165e-30` and maximum relative accounting error was
  `2.9056583757232816e-16`.
- Gates A-H passed. All 45 biological records and 10 unresolved campaign
  overrides remain SI-labelled, provenance-complete, and
  `CALIBRATION_REQUIRED`; manufactured executable overrides remain separately
  labelled and are not calibration evidence. Recorded limitations are the
  uncalibrated parameters, immobile-field EPS abstraction, simplified non-CFD
  shear, and descriptive rather than global sensitivity analysis.

## P3 – Phase 3 – Desktop GUI

Source: `docs/06_PHASE_THREE_DESKTOP_GUI.md`.

| ID | Work package | Status |
| --- | --- | --- |
| P3-WP01 | Stable application API | COMPLETE |
| P3-WP02 | Desktop shell | COMPLETE |
| P3-WP03 | Simulation viewer | COMPLETE |
| P3-WP04 | Experiment editor | INCOMPLETE |
| P3-WP05 | Controls, checkpoints, and inspection | INCOMPLETE |
| P3-WP06 | Analytics and export | INCOMPLETE |
| P3A | Phase 3 Audit | INCOMPLETE |

P3-WP01 validation evidence:

- `biomesh.application.ApplicationService` exposes typed run, pause, one-boundary
  step, hash-verified checkpoint/resume, immutable snapshot/inspection, and
  completed canonical-artifact export operations over the existing P2 fixture
  path. Mutable solver state remains private; no GUI or worker dependency was
  added.
- Pause/step/resume and checkpoint reconstruction produce equal final snapshots.
  Snapshot arrays are immutable byte-backed read-only views. The CLI/API
  equivalence test compares every raw artifact byte-for-byte for the same
  fixture condition and seed.
- Focused application/P2 validation passed 9 tests. The complete Python 3.14.4
  gate passed 151 tests, Ruff, strict mypy, `git diff --check`, and module help.

P3-WP02 validation evidence:

- `biomesh.gui.main_window.MainWindow` provides File/View/Help menus, two
  dockable panels,
  a read-only persistent error console, a status bar, and an intentionally
  empty central placeholder. Project entries are opaque readable-file
  references only; no project schema, scientific load, viewer, editor,
  controls, worker, analytics, or export behavior is present.
- Versioned UI preferences contain only recent paths and Qt window geometry/
  dock state. They are strictly validated, atomically written to a separate
  XDG configuration file, and never read or write biological parameters.
- Six focused headless tests cover startup, shell chrome, recent projects,
  missing/invalid file errors, corrupt preferences, round-trip persistence,
  and unchanged biological-parameter hashes. The complete Python 3.14.4 gate
  passed 161 tests, Ruff, strict mypy, `git diff --check`, module help, and the
  offscreen `python -m biomesh.gui --smoke-test` application path.

P3-WP03 validation evidence:

- `biomesh.gui.viewer.SimulationViewer` renders immutable snapshot capsules in
  SI coordinates and the five immutable scalar arrays in explicit grid-index
  coordinates through PyQtGraph. Separate canvases avoid inventing a physical
  field extent absent from the frozen P3-WP01 snapshot contract.
- Mouse navigation and explicit zoom, pan, and fit operations are available.
  Each layer has visibility, opacity, and a unit/range legend. A newest-frame
  limiter bounds presentation rate; focused work counters verify that hidden
  cells skip path rebuilds and hidden fields skip image uploads.
- The focused offscreen shell/viewer gate passed 7 tests. Its real P2
  application-path probe rendered the reference-scale final snapshot in under
  one second and matched all five displayed fields to canonical exported NumPy
  arrays at `rtol=1e-12`, `atol=1e-15`. The complete Python 3.14.4 gate passed
  162 tests, Ruff, strict mypy, `git diff --check`, module help, and the
  offscreen GUI smoke path.

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

`P3-WP04 – Experiment editor`.

## Remaining Issues

- All biological values remain `CALIBRATION_REQUIRED`; the reference is a
  non-scientific software/replay fixture.
- The canonical P1A tag `v0.1.1-audit` remains absent and must only be created
  through its approved accepted-audit workflow; P2A does not retroactively
  create it.
- P3-WP03 is complete. P3-WP04 is the first incomplete package; the desktop has
  no experiment editor, run controls, worker, inspection, analytics, additional
  export, or later P3 behavior.
