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
| P4-WP04 | Model and parameter registry | COMPLETE |
| P4-WP05 | Local run queue | COMPLETE |
| P4-WP06 | Portable projects and packaging | COMPLETE |
| P4-WP07 | Experimental acceleration boundary | COMPLETE |
| P4A | Phase 4 Audit | COMPLETE |

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

P4-WP04 validation evidence:

- Strict immutable schema-version 1 records store named/versioned models and
  parameter sets with canonical SHA-256 identities. Parameter values retain SI
  units, source, structured citations, uncertainty, notes, calibration status,
  and an explicit measured, literature-derived, fitted, assumed, or
  calibration-required provenance category. Numeric values require citations;
  unknown records preserve every `CALIBRATION_REQUIRED` placeholder.
- The built-in catalog validates all five existing parameter documents through
  their accepted schemas only after their exact P2A file hashes pass. Audited
  imports must equal a complete code-owned built-in identity; focused tamper
  and relabelling probes failed closed even when the altered record hash was
  recomputed. All 45 built-in biological values remain unresolved and no
  calibration or biological claim is generated.
- Registry verification, atomic export, validated atomic import, and launch
  preflight application paths passed. Export/import bytes were identical and
  retained citations and uncertainty for measured, literature-derived,
  fitted, assumed, and unresolved test records. Exact model/schema/name/SI-unit
  checks run before the controlled plugin loader; a unit mismatch loaded no
  plugin code, and successful preflight required the exact reviewed selection.
- Registry reports bind registry, model, parameter-set, and plugin-selection
  identities without launching a simulation or changing P4-WP01 projects,
  raw-run artifacts, or P4-WP02 reports. Python 3.14.4 passed module help, live
  built-in verification, Ruff, strict mypy over 48 source files,
  `git diff --check`, and 223 tests. No P4-WP05 or later behavior was added.

P4-WP05 validation evidence:

- Strict schema-version 1 queue/item/resource/audit records persist through
  atomic replacement under a state lock. Highest integer priority executes
  first and equal priorities retain FIFO order. A separate nonblocking worker
  lease permits one local drain process, while status joins each item to an
  atomic campaign-state snapshot with exact completed/planned run progress.
- Before claiming work, the worker applies exact Linux CPU affinity and equal
  soft/hard `RLIMIT_AS` memory limits, reads both settings back, and persists
  their receipt. Work fails explicitly when current CPU availability or worker
  virtual-memory requirements cannot satisfy the declared limits; no remote or
  fallback execution path exists.
- Queued cancellation changes no project state. Running cancellation targets
  only a verified PID/process-start identity and stops through the campaign
  persistence boundary. Published completion receipts recover only after hash
  verification; otherwise cancelled or stale unpublished runs become explicit
  retryable `cancelled` or `interrupted` failures. Completed artifact bytes are
  reverified, never rewritten, and never rerun.
- The real `queue create`, `enqueue`, `status`, `run`, `run --once`, and
  `cancel` application paths passed, including priority ordering across worker
  restarts, live progress, single-worker rejection, queued/running
  cancellation, and exact one-core/8 GiB OS-limit receipts. Python 3.14.4
  passed module help, Ruff, strict mypy over 52 source files,
  `git diff --check`, and 227 tests. No P4-WP06 or later behavior was added.

P4-WP06 validation evidence:

- Strict schema-version 1 `.biomesh` archives carry a portable project
  definition, definition-bound campaign state, archive-contained hash-bound
  fixtures, and every artifact plus completion receipt for each verified
  completed run. Per-file paths, roles, sizes, and SHA-256 identities are
  cross-checked against the embedded project records; pending and failed runs
  remain explicit and running or unpublished artifact state fails closed.
- Stored ZIP metadata is fixed for byte-identical export. Verification rejects
  duplicate, encrypted, compressed, non-regular, out-of-root, missing, extra,
  oversized, corrupt, or project-inconsistent members. Import validates into a
  temporary sibling through the existing `CampaignService` before atomic
  publication and grants no plugin trust, registry identity, or queue state.
- A real P3-backed manufactured campaign exported twice byte-identically with
  20 carried files. The wheel-based Linux bundle verified its checksums,
  installed outside the clone, passed CLI validation and offscreen GUI smoke,
  then verified/imported the archive and retained a byte-identical completed
  artifact tree. The deterministic bundle builder rejects generated project,
  queue, report, raw-run, archive, CSV, Parquet, and NumPy-result payloads.
- Python 3.14.4 passed module help, Ruff, strict mypy over 55 source files,
  `git diff --check`, and 235 tests. No P4-WP07 or P4A behavior was added.

P4-WP07 validation evidence:

- Benchmark API version 1 defines strict immutable case, backend, output,
  environment, timing-observation, and divergence records. The fixed input is
  SHA-256-bound deterministic dimensionless 48 by 48 synthetic 2D stencil for
  four steps with `1e-12` absolute and relative engineering tolerances; it is
  not a model, biological input, 3D workload, or scientific result.
- The default `benchmark acceleration` application path executed only the
  scalar-loop CPU reference and recorded the experimental candidate as
  disabled. The candidate ran only with `--experimental`, declared NumPy
  float64 CPU/2D execution and `gpu_used: false`, and measured zero absolute
  and relative divergence with zero mismatches across all 2,304 values.
- Stdout, atomic artifact publication, explicit overwrite rejection, candidate
  divergence failure, invalid-output rejection, and opt-in timing paths passed.
  Timings remain raw local nanosecond observations with no warm-up, comparison
  ratio, inference, performance claim, GPU/3D claim, or scientific-accuracy
  claim. Accepted engine, campaign, plugin, registry, queue, archive, package,
  completed-run, and desktop paths remain unchanged.
- Python 3.14.4 passed module and benchmark help, Ruff, strict mypy over 57
  source files, `git diff --check`, and 242 tests. P4A was not begun; no merge
  or tag was created.

P4A production-remediation evidence (2026-08-11; audit remains incomplete):

- `P4A-001` is remediated prospectively by project/archive schema version 2.
  The pending platform-reference archive contains the project/state records,
  accepted fixture, and all five exact biological parameter documents under a
  strict eight-file checksum inventory. A clean installed wheel imported the
  archive outside the clone and completed all six runs. A completed 110-file
  archive reimported with zero byte mismatches, and pending/completed exports
  each reproduced byte-identically (`ed10fa93...f1f0d` and
  `3b402104...bce38`, respectively). The final Linux installer bundle was
  checksum-verified as `3f07fc4d...b1763` before its documented isolated
  install, validation, and offscreen GUI smoke paths passed.
- `P4A-002` is remediated prospectively by a strict execution identity that
  binds the complete built-in registry, all five named/versioned model and
  parameter-set records, parameter-source hashes, and canonical empty plugin
  set (`1919457d...10a0`) before work starts. All six real run requests and
  version 2 completion receipts repeated one exact execution identity
  (`cd8515f0...00a22`). Legacy version 1 completed projects/receipts remain
  readable and byte-unchanged; unfinished execution and backfilling fail.
- `P4A-003` is remediated by tracked
  `experiments/platform_reference.yaml` and the accepted command surface in
  `docs/09_PHASE_FOUR_AUDIT.md`. The reference is two manufactured SI-labelled
  conditions at seeds 101, 202, and 303, remains
  `CALIBRATION_REQUIRED`, and makes no biological-experiment claim.
- Focused project/archive/plugin/registry/queue/report tests passed. The full
  Python 3.14.4 gate passed 244 tests, Ruff, strict mypy over 57 source files,
  `git diff --check`, and module help. All 11 P2 fixture/report paths, P1
  validators and zero-mismatch replay, P3 zero-mismatch frontend/checkpoint
  paths and GUI gates, queue recovery, plugin/registry checks, default-disabled
  and opt-in isolated acceleration, clean wheel/Linux-installer paths, and the
  corrected P4A application commands passed.
- These are production remediation results only. P4A remains `INCOMPLETE` and
  must rerun independently from the exact pushed remediation commit; no audit
  result, merge, or tag is claimed here.

P4A independent audit evidence (2026-08-11):

- Audit result: `PASS WITH RECORDED LIMITATIONS`; Phase 4 is accepted at exact
  pushed prerequisite `b5bb3cf8ce12e67f6d80048aab2545e89bfcabe4`.
- A fresh Python 3.14.4 environment passed module help, Ruff, strict mypy over
  57 source files, `git diff --check`, and all 244 tests. P1 validators and
  zero-mismatch replay, all 11 P2 fixture/report paths, P3 zero-mismatch
  frontend/checkpoint verification, GUI/integration tests, and offscreen GUI
  smoke passed.
- The strict eight-file pending archive reproduced byte-identically at
  `ed10fa93...f1f0d`, carried the fixture and all five required parameter
  resources, and completed six runs from a clean external wheel installation.
  The external 110-file completed archive reproduced at `3795db66...4c37`,
  and completed export/import preserved the full 111-file project tree with
  zero byte mismatches. Corruption and path traversal failed explicitly.
- All six run requests and six schema-version 2 receipts repeated the exact
  five-model execution identity `cd8515f0...00a22`, registry identity, source
  hashes, and canonical empty-plugin identity `1919457d...10a0`. Legacy
  schema-version 1 completed bytes remained readable and unchanged; unfinished
  execution/backfilling failed explicitly.
- Independent report inspection retraced all 288 observations to raw hashes,
  sizes, Parquet rows, columns, and values. All six planned runs were covered,
  with 96 summaries, 48 pairwise comparisons, and no missing run. Plugin trust,
  registry immutability/SI checks, queue ordering/resources/cancellation/retry/
  recovery, and disabled-by-default acceleration isolation/equivalence passed.
- Repeated wheel, sdist, and Linux installer outputs were byte-identical at
  `12e69544...effb`, `c70ca745...424f`, and `4ff5aedc...f69d`. Fresh external
  wheel, sdist, and checksum-verified installer CLI/GUI paths passed. No
  generated research output was bundled or tracked.
- No Critical or Major finding remains. Biological values remain
  `CALIBRATION_REQUIRED`; plugin sandboxing, archive signing/confidentiality,
  portable queue state, installer update/rollback, biological validation, and
  GPU/3D/performance claims remain outside the accepted scope.

## P5 – Phase 5 – Security and Distribution Hardening

Source: `docs/10_PRE_V1_ROADMAP.md`.

| ID | Work package | Status |
| --- | --- | --- |
| P5-WP01 | Threat model and security requirements | COMPLETE |
| P5-WP02 | Installed-build provenance | COMPLETE |
| P5-WP03 | Signed and optionally confidential archives | COMPLETE |
| P5-WP04 | Isolated plugin execution | COMPLETE |
| P5-WP05 | Installer lifecycle and supply-chain verification | COMPLETE |
| P5A | Phase 5 Audit | COMPLETE |

P5-WP01 validation evidence:

- `docs/P5_WP01_THREAT_MODEL.md` version 1.0.0 maps all P5-applicable P4A
  limitations to assets, actors, entry points, trust boundaries, assumptions,
  abuse cases, required controls, verification, owners, open mitigation status,
  and residual risks. Queue portability, calibration/validation, and
  3D/acceleration remain explicitly assigned to P6-P8.
- The requirements distinguish integrity, authenticity, confidentiality,
  authorization, trust, provenance, and sandboxing; checksum integrity is not
  described as a signature. P5-WP02 through P5-WP05 receive 43 normative
  controls and 49 concrete fail-closed misuse/negative tests before any
  implementation begins.
- P5-WP01 adds no security implementation, algorithm choice, key material,
  scientific behavior, trust grant, calibration change, archive or artifact
  mutation, UI, cloud, release, or later-work-package behavior.
- Python 3.14.4 module help, Ruff, strict mypy, `git diff --check`, and all 244
  tests passed on 2026-08-11.

P5-WP02 validation evidence:

- BioMesh 0.5.0 publication now atomically produces exactly one wheel, sdist,
  Linux installer, and canonical cross-artifact manifest from a pre-resolved
  clean Git commit. Embedded records bind the exact commit, deterministic
  SHA-256 source-tree identity, and exact Python, Git, Hatchling, and BioMesh
  builder versions without requiring Git after installation.
- Verification rejects dirty tracked/untracked source, missing Git identity,
  changed-during-build source, altered artifact bytes, missing/malformed or
  inconsistent fields, duplicate/mismatched records, package-version drift,
  and embedded/external substitutions. Failed builds publish no output.
- Two full builds from separate clean clones of one commit produced equal
  wheel, sdist, installer, and manifest bytes. External wheel, sdist, and
  checksum-verified Linux-installer paths exposed the same source/build
  identity, and in-clone/installed P1 reference artifacts matched byte for
  byte. Focused and full Python 3.14.4 gates passed 256 tests, Ruff, strict mypy,
  module help, and `git diff --check` on 2026-08-11.
- This is integrity/provenance evidence, not authenticity, signing,
  confidentiality, trust, calibration, or installer lifecycle assurance. At
  the P5-WP02 boundary, P5-WP03 through P5-WP05 and P5A were incomplete.

P5-WP03 validation evidence:

- `docs/P5_WP03_ARCHIVE_SECURITY_POLICY.md` version 1.0.0 resolves AS-05 from
  RFC 8032, RFC 9180, RFC 7748, RFC 5869, NIST SP 800-38D, FIPS 180-4, RFC
  4648, and RFC 8410. It registers exact Ed25519 and RFC 9180 base-mode
  X25519/HKDF-SHA-256/AES-256-GCM HPKE suites, encodings, domain-separated
  constructions, recipient/key and replay bindings, one-message HPKE nonce/
  sequence policy, transition rules, and prohibited fallback, guessing,
  negotiation, and downgrade behavior.
- Secure verification binds every exact unsigned payload byte plus all signer,
  key, suite, encoding, confidentiality, recipient, HPKE context, and replay
  metadata. Explicit host-owned trust handles unknown, key-mismatch, revocation,
  validity windows, and replay policy before P4 parsing/import;
  archive contents grant no trust, authorization, calibration, or sandboxing.
- Optional authenticated confidentiality is separate from signing and fails on
  wrong recipients/keys, metadata or ciphertext change, truncation, extension,
  reordering, malformed fields, unsupported suites, or missing requested
  properties before plaintext/project publication. Legacy raw archives require
  explicit caller policy and persist `UNAUTHENTICATED`/`PLAINTEXT` status.
- MT-AR-01 through MT-AR-14 focused tests assert actionable errors and absence
  of targets/partial projects. The exact prerequisite's pending eight-file P4
  payload reproduced unchanged at SHA-256
  `91473214ce3f523f72d55e9750e29940a414aac2560f4294cb0d12a1e7eafa4f`;
  signed import retained completed artifact/receipt bytes. Python 3.14.4 with
  `cryptography` 50.0.0 passed 270 tests, Ruff, strict mypy over 61 source
  files, `git diff --check`, module help, and the secret-leak review on
  2026-08-12.
- P5-WP03 implements no plugin sandbox, installer lifecycle, queue portability,
  new science, calibration, UI, cloud, remote execution, or P5 acceptance.
  At that work-package boundary, P5-WP04, P5-WP05, and P5A were incomplete.

P5-WP04 validation evidence:

- Every reviewed non-empty operation now passes whole-set review/API/
  distribution/entry-point/root preflight before code starts, then executes in
  a fresh Bubblewrap 0.11.1 boundary under sandbox policy 1.0.0. Read-only
  declared runtime mounts, a read-only root, private temporary/output paths,
  cleared environment, isolated network/PID namespaces, dropped capabilities,
  and libseccomp syscall denial prevent access to arbitrary host/project files,
  secrets, network, mutable engine state, and undeclared child capabilities.
  Enforcement failure has no fallback.
- Schema 1 canonical messages are request/response bounded and bind the plugin,
  selection, policy, operation, and request identity. The host revalidates
  schema, units, complete biological provenance, `CALIBRATION_REQUIRED`, field
  identity/shape, safe paths, and exporter bytes before atomic publication.
  Secret-free receipts distinguish preflight denial, setup, policy, timeout,
  crash, resource, malformed-output, communication, and success outcomes.
- MT-PL-01 through MT-PL-13 cover denied file/network/environment/state/process
  attempts, policy mismatch, SI/provenance kinetics, malformed/oversized/wrong
  identity output, crash, wall timeout, CPU/memory exhaustion, interruption
  boundaries, unchanged completed bytes, and empty-set no-process behavior.
  The canonical empty-plugin SHA-256 remains
  `1919457d222318dd73626ea9b92a26b0697d1b96230dff5ed254842ca9b310a0`.
- P5-WP04 adds no plugin approval, archive trust, installer lifecycle, queue
  portability, new science, calibration, UI, cloud, remote execution, or P5
  acceptance. Python 3.14.4 passed 285 tests, Ruff, strict mypy over 64 source
  files, module help, plugin CLI receipt inspection, and `git diff --check` on
  2026-08-12. At that work-package boundary, P5-WP05 and P5A were incomplete.

P5-WP05 validation evidence:

- Policy/schema 1 in `docs/P5_WP05_INSTALLER_LIFECYCLE.md` verifies the exact
  P5-WP02 wheel, build identity, and installer artifact binding before prefix
  mutation, then binds every installed application, dependency, metadata, and
  version-specific launcher regular file to a canonical path/role/size/SHA-256/
  owning-version record. The complete manifest hash is part of the side-by-side
  version-directory identity; unsafe, duplicate, symlinked, non-regular,
  missing, extra, modified, ambiguous, or out-of-root state fails explicitly.
- Fresh install and upgrade stage/reverify a complete candidate, atomically
  publish it beside prior versions, pass installed CLI help and offscreen GUI
  smoke, and only then atomically switch the single `current` pointer. Exact
  verified rollback targets repeat both smoke paths. A canonical transaction
  journal recovers every staging, publication, activation, rollback, and
  uninstall boundary to one explicit complete state without mixed launchers.
- Normal uninstall removes only an exact manifest-owned version tree and its
  fixed launchers. Modified/missing/extra state blocks by default; an exact
  path acknowledgement plus explicit quarantine retains the complete changed
  tree rather than deleting unowned/local bytes. Projects, archives,
  parameters, queues, reports, configuration, completed artifacts, research
  data, and source datasets remain outside installer ownership and reproduce
  byte-identically across all lifecycle paths.
- MT-IN-01 through MT-IN-14 cover altered wheel/provenance/ownership inputs,
  traversal/duplicate/symlink/target-root failures, fresh/upgrade/rollback/
  uninstall interruptions, smoke failure, changed owned paths, absent/altered
  rollback, ownership-safe quarantine, user-data retention, launcher mismatch,
  installed CLI/GUI smoke, and exact completed-artifact preservation. BioMesh
  also selects its declared PySide6 binding before pyqtgraph loads, preventing
  unrelated Qt bindings from mixing ABIs during installed GUI verification.
- Python 3.14.4 passed 311 tests (including the host-level Bubblewrap/
  libseccomp cases), Ruff, strict mypy, module help, and `git diff --check` on
  2026-08-14. A clean temporary clone also built/verified the complete 0.5.0
  publication and passed real bundle fresh-install CLI/GUI smoke; a non-
  published `0.5.0.post1` rehearsal passed upgrade smoke, exact rollback, both
  uninstalls, five lifecycle logs, and unchanged adjacent user-data SHA-256.
  P5-WP05 adds no automatic update, system-package integration,
  cloud/remote execution, queue portability, new UI, science, calibration,
  archive/plugin trust, or P5 acceptance. The completed implementation is
  frozen for independent audit by `v0.5.0`; P5A remains incomplete.

P5A remediation evidence:

- The remediation started from exact pushed implementation commit
  `d41c7cbbadbe0ed1af9c5547dcb1429da3f99a8f` on
  `origin/phase-5-security-distribution`. Independent reproductions confirmed
  all three Major findings before changes: nested prefix symlinks redirected
  writes, a traversal stage name redirected recovery deletion, and a broad
  plugin root exposed a sibling file.
- Installer preflight now rejects symlinked prefix/lib/bin and lifecycle-root
  components; safe direct-child derivation and strict journal identity/phase
  validation prevent both write and recovery redirection. Plugin preflight
  inventories and rechecks only the selected entry-point module/package and
  mounts individual declared dependency package roots rather than broad
  site-package content. Source-run metadata records commit, working-tree
  identity, and state; run metadata records the complete declared direct
  runtime dependency inventory. The existing PySide6 binding pin is covered by
  a conflicting-preference regression test.
- Focused remediation/installer/plugin/provenance/GUI tests passed 48 tests;
  the explicit BP/AR/PL/IN evidence collection passed 85 tests. The final gate
  passed `python -m biomesh --help`, `ruff check .`, `mypy src`, `pytest -q`
  with 319 passed, and `git diff --check`.
- P5A remains `INCOMPLETE`; this remediation does not accept Phase 5, create an
  accepted-audit tag, merge to `main`, or unblock P6. A separate fresh P5A audit
  must use the pushed remediation commit.

P5A installer recovery/provenance remediation evidence:

- The follow-up remediation started from exact commit
  `afea7c11a148cbbdd52df2f2534bd187074dcdb6`. Safe temporary reproductions
  confirmed that a canonical `launchers-removed` journal activated an
  unmanifested retired tree as `verified_installation_restored`, deleted the
  journal, and ran zero smoke checks; the target-to-retired rename crash window
  likewise activated a modified tree whose later verification reported
  `modified:app/biomesh/__init__.py`, with zero smoke calls.
- Uninstall recovery now accepts exactly one journal-named target or retired
  tree and requires its canonical manifest, version, manifest SHA-256, wheel
  SHA-256, provenance SHA-256, directory identity, and complete owned-file tree
  to match before restore. It smoke-checks the installed CLI/offscreen GUI
  before current-version activation and preflights all launcher/current paths.
  Missing, malformed, mismatched, modified, extra, symlinked, ambiguous, or
  smoke-failing state leaves launchers/current unchanged and retains the journal
  for explicit recovery. Exact acknowledged quarantine remains ownership-safe.
- A separate temporary Git fixture confirmed that changing equal untracked
  bytes from mode 0644 to 0755 previously produced the same modified identity.
  The versioned `biomesh-working-tree-v2` encoding length-delimits typed fields
  and binds each untracked regular file's permission mode, path, and bytes;
  repeated collection is deterministic and the clean identity path is unchanged.
- Python 3.14.4 passed 49 focused installer/provenance tests, the explicit
  103-test BP/AR/PL/IN evidence collection, `python -m biomesh --help`, Ruff,
  strict mypy over 65 source files, the complete suite with 337 tests, and
  `git diff --check` on 2026-08-15.
- P5A remains `INCOMPLETE`; this remediation does not accept Phase 5, merge or
  tag an audit, unblock P6, or add later-phase behavior. A fresh independent
  P5A audit must assess the pushed remediation tip.

P5A final containment/recovery remediation and fresh audit evidence
(2026-08-15):

- The rejected audit revision was exact pushed commit
  `0d266186c73a209053c0d3f42a975ac5c46f35e3` on
  `origin/codex/p5a-installer-recovery-provenance`. Independent synthetic
  pre-fix probes reproduced both blockers: an installed-style broad BioMesh
  mount exposed an undeclared sibling (`sentinel_visible=True`), built-in
  mutation yielded `inventory_matches=False` with `preflight_accepted=True`,
  changed target wheel/provenance identities still smoke-tested and activated,
  and rollback retained a valid version unrelated to its journal source/target.
- Plugin discovery now resolves and individually mounts only the exact
  `biomesh` package and one validated BioMesh `.dist-info` directory. The
  selected plugin payload and declared dependency package roots remain explicit
  mounts; site-packages, environments, prefixes, and undeclared siblings are
  never fallback mounts. Both built-in and external distribution inventories
  must match before every operation, and uncertain core-root discovery rejects
  execution.
- Transaction journal schema 2 records exact source and target version,
  manifest, wheel, and provenance identities. A centralized comparison proves
  the current/candidate state is an exact recorded transaction state before
  smoke, launcher or `current` mutation, activation, retirement/finalization,
  or journal deletion. Identity mismatch and unrelated rollback state leave all
  activation paths unchanged and retain the journal; legacy schema-1 recovery
  fails closed rather than inferring missing identity.
- Focused regressions cover installed sibling denial with worker/plugin
  availability, authorized dependency mounts, built-in and external mutation,
  unsafe BioMesh, metadata, and declared-dependency discovery,
  wheel/provenance/manifest/version mismatches,
  pre-smoke ordering, unchanged activation/launchers, journal retention,
  unrelated rollback state, exact source identity, and successful exact-target
  recovery.
- The required eight-file BP/AR/PL/IN collection passed 118 tests with zero
  failures or skips. Python 3.14.4 passed `python -m biomesh --help`, Ruff,
  strict mypy over 65 source files, the complete suite with 352 tests and zero
  failures/skips, and `git diff --check`.
- A distinct post-fix audit pass re-read BP/AR/PL/IN ownership and threat/control
  mapping, inspected build/archive/plugin/installer ordering, and ran temporary
  probes outside the regression entry points. It observed
  `sentinel_visible=False`, built-in and external mutation
  `preflight_denied`, every target identity mismatch rejected with zero smoke
  calls and journal retention, successful exact-identity recovery, and
  unrelated rollback state rejected without mutation.
- Audit decision: `P5A ACCEPTED`. No Critical, High, or Medium finding remains,
  both original blockers are closed, and no new acceptance-blocking defect was
  found. P5A is `COMPLETE`. Per this audit task's explicit boundary, no merge,
  tag, `main` mutation, or P6 implementation occurred.

## P6 – Phase 6 – Portable Operations

Source: `docs/10_PRE_V1_ROADMAP.md`.

| ID | Work package | Status |
| --- | --- | --- |
| P6-WP01 | Portable queue-intent schema | INCOMPLETE |
| P6-WP02 | Explicit import and local rebinding | INCOMPLETE |
| P6-WP03 | Resume, retry, and recovery across hosts | INCOMPLETE |
| P6-WP04 | Operational documentation and migration | INCOMPLETE |
| P6A | Phase 6 Audit | INCOMPLETE |

## P7 – Phase 7 – Calibration and Validation

Source: `docs/10_PRE_V1_ROADMAP.md`.

| ID | Work package | Status |
| --- | --- | --- |
| P7-WP01 | Calibration protocol and evidence governance | INCOMPLETE |
| P7-WP02 | Versioned dataset ingestion and quality control | INCOMPLETE |
| P7-WP03 | Deterministic parameter estimation and uncertainty | INCOMPLETE |
| P7-WP04 | Independent validation and applicability domain | INCOMPLETE |
| P7-WP05 | Registry promotion and scientific reporting | INCOMPLETE |
| P7A | Phase 7 Audit | INCOMPLETE |

P7 is evidence-blocked until suitable licensed source data and qualified domain
review are available. Unknown values remain `CALIBRATION_REQUIRED`; software
work alone cannot satisfy P7 or P7A.

## P8 – Phase 8 – 3D and Accelerated Computing

Source: `docs/10_PRE_V1_ROADMAP.md`.

| ID | Work package | Status |
| --- | --- | --- |
| P8-WP01 | 3D model and numerical contract | INCOMPLETE |
| P8-WP02 | Deterministic 3D CPU reference | INCOMPLETE |
| P8-WP03 | Accelerated backend and isolation | INCOMPLETE |
| P8-WP04 | Equivalence, determinism, and performance methodology | INCOMPLETE |
| P8-WP05 | Application integration and provenance | INCOMPLETE |
| P8A | Phase 8 Audit | INCOMPLETE |

## P9 – Phase 9 – Version 1 Release

Source: `docs/10_PRE_V1_ROADMAP.md`.

| ID | Work package | Status |
| --- | --- | --- |
| P9-WP01 | Version 1 scope, API, and schema freeze | INCOMPLETE |
| P9-WP02 | Migration and backward compatibility | INCOMPLETE |
| P9-WP03 | Release packaging and platform matrix | INCOMPLETE |
| P9-WP04 | Documentation, examples, and claim review | INCOMPLETE |
| P9-WP05 | Release-candidate rehearsal | INCOMPLETE |
| P9A | Version 1 Release Audit | INCOMPLETE |

## Next Work Package

`P6-WP01 – Portable queue-intent schema` is the first incomplete pre-v1 work
package. It may begin only in a fresh subsequent task in strict phase order;
this P5A task does not authorize or implement P6 behavior.

## Remaining Issues

- All biological values remain `CALIBRATION_REQUIRED`; the reference is a
  non-scientific software/replay fixture.
- The canonical P1A tag `v0.1.1-audit` is present at the accepted P1A commit;
  P2A does not retroactively change that historical audit.
- P4A accepted Phase 4. P4-WP01 through P4-WP06 add the local synchronous
  project/campaign model, presentation-neutral comparison/report data, and a
  separately verified plugin API plus a declarative model/parameter registry.
  The accepted engine/campaign path still uses zero plugins and is unchanged
  by registry data. P4-WP05 adds the separate persistent OS-limited local queue
  described above. P4-WP06 adds explicit portable archive CLI paths and a
  documented Linux installer bundle without migrating queue state or granting
  trust. P4-WP07 adds only an isolated disabled-by-default synthetic 2D
  benchmark and opt-in NumPy CPU candidate; no benchmark backend enters model
  execution and no GPU, 3D, performance, or scientific claim is made. The
  desktop has no queue/report/plugin/registry/archive UI, cloud, automatic
  plugin trust, or calibration behavior.
