# Changelog

All notable repository changes are documented here.

## Unreleased

### Added

- Pre-v1 governance roadmap – Strict P5-P9 work-package ordering with canonical
  implementation/audit branches and tags, threat-derived security hardening,
  portable operations, evidence-gated biological calibration and validation,
  separately audited 3D/acceleration, and a blocking version 1 release audit.
  This planning change adds no implementation or post-v1 authority.
- P5-WP01 – Versioned the P4A-derived threat model for build provenance,
  archive authenticity/confidentiality, plugin isolation, installer lifecycle,
  and local execution. It defines assets, actors, entry points, trust
  boundaries, assumptions, abuse cases, owners, open mitigation status,
  residual risks, and 49 fail-closed misuse tests required before P5-WP02
  through P5-WP05 implementation. No security control or algorithm was added.
- P5-WP02 – Added deterministic whole-set building and fail-closed verification
  for BioMesh 0.5.0 wheels, sdists, and Linux installers. Canonical embedded
  records bind the exact clean Git commit, SHA-256 source-tree identity, and
  Python/Git/Hatchling/BioMesh builder versions; the publication manifest binds
  final artifact SHA-256 values and sizes. Installed execution exposes the
  embedded identity without Git and records the exact commit instead of an
  unavailable placeholder. Focused MT-BP-01 through MT-BP-08 tests cover dirty,
  missing, changed, tampered, malformed, duplicate, repeated-build, and
  clean-install behavior without adding authenticity, signing, lifecycle, or
  scientific claims.
- P5-WP03 – Resolved AS-05 with versioned algorithm policy 1.0.0 and added an
  algorithm-agile secure envelope around exact deterministic P4 archive bytes.
  The production profile uses Ed25519 signing and separately requested RFC 9180
  X25519/HKDF-SHA-256/AES-256-GCM HPKE confidentiality, binds signer/key,
  recipient/key, suite, encoding, payload, HPKE context, and replay metadata,
  and verifies host-owned trust before P4 validation/import. Unknown, mismatched,
  revoked, expired, tampered, replayed, wrong-recipient, malformed, duplicated,
  unsupported, and property-confused inputs fail without partial publication.
  Legacy raw P4 archives now require explicit caller opt-in and retain durable
  `UNAUTHENTICATED`/`PLAINTEXT` status. Private key markers and secret-bearing
  archive/installer paths are rejected; keys remain external. Focused
  MT-AR-01 through MT-AR-14 tests preserve inner archive and completed-run
  bytes and keep authenticity, confidentiality, trust, authorization,
  provenance, sandboxing, and scientific validity distinct.
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
- P4-WP02 – Presentation-neutral JSON and CSV comparison/report data over
  hash-verified P4 project runs. Exact SI scalar observations retain raw
  artifact SHA-256, size, row, column, run, seed, and replicate traceability;
  condition distributions, Student-t uncertainty, pairwise mean differences,
  and Hedges g remain descriptive. Incomplete runs and single-seed evidence are
  explicit, report publication is atomic and deterministic, and no scientific
  conclusion or calibration claim is generated.
- P4-WP03 – Version 1 immutable plugin interfaces for species, kinetics,
  fields, metrics, and exporters. Whole-set API, metadata-hash, exact
  distribution/entry-point, and code-owned trust-policy checks complete before
  any plugin import. The deterministic `plugins verify` path records plugin
  provenance and limitations atomically, verifies core operation with zero
  plugins, and exercises a packaged `CALIBRATION_REQUIRED` species/kinetics
  example using only caller-supplied SI/provenance inputs. Existing engine,
  campaign, raw-run, and report contracts remain unchanged.
- P4-WP04 – Deterministic named/versioned model and parameter-set registry with
  canonical record hashes, SI compatibility checks, measured,
  literature-derived, fitted, assumed, and calibration-required provenance,
  structured citations, uncertainty-preserving import/export, and exact
  reviewed-plugin preflight. The five existing accepted parameter presets are
  byte-verified and immutable; registry reports do not launch simulations,
  alter raw runs/reports, or make calibration or biological claims.
- P4-WP05 – A persistent local campaign queue with deterministic priority/FIFO
  scheduling, atomic audited state, run-level progress, exact Linux CPU-affinity
  and address-space limits, single-worker enforcement, targeted cancellation,
  and stale-worker restart recovery. It schedules only the accepted P4-WP01
  campaign service; completed artifacts remain immutable and hash-verified,
  interrupted/cancelled runs remain explicit and retryable, and no remote,
  scientific, plugin-trust, archive, packaging, or acceleration path is added.
- P4-WP06 – Deterministic portable project export, checksum verification, and
  atomic import with archive-contained hash-bound fixtures, exact completed-run
  artifacts/receipts, explicit pending/failed state, and clean-install
  reproduction. A separate reproducible Linux wheel-installer bundle verifies
  its own checksums and rejects generated project, queue, report, raw-run,
  archive, CSV, Parquet, and NumPy research data. Archive exchange grants no
  plugin trust, registry identity, or queue migration and adds no scientific,
  calibration, acceleration, P4-WP07, or audit behavior.
- P4-WP07 – A versioned, isolated benchmark boundary with a deterministic
  scalar-loop CPU reference and an explicitly enabled NumPy CPU feasibility
  candidate over one synthetic dimensionless 2D stencil. Reports measure
  pointwise divergence and optional raw local timings, publish atomically, and
  state accuracy/performance limitations without a speedup, GPU, 3D,
  production, or scientific claim. The accepted engine and all completed-run,
  plugin, registry, queue, archive, package, and desktop contracts remain
  unchanged.

### Audit findings

- P4A – The independent rerun of exact pushed prerequisite
  `b5bb3cf8ce12e67f6d80048aab2545e89bfcabe4` passed with recorded
  limitations and accepted Phase 4. Python 3.14.4, all 244 tests, complete
  P1-P3 regressions, all 11 P2 fixture/report paths, six-run external wheel
  archive completion, 288 raw-retraced report observations, six exact
  request/receipt identities, queue/plugin/registry/acceleration controls,
  corruption/traversal rejection, a byte-identical 111-file completed project
  reimport, and reproducible wheel/sdist/installer bytes passed. No Critical or
  Major finding remains; biological/calibration, plugin sandboxing, archive
  signing, portable queue, installer lifecycle, GPU/3D, and performance claims
  remain outside scope.

- P4A – The first independent audit identified `P4A-001` (pending portable
  campaigns omitted the five fixture-relative biological parameter documents),
  `P4A-002` (completed-run provenance did not explicitly identify the complete
  named/versioned model/parameter registry selection or the empty plugin set),
  and `P4A-003` (the audit authority named unsupported commands and a missing
  platform reference). The independent rerun recorded above closes all three
  findings.

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

- P4A remediation – New schema-version 2 project definitions bind the complete
  built-in registry, all five named/versioned model and parameter-set records,
  exact parameter-source hashes, and the canonical zero-plugin-set hash before
  execution. Real run requests and version 2 completion receipts repeat that
  identity. Historical schema-version 1 completed projects and receipts remain
  byte-preserved and readable; unfinished legacy execution/backfilling fails
  explicitly.
- P4A remediation – New deterministic archive schema version 2 embeds all five
  fixture-required biological parameter documents at contained relative paths,
  inventories and cross-checks every byte, preserves completed artifacts and
  receipts, and allows an imported pending multi-condition campaign to complete
  from an installed-layout package. Plugin code/trust, registry documents/trust,
  and queue state remain non-transferable.
- P4A remediation – Added `experiments/platform_reference.yaml`, a strict
  two-condition, three-fixed-seed manufactured software-validation project with
  SI/provenance-complete sweep records and `CALIBRATION_REQUIRED` boundaries,
  and aligned `docs/09_PHASE_FOUR_AUDIT.md` with the accepted project, campaign,
  archive, report, plugin, registry, benchmark, and Hatchling command surface.

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
