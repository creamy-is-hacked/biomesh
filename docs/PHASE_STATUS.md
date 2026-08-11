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
| P3-WP04 | Experiment editor | COMPLETE |
| P3-WP05 | Controls, checkpoints, and inspection | COMPLETE |
| P3-WP06 | Analytics and export | COMPLETE |
| P3A | Phase 3 Audit | COMPLETE |

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

P3-WP04 validation evidence:

- `biomesh.gui.experiment_editor.ExperimentEditor` generates one form from
  each of the five existing frozen biological-parameter schemas. Every record
  displays value, SI unit, source, uncertainty, notes, calibration status, and
  explicit field or record validation errors; names and required units remain
  read-only.
- Mutable draft text is structurally separate from immutable validated
  configurations. All five schemas save atomically to TOML and reload with
  equal Pydantic semantics. Invalid drafts cannot save or become run-eligible,
  and schema-valid unresolved provenance remains explicitly
  `CALIBRATION_REQUIRED` and run-ineligible.
- Repository templates create unsaved editable copies. P2A-accepted presets
  are SHA-256-bound to implementation revision
  `6adb5def6f094762cb79ba3a2eddeede6007a2f5`, open read-only, and cannot be
  overwritten even from an editable clone. Twelve focused tests, including the
  offscreen editor path, and the offscreen application smoke path passed. The
  complete Python 3.14.4 gate passed 174 tests, Ruff, strict mypy,
  `git diff --check`, and module help.

P3-WP05 validation evidence:

- `biomesh.gui.simulation_worker.SimulationWorker` exclusively owns the frozen
  public `ApplicationService` on one background thread. Its ordered command
  boundary supports continuous run, pause, deterministic one-boundary step,
  stop through public close, finite positive speed targets, hash-verified
  checkpoint/resume, stale-safe public inspection, and error propagation.
- Desktop selectors cover exactly the 15 existing P2 fixture/condition pairs
  and fixed seeds 101, 202, and 303. Invalid or unresolved editor state cannot
  enable run or checkpoint resume. Editor documents are never placed in
  `RunRequest`, and no configuration-to-engine bridge or scientific change is
  claimed.
- Cell clicks hit-test immutable snapshot capsules. The inspector matches the
  public `CellInspection` record for lineage identity/parent, strain, biomass,
  state, local solutes, quorum activation, and local EPS density. The frozen
  record has no per-cell EPS rate, which is reported as unavailable rather than
  inferred from private state.
- The focused application/GUI gate passed 18 tests. The complete Python 3.14.4
  gate passed 185 tests, Ruff, strict mypy, `git diff --check`, module help, and
  the offscreen GUI smoke path.

P3-WP06 validation evidence:

- `biomesh.gui.analytics.AnalyticsPanel` plots immutable public snapshot values
  for population, total dry biomass, stored producer cell frequency, EPS,
  continuous quorum-active fraction, thickness, roughness, and separate carbon
  and oxygen penetration depths. Missing metrics/units fail explicitly and no
  scientific quantity or conversion is inferred.
- Completed-run export reuses the existing worker and public application export
  operation. It preserves canonical Parquet tables, NumPy fields, and run
  metadata bytes; adds exact long-form CSV/Parquet analytics and eight PNGs;
  and records deterministic artifact hashes plus seed, commit, fixture and
  biological-parameter hashes, `CALIBRATION_REQUIRED`, and software versions.
- Focused tests compare live/export values exactly with immutable metrics and
  corresponding canonical tables, verify export schemas and provenance,
  atomic failure/retry and cancellation cleanup, responsive worker execution,
  and propagated errors. The complete Python 3.14.4 gate passed 190 tests,
  Ruff, strict mypy, `git diff --check`, module help, and the clean offscreen GUI
  smoke path.

P3A pre-audit blocker remediation evidence:

- The first independent P3A attempt against
  `c2de0acfc1f025492069923f7594443b933e5acd` stopped because the mandatory
  `compare-frontends` and `verify-checkpoint` commands, reference selector, and
  `tests/gui tests/integration` collection paths were absent.
- The focused remediation adds an atomic byte-equivalence report over the
  manufactured producer fixture, a hash-bound one-boundary checkpoint and
  deterministic replay verifier, strict path/provenance validation, actionable
  tamper errors, and real GUI/integration audit collections. Audit seed 42 is
  non-biological and isolated to the P3 application verification adapter; the
  P2 campaign and desktop selectors remain fixed at 101, 202, and 303.
- Local Python 3.14.4 evidence passed 195 tests, Ruff, strict mypy,
  `git diff --check`, module help, offscreen GUI smoke, exact zero-mismatch
  frontend comparison, and zero-mismatch checkpoint replay. These were
  pre-audit remediation results; the independent result is recorded below.
- Display-usability prequalification reproduced a 1327×1173 implicit minimum,
  larger than the former 1100×720 default. The focused remediation contains
  rich dock content in local scroll areas, declares 1024×720 as the minimum
  supported display, and verifies both that exact composed size and keyboard
  traversal of primary controls. This changes presentation only.

P3A independent audit evidence (2026-08-10):

- Audit result: `PASS WITH RECORDED LIMITATIONS`; Phase 3 is accepted at pushed
  implementation commit `ed062935552c6a5df639c56474c7854cac91bd69`. The
  requested prerequisite `c2de0acfc1f025492069923f7594443b933e5acd` was
  verified as an ancestor before the clean-clone audit.
- A fresh Python 3.14.4 editable `.[dev]` install passed all mandatory commands
  in document order: 195 full-suite tests, 2 audit-collection tests, GUI smoke,
  zero-mismatch CLI/application equivalence, and zero-mismatch replay of all
  15 checkpoint files. Ruff, strict mypy, `git diff --check`, module help, P1
  validators/replay, and P2 fixture validation also passed.
- Real application probes verified solver-boundary run, pause, step, stop,
  checkpoint and resume; equal resumed/uninterrupted snapshots; immutable
  visualization and inspection accuracy; schema-generated forms; explicit
  validation and worker errors; analytics equality with stored metrics;
  atomic cancellation; canonical artifact preservation; and complete export
  provenance.
- The exact 1024×720 window remained usable with local dock scrolling and
  explicit keyboard traversal. A normal manufactured reference completed in
  0.323156294063665 s with 239 event-loop iterations and a maximum observed
  gap of 0.023815248045139015 s. Reference screenshots are retained under
  `validation/p3a/`.
- Fresh external Python 3.14.4 environments installed both wheel and sdist,
  launched GUI smoke, reproduced zero frontend mismatches, and replayed the
  packaged checkpoint without mismatch. Generated outputs remained ignored.
- No Critical or Major finding remains. BM-010 is closed by direct worker,
  cancellation, responsiveness, and actionable-error evidence. Biological
  inputs remain SI-labelled, provenance-complete, and
  `CALIBRATION_REQUIRED`; manufactured fixtures remain distinct from
  biological evidence.

## Dedicated repository remediation after P3-WP04

This is a controlled repository-hardening pass, not P3-WP05 and not a change
to the established P3-WP04 scientific or editor behavior.

- `BM-001` is fixed: SoluteField construction and candidate updates now reject
  every negative concentration, including values within the former numerical
  tolerance; finite-state validation and focused regressions remain explicit.
- `BM-002` is fixed: condition IDs are restricted to safe path components,
  campaign runs use a staged output root, and resolved output-tree checks reject
  escapes and symlinks before publication and during report validation.
- `BM-003` and `BM-005` are fixed: wheel/sdist builds carry the versioned
  experiment and parameter records as package resources; source and installed
  runtime roots are resolved explicitly; CI covers Python 3.14 versioned CLI
  and GUI entry points, `validate all`, GUI smoke, wheel/sdist installation,
  and external-working-directory execution.
- `BM-004` is fixed: simulation artifacts, campaign JSON, checkpoints, exports,
  and PNG reports use temporary sibling files/directories and atomic replace;
  failed publication leaves no final partial result and focused retry tests
  cover each affected surface.
- `BM-006` is fixed: RunMetadata requires exactly 64 lowercase hexadecimal
  characters for parameter-file SHA-256 provenance.
- `BM-007` is fixed through the documented accepted-audit Git workflow: the
  canonical P1A tag `v0.1.1-audit` identifies the accepted P1A commit.
- `BM-008` and `BM-009` are deferred. The current repository contracts do not
  establish the required behavior sufficiently to implement it without
  inventing policy or changing completed phase behavior.
- `BM-010` is closed by P3A. The independent clean-clone audit directly
  exercised worker ordering, stop, export cancellation, responsiveness, and
  propagated actionable errors without finding a Critical or Major defect.

Remediation verification evidence: Python 3.14.4, 183 tests, Ruff, strict
mypy, module and console CLI versions/help, `validate all`, offscreen GUI
smoke, `git diff --check`, wheel and sdist builds, and separate external-prefix
wheel/sdist resource/CLI/GUI smoke runs using the verified local runtime
dependencies. A network-isolated clean dependency installation was not
available in this environment; CI now performs that clean installation.

## P4 – Phase 4 – Research Platform

Source: `docs/08_PHASE_FOUR_RESEARCH_PLATFORM.md`.

| ID | Work package | Status |
| --- | --- | --- |
| P4-WP01 | Project and campaign model | COMPLETE |
| P4-WP02 | Comparison and reports | COMPLETE |
| P4-WP03 | Plugin API | COMPLETE |
| P4-WP04 | Model and parameter registry | INCOMPLETE |
| P4-WP05 | Local run queue | INCOMPLETE |
| P4-WP06 | Portable projects and packaging | INCOMPLETE |
| P4-WP07 | Experimental acceleration boundary | INCOMPLETE |
| P4A | Phase 4 Audit | INCOMPLETE |

P4-WP01 validation evidence:

- Versioned strict records cover projects, accepted-fixture experiments,
  campaigns, expanded runs, SHA-256/size-bound artifacts, retryable failures,
  and deterministic audit transitions. Explicit and arithmetic seed policies
  expand to one stable seed per replicate, while SI/provenance-complete sweep
  points must exactly match accepted P2 fixture conditions.
- Project creation and state replacement are atomic. A process lock serializes
  campaign mutation; interrupted runs become explicit retryable failures, and
  a crash after artifact publication recovers only a hash-verified completion
  receipt. Completed runs are skipped by resume/retry and artifact drift fails
  closed.
- The `project create` and `campaign status`, `resume`, and `retry` CLI paths
  passed using the real P3 `ApplicationService`. A controlled fixture-drift
  failure remained visible and retried successfully after restoration. The
  Python 3.14.4 full gate passed module help, Ruff, strict mypy,
  `git diff --check`, and 204 tests. No P4-WP02 or later behavior was added.

P4-WP02 validation evidence:

- The read-only report service consumes only hash-verified P4-WP01 completed
  runs. Sixteen declared scalar metrics retain their existing SI units and
  trace every replicate value to the raw artifact path, SHA-256, byte size,
  Parquet row and column, run ID, seed, and replicate index. Project state and
  raw artifacts are unchanged by reporting.
- Condition distributions expose every replicate plus mean, median, range,
  sample variance, standard deviation, and two-sided 95% Student-t intervals.
  Pairwise condition data exposes the unit-aware difference in means, Hedges g
  where defined, and a Welch Student-t interval. These are descriptive report
  data only; no significance decision, scientific conclusion, calibration, or
  GUI inference is generated.
- Every planned run remains in report coverage with its completed, pending,
  running, or failed status and explicit failure record. Per-summary missing
  run IDs are retained, and all one-observation summaries/comparisons are
  labelled `SINGLE_SEED_ONLY` with unavailable uncertainty rather than a
  manufactured estimate.
- The real `campaign report` application path used four P3-backed runs and
  produced 192 traced observations, 96 condition summaries, and 48 pairwise
  comparisons. A second report was byte-identical; all five data files matched
  the report manifest, and atomic failure cleanup passed. The Python 3.14.4
  full gate passed module help, Ruff, strict mypy, `git diff --check`, and 208
  tests. No P4-WP03 or later behavior was added.

P4-WP03 validation evidence:

- Version 1 immutable component contracts cover species, kinetics, fields,
  metrics, and exporters. Plugin metadata records exact ID/version/API,
  component kinds, source, `CALIBRATION_REQUIRED` status, limitations, and a
  canonical SHA-256. Kinetics execution requires SI-explicit state plus
  complete biological-parameter provenance and rejects unresolved values.
- Controlled loading validates the complete manifest and explicit code-owned
  trust policy before importing any selected entry point. Exact API version,
  metadata hash, distribution/version, and entry-point identity fail closed;
  focused probes confirmed incompatible and unreviewed sets load no code.
  Runtime metadata and every declared component interface must equal the
  reviewed declaration.
- The accepted engine and campaign runner remain the zero-plugin core path.
  The packaged example exposes an uncalibrated non-taxonomic species and the
  existing dual-substrate rate equation using only caller-owned SI/provenance
  inputs; it adds no biological constant or accepted-engine behavior.
- `plugins verify` passed both stdout and atomic-output application paths. Two
  published manifests were byte-identical and retained plugin distribution,
  entry-point, review, selection/metadata hashes, limitations, calibration,
  and self-check provenance. A no-dependency wheel build/install exposed the
  declared entry point and passed the verification path from an external
  working directory.
  Python 3.14.4 passed module help, `validate all`, Ruff, strict mypy over 45
  source files, `git diff --check`, and 215 tests. No P4-WP04 or later behavior
  was added.

## Next Work Package

`P4-WP04 – Model and parameter registry`.

## Remaining Issues

- All biological values remain `CALIBRATION_REQUIRED`; the reference is a
  non-scientific software/replay fixture.
- The canonical P1A tag `v0.1.1-audit` is present at the accepted P1A commit;
  P2A does not retroactively change that historical audit.
- P3A accepted Phase 3. P4-WP01 through P4-WP03 add the local synchronous
  project/campaign model, presentation-neutral comparison/report data, and a
  separately verified plugin API. The accepted engine/campaign path still
  uses zero plugins. The desktop has no report/plugin UI, persistent queue,
  model registry, portable archive, acceleration, or calibration behavior.
