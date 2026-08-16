# BioMesh Project State

This file is the canonical snapshot of the repository's current development
state. Read it immediately after `docs/STANDARDS.md` before selecting work.
`docs/PHASE_STATUS.md` remains the authoritative ordered work-package tracker.

Snapshot verified: 2026-08-16 for P6-WP04 on
`phase-6-portable-operations`. The completed implementation publishes the
operator migration/version matrix and adds only deterministic no-publication
dry-run plus read-only portable-record status. Python 3.14.4 passes 23 focused
P6 tests, the 60-test P6/P4 migration regression collection, and the 375-test
full gate. Phase 5 remains the latest accepted phase at `v0.5.1-audit`;
`v0.6.0` freezes P6 implementation for P6A but does not accept Phase 6.

| Field | Current state |
| --- | --- |
| Current phase | P6 – Phase 6 – Portable Operations (implementation complete; P6A not begun) |
| Current work package | P6-WP04 – Operational documentation and migration (`COMPLETE`) |
| Current branch | `phase-6-portable-operations` after P6-WP04 |
| Latest accepted phase | P5 – Phase 5 – Security and Distribution Hardening, accepted by P5A on 2026-08-15 |
| Latest version tag | `v0.6.0` (P6 implementation prerequisite; not phase acceptance) |
| Current test count | 375 passed, 0 failed, 0 skipped (`pytest -q`, 2026-08-16) |
| Next planned work package | P6A – Phase 6 Audit in a fresh independent task; P7 and later work remain unauthorized |

## Outstanding technical debt

- License selection is pending; no license was added by the audit.

## Known limitations

- Biological parameters remain configurable and `CALIBRATION_REQUIRED`; no
  calibrated biological result is claimed.
- P1's reference is a zero-duration, zero-cell, zero-solute software fixture,
  not a calibrated biological experiment.
- P2-WP06 supplies a deterministic campaign adapter and required CLI surface
  using 11 manufactured SI-labelled software-validation fixtures covering all
  15 executable conditions at three fixed seeds. Fixture configuration and the
  five biological TOML records have separate hashes; biological records remain
  provenance-complete and `CALIBRATION_REQUIRED`. P2A accepted the application
  path after two complete byte-identical campaign/report runs. Fixtures and
  their outputs are not calibration or biological evidence. The sensitivity
  rankings are descriptive observed ranges, EPS is an immobile field, shear is
  a non-CFD exposure abstraction, and P2 adds no mutation or evolution.
- P3-WP01 controls only the existing manufactured P2 fixture path. It is
  synchronous and headless; checkpoints are hash-verified deterministic replay
  positions, and export preserves the existing completed raw artifact set. The
  pre-audit verification adapter accepts independent deterministic seed 42 for
  CLI/application byte comparison without expanding the published P2 campaign
  or GUI seed selectors. The minimum supported desktop display is 1024×720;
  rich dock content scrolls locally and primary controls have explicit keyboard
  focus order.
- P3-WP03 renders immutable snapshots only. Cells retain SI coordinates in a
  separate canvas from grid-indexed fields because P3-WP01 exposes no physical
  field extent. P3-WP04 edits the five existing biological-parameter schemas
  only; unresolved records remain `CALIBRATION_REQUIRED` and run-ineligible.
  Audited presets are hash-bound and read-only, while editable configurations
  are separate from UI preferences and round-trip through strict TOML
  validation.
- P3-WP05 controls only the exact existing P2 fixture/condition/seed surface.
  The editor is an eligibility gate but its parameter document is not executed.
  One worker serializes public application-service calls; stop completes any
  in-flight accepted boundary before closing and schedules no later advance.
  Inspection uses immutable public records; local EPS density is exposed but a
  per-cell EPS production rate is not, so the UI does not infer one. P3-WP06
  plots only received immutable stored metrics. Its completed-run
  bundle preserves canonical field/table/metadata bytes, adds exact
  CSV/Parquet and PNG representations, and publishes atomically through the
  existing cancellable worker. Fresh-session checkpoint resume does not invent
  unseen earlier plot history. Project models, persistent queues, plugins,
  acceleration, calibration behavior, and new biology remain absent. P3A
  accepted these boundaries after zero-mismatch frontend and checkpoint
  verification, direct desktop probes, and clean wheel/sdist application paths.
- License selection is pending.
- The post-P3-WP04 remediation fixes BM-001, BM-002, BM-003, BM-004, BM-005,
  BM-006, and BM-007. BM-008 and BM-009 remain deferred because their required
  behavior is not established by the current contracts. P3A closes BM-010:
  direct worker, stop, export-cancellation, responsiveness, and error probes
  passed without adding scientific or P4 behavior.
- P4-WP01 projects reference accepted application fixtures by SHA-256 and
  execute synchronously through `ApplicationService`. Sweep points must match
  existing fixture conditions exactly; they do not apply arbitrary editor
  documents or invent biological inputs. P4-WP02 reports only 16 exact stored
  SI scalar metrics from hash-verified completed runs; every observation traces
  to raw bytes, missing runs remain explicit, and single-seed evidence cannot
  acquire an uncertainty estimate or replicated claim. Its JSON/CSV data is
  presentation-neutral and creates no scientific conclusion or calibration
  result. P4-WP02 itself adds no project archive, persistent queue, report UI,
  model registry, packaging, or acceleration behavior.
  P4-WP03 adds versioned species, kinetics, field, metric, and exporter
  interfaces behind a whole-set compatibility and explicit review-policy
  preflight. The accepted engine/campaign path remains zero-plugin; the
  packaged example is `CALIBRATION_REQUIRED` software-extension evidence, not
  biological evidence. Completed run artifacts are immutable and
  hash-verified. P4-WP04 adds a deterministic declarative registry with named
  and versioned model/parameter records, exact SI compatibility, five distinct
  provenance categories, lossless citations/uncertainty, and code-owned
  immutable audited identities. All 45 built-in values remain unresolved; a
  successful compatibility preflight is not calibration approval. The
  registry launches no simulation and does not alter existing projects, raw
  artifacts, reports, or their traceability. P4-WP05 adds a separate persistent
  local queue with deterministic priority/FIFO ordering, exact Linux CPU
  affinity and address-space limits, run-count progress, targeted cancellation,
  and stale-worker recovery. It invokes only the accepted P4-WP01 campaign
  service. Completed runs remain hash-verified and immutable; cancelled or
  interrupted unpublished runs remain explicit and retryable. Queue project
  references remain local absolute scheduler state and are deliberately not
  embedded in portable archives. P4-WP06 adds deterministic checksum-verified
  project archives with embedded hash-bound fixtures, required biological
  parameter documents, and exact completed-run artifacts/receipts, plus a
  reproducible Linux wheel-installer bundle that rejects generated research
  data. Import grants no plugin or registry trust and does not migrate queue
  state. The desktop has no
  report/plugin/registry/queue/archive UI, calibration, cloud, or automatic
  plugin-trust behavior. P4-WP07 adds a separate benchmark API with a scalar
  CPU reference and an explicitly enabled NumPy CPU feasibility candidate over
  a synthetic dimensionless 2D stencil. The fixed 2,304-value case measured
  zero divergence at `1e-12` absolute/relative engineering tolerances. Optional
  timings are raw local observations only. No benchmark backend enters model,
  campaign, queue, plugin, registry, archive, package, or GUI execution; no
  3D/GPU, production performance, or scientific-accuracy claim is made.
- P4A independently accepted the prospective schema-version 2 execution
  identity and portability. New projects bind the complete built-in registry,
  all five named/versioned model/parameter-set and parameter-source hashes, and
  the canonical explicit zero-plugin set before execution; run requests and
  completion receipts repeat that identity. New archives embed all five exact
  fixture-relative biological parameter documents and execute pending
  multi-condition campaigns from a clean wheel installation. Historical
  completed schema-version 1 projects remain byte-preserved and readable;
  missing provenance is never backfilled. Plugin code/trust, registry
  documents/trust, queue state, SI/calibration boundaries, and the isolated
  acceleration boundary remain unchanged. The rerun retraced 288 report
  observations, verified six request/receipt identities, completed the pending
  archive from an external wheel, preserved a 111-file completed project tree,
  and reproduced wheel, sdist, and installer bytes without a Critical or Major
  finding.
- P5-WP02 implements deterministic whole-set provenance for BioMesh 0.5.0
  wheel, sdist, and Linux-installer artifacts. A canonical external manifest
  binds final artifact hashes/sizes while embedded records expose the exact
  clean commit, SHA-256 source-tree identity, package version, and declared
  tool versions without Git. In-clone and installed reference bytes remain
  equal, and installed run metadata uses the embedded exact commit. This
  provides integrity/provenance only: archive authenticity/confidentiality,
  plugin isolation, installer lifecycle, and P5 acceptance remained open at
  that work-package boundary. No trust, signing algorithm, key, calibration
  status, scientific behavior, queue portability, or 3D/acceleration status
  changes.
- P5-WP03 policy 1.0.0 and envelope schema 1 authenticate exact P4 payload
  bytes with Ed25519 under explicit host-owned signer/key, validity, revocation,
  and replay policy. Optional RFC 9180 X25519/HKDF-SHA-256/AES-256-GCM HPKE
  confidentiality separately binds recipient/key and all visible security
  metadata. Legacy raw
  archives require explicit caller opt-in and persist `UNAUTHENTICATED` status.
  The inner archive, checksum inventory, execution identity, completed
  artifacts/receipts, SI/provenance and `CALIBRATION_REQUIRED` boundaries,
  zero-plugin identity, queue exclusion, and atomic P4 validation remain
  unchanged. A signature or successful decryption grants no execution,
  plugin/registry trust, sandboxing, calibration, or scientific validity.
  Private keys remain externally owned and are neither serialized nor logged.
  Host/runtime compromise, post-decryption disclosure, key custody, replay-store
  policy, and bounded resource exhaustion remain residual risks. Queue
  portability, validation, and 3D/acceleration remain P6-P8; plugin isolation
  and installer lifecycle are addressed below.
- P5-WP04 sandbox policy 1.0.0 moves every reviewed non-empty plugin operation
  behind a fresh Bubblewrap/libseccomp Linux boundary. Whole-set review and
  compatibility preflight precede code startup; read-only declared runtime
  mounts, a cleared environment, network/PID isolation, dropped capabilities,
  syscall denial, and explicit wall/CPU/address-space/message/process limits
  contain plugin code. The runtime mounts only the exact BioMesh package and
  metadata roots plus selected payload and declared dependency roots; it never
  mounts their containing site-packages. Built-in and external payload
  inventories are rechecked before each operation. Versioned request/result
  messages bind exact identities,
  validate units/provenance/shape/path/calibration boundaries, and produce
  secret-free outcome receipts before result publication. Empty selection
  starts no process and preserves the P4A core path. This does not establish
  plugin scientific validity or close host/kernel and bounded-denial-of-service
  residual risks. Queue portability, validation, and 3D/acceleration remain
  P6-P8; the installer lifecycle is addressed below.
- P5-WP05 policy/manifest schema 1 verifies exact P5-WP02 supply inputs before
  prefix mutation, inventories every candidate application, dependency,
  metadata, and launcher file, and publishes version roots side by side under
  a manifest-hash identity. Installed CLI help and offscreen GUI smoke precede
  the atomic `current` switch. Journalling recovers install, upgrade, rollback,
  and uninstall boundaries; modified state blocks unless every reported path
  is explicitly acknowledged, and changed uninstall trees are quarantined
  rather than deleted. Projects, archives, parameters, queues, reports,
  configuration, completed artifacts, research data, and source datasets
  remain outside ownership and byte-preserved. This adds no automatic updater,
  system-package integration, remote/cloud execution, queue portability, new
  UI/science, calibration, or trust grant. Host/root compromise, dependency
  availability, and distributor authenticity remain residual risks. Journal
  schema 2 binds exact source and target version, manifest, wheel, and
  provenance identities before every recovery side effect; rollback accepts
  only exact recorded states. P5A independently reproduced the rejected
  containment and recovery cases, passed the 118-test P5 collection and
  352-test complete suite, and accepted Phase 5 on 2026-08-15.
- P6-WP01 exports strict schema-version 1 queue intent only. It carries
  priority/FIFO ordered immutable campaigns, path-free fixture/registry/model/
  parameter/zero-plugin dependency identities, source project-definition
  hashes, and optional archive envelope/payload provenance. Nonblocking worker,
  queue, and project snapshots reject active, stale, missing, unsafe,
  ambiguous, incompatible, or drifted references before atomic publication.
  PID/process-start identity, locks, lifecycle/cancellation/failure state,
  local scheduler paths, and requested/applied CPU or memory policy are absent.
  Completed, failed, and cancelled history is not exported. There is no import,
  local path/resource rebinding, cross-host execution/recovery, migration/UI,
  credential transfer, trust/calibration promotion, science, or acceleration;
  those boundaries remain P6-WP02 or later where authorized.
- P6-WP02 imports only canonical compatible P6-WP01 bytes into deterministic
  `UNBOUND` records, then requires one explicit safe local project path per
  source identity plus a complete new local CPU/memory policy before producing
  `BOUND_NONRUNNABLE` records. Binding revalidates exact project definition,
  campaign, fixture, complete accepted execution/parameter identities,
  project/archive hashes, project state, artifacts, and changed-during-read
  input while holding all project locks. It creates no P4 queue, queue ID,
  enqueue counter, process/lock/lifecycle state, source resource receipt, or
  executable item. Archive/plugin/registry trust and authorization remain
  `NOT_GRANTED`, archive status remains source provenance, and calibration
  remains `CALIBRATION_REQUIRED`. Cross-host activation, execution, retry,
  recovery, concurrency, and report comparison were the P6-WP03 boundary;
  operator migration documentation remains P6-WP04.
- P6-WP03 adds explicit schema-version 1 activation of a complete local
  binding into a fresh P4 queue with new destination scheduler identity,
  atomic queue/lock/provenance publication, existing P4 resume/recovery/retry
  boundaries, and portable report traceability separated from environment
  metadata. It does not transport source process/lock/lifecycle/resource state,
  reuse completed artifacts, grant trust or authorization, or add remote
  scheduling, migration/UI, credentials, science, calibration, or acceleration.
- P6-WP04 documents the exact supported migration matrix and requires an
  archive-imported source staging queue for clean installations because P4
  archive import intentionally creates a portable project-definition hash.
  Direct intent export is bindable only when destination definition/state/
  dependency bytes and archive provenance are already identical. Dry-run and
  `migration-status` are deterministic/read-only and grant no trust,
  authorization, or calibration. P6 remains Linux-local, exact-versioned, and
  operator-mediated with no remote/cloud scheduler, automatic path/credential
  transfer, UI, or downgrade support. P6A remains required.

## Pre-v1 roadmap boundary

- `docs/10_PRE_V1_ROADMAP.md` authorizes P5 through P9 in strict order with a
  blocking independent audit after every phase. Only the first `INCOMPLETE`
  package in `docs/PHASE_STATUS.md` may execute.
- P5 addresses security and distribution hardening; P6 addresses portable
  queue intent; P7 is an evidence-gated calibration and validation program; P8
  provides separately audited 3D and acceleration work; and P9 freezes and
  audits the v1 release candidate.
- The roadmap itself adds no code, security guarantee, calibrated value,
  dataset, scientific behavior, 3D/GPU implementation, UI feature, release,
  or post-v1 authority.

## Update policy

Update this file whenever a work package completes, a remediation completes,
an audit completes, a phase is accepted, or a release tag is created. Refresh
the snapshot from the live branch, tags, test output, and the relevant
status/limitation records; do not infer unverified state.
