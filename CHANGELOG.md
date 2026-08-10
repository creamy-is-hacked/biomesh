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
- P3-WP01 – A typed synchronous application service exposing run, pause, one
  solver-boundary step, hash-verified checkpoint/resume, immutable snapshot and
  cell inspection, and canonical raw-artifact export operations. The service
  reuses the accepted P2 fixture adapter and exposes no mutable engine state,
  GUI toolkit, worker, viewer, or new scientific behavior.
- P3-WP02 – A PySide6 Linux desktop shell with a main window, File/View/Help
  menus, dockable project and error-console panels, a status bar, opaque recent
  project references, and strict atomic UI-preference persistence under the
  user's configuration directory. Qt runs independently of the scientific
  application service; no viewer, editor, worker, analytics, controls, export,
  or scientific behavior was added.
- P3-WP03 – A PyQtGraph-backed, snapshot-only simulation viewer with separate
  coordinate-faithful cell and scalar-field canvases, zoom, pan, fit, per-layer
  visibility and opacity, value legends, and newest-frame rate limiting.
  Hidden layers skip cell-path rebuilds and field-image uploads; headless
  application-path tests compare displayed fields with canonical exported
  NumPy arrays without changing the immutable application API or simulation.
- P3-WP04 – A schema-generated editor for all five existing validated
  biological-parameter documents. It displays complete SI provenance and
  explicit validation errors, keeps mutable draft/UI state separate from
  immutable validated configurations, atomically saves and semantically
  reloads TOML, rejects invalid or unresolved run eligibility, and provides
  editable templates plus SHA-256-bound read-only P2A presets that cannot be
  overwritten. It adds no run controls, worker, project model, export, or
  scientific behavior.
- P3-WP05 – A smallest-scope background worker and desktop controls for exact
  existing P2 fixture/condition/seed requests, solver-boundary run, pause,
  single-step, stop, speed targets, hash-verified checkpoint/resume, and
  immutable cell-click inspection. Invalid or unresolved editor state cannot
  enable run or checkpoint resume, editor documents are never passed to the
  engine, stale-frame inspection fails explicitly, and accepted stop prevents
  any later advancement. No scientific behavior, analytics, additional export,
  campaign/project model, or future-phase behavior was added.
- P3-WP06 – Snapshot-only live plots for exact stored population, dry biomass,
  producer cell frequency, EPS, continuous quorum response, thickness,
  roughness, and carbon/oxygen penetration depths. Completed runs export on the
  existing worker as deterministic PNG and exact CSV/Parquet analytics while
  preserving canonical Parquet tables, NumPy fields, seed, commit, biological
  parameter hashes, calibration status, and software versions. Cancellation
  and failure leave no partial target; no scientific behavior or future-phase
  model was added.
- P4-WP01 – Versioned local project, experiment, campaign, run, artifact, and
  audit records with deterministic explicit/sequence seed policies and
  SI/provenance-complete sweep points. Campaign state is lock-protected and
  atomically replaced; interrupted publication is reconciled from a completion
  receipt, completed artifacts are hash-verified and never rerun, and partial
  failures remain explicit until an intentional retry. The synchronous runner
  uses only the accepted P3 application service and adds no queue, report,
  plugin, registry, archive, acceleration, calibration, or scientific behavior.

### Audit findings

- P3A – Independent clean-clone audit of pushed implementation commit
  `ed062935552c6a5df639c56474c7854cac91bd69` passed with recorded
  limitations. Python 3.14.4 installation, all 195 tests, the two audit
  collections, Ruff, strict mypy, module help, GUI smoke, P1/P2 preservation,
  zero-mismatch frontend comparison, 15-file checkpoint replay, real desktop
  controls/inspection/analytics/export probes, 1024×720 responsiveness,
  keyboard traversal, canonical artifacts, provenance, output hygiene, and
  fresh wheel/sdist application paths passed. No Critical or Major finding
  remains; manufactured fixtures remain separate from biological evidence and
  all biological parameters remain `CALIBRATION_REQUIRED`.

- P3A – The first independent audit attempt against
  `c2de0acfc1f025492069923f7594443b933e5acd` stopped with `FAIL`: the mandatory
  `compare-frontends` and `verify-checkpoint` CLI paths, reference selector,
  and documented `tests/gui tests/integration` collection paths were absent.
  No later audit condition, merge, or tag was attempted in that failed run.

- P2A – Independent clean-clone audit of
  `6adb5def6f094762cb79ba3a2eddeede6007a2f5` passed with recorded limitations.
  Python 3.14.4 installation, all 145 tests, P1 validators and replay, all 11
  campaign/report paths, byte-identical full replay, artifact hashes and
  schemas, accounting, replicate Student-t statistics, descriptive rankings,
  documentation, provenance, and output hygiene passed. Phase 2 is accepted;
  manufactured fixtures remain distinct from biological calibration.
- P2A – Independent audit of
  `88386fab116976ebae4b6a9a5a53bb1511053e86` found `P2A-003`: the implemented
  P2-WP05/P2-WP06 release behavior was absent from `docs/ARCHITECTURE.md`, and
  `README.md` still said Phase 2 may begin. The technical, campaign, artifact,
  accounting, provenance, and byte-replay evidence otherwise passed.
- P2A – Independent audit of `d0c80c5` failed (`P2A-001`): the P2 production
  campaign runner and all documented experiment, sweep, and report CLI paths
  were absent. This P2-WP06 remediation adds the deterministic runner and the
  required command paths with manufactured SI software-validation fixtures;
  P2A must be rerun independently before any Phase 2 acceptance claim.
- P2A follow-up `P2A-002` found that the published root fixture set still
  omitted executable paths for both inoculation patterns, both EPS-control
  modes, and the nutrient/oxygen sweep. P2-WP06 now publishes those five
  missing paths and validates exact one-time coverage of all 15 executable
  campaign conditions.

### Fixed

- P3 pre-audit blocker remediation adds strict manufactured reference
  selection, atomic CLI/application byte-equivalence evidence, hash-verified
  checkpoint replay, actionable tamper failures, and the documented GUI and
  integration test collections. The P2 published seed matrix and desktop
  selector remain fixed at 101, 202, and 303; audit seed 42 is isolated to the
  P3 application verification surface. Python 3.14.4, 195 tests, Ruff, strict
  mypy, module help, `git diff --check`, both mandatory CLI paths, and offscreen
  GUI smoke passed locally. The subsequent clean audit accepted P3 with the
  recorded limitations above.
- P3 display-usability remediation contains rich dock contents within local
  scroll areas, declares and verifies a 1024×720 supported minimum, and adds
  explicit logical keyboard focus order for run, lifecycle, speed, and
  checkpoint controls without changing simulation state or scientific inputs.

- Repository remediation after P3-WP04: SoluteField now rejects every
  negative state; campaign condition IDs and all resolved outputs are
  root-contained; artifacts, campaign records, checkpoints, exports, and
  reports publish via retry-safe atomic staging; packaged wheels/sdists carry
  runtime fixtures; CI covers external package installs and entry points;
  RunMetadata enforces canonical SHA-256 provenance; and the accepted P1A
  audit tag is recorded. BM-008/BM-009 remain deferred by contract. P3A closes
  BM-010 after direct worker, stop, cancellation, responsiveness, and
  actionable-error probes passed.

- P2-WP06 – Remediated `P2A-003` by aligning README status and the documented
  command surface with all 11 published fixtures, and by documenting P2-WP05
  waste/shear plus the P2-WP06 campaign adapter, update order, artifacts,
  statistics, reports, and calibration boundary. The full required gate passed
  with 145 tests; P2A must rerun independently before Phase 2 acceptance.
- P2-WP06 – Added the executable P2 update adapter, strict artifact checks,
  raw Parquet/NumPy run outputs, provenance manifests, replicate statistics,
  descriptive observed-range sensitivity rankings, and PNG reports. Verified
  locally with all required CLI paths, `ruff check .`, `mypy src`, and 144
  tests, then reproduced from a fresh Python 3.14 editable-install clone.
  Fixtures are manufactured software validation only, not calibration.
- P2-WP06 – Completed the `P2A-002` release surface with 11 strict root-level
  fixtures covering all 15 conditions at seeds 101, 202, and 303. The fixture
  configuration hash is now distinct from the five `CALIBRATION_REQUIRED`
  biological-parameter records. Full artifact validation rejects path escape,
  missing or malformed Parquet/NumPy data, hash/size drift, incomplete SI
  accounting, malformed provenance, incomplete replicate statistics, and
  missing applicable observed-range rankings. All 11 fixture/report trees
  replayed byte-identically.

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
