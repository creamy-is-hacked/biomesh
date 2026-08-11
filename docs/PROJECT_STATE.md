# BioMesh Project State

This file is the canonical snapshot of the repository's current development
state. Read it immediately after `docs/STANDARDS.md` before selecting work.
`docs/PHASE_STATUS.md` remains the authoritative ordered work-package tracker.

Snapshot verified: 2026-08-11 after P4A production remediation validation on
the Phase 4 branch.
P3 remains the latest audited and accepted phase at accepted main commit
`ae67b3fb86e61cd75d373d790decdd4008bd3313` and tag `v0.3.1-audit`. The Python
3.14 full gate passes 244 tests.

| Field | Current state |
| --- | --- |
| Current phase | P4 – Phase 4 – Research Platform (in progress) |
| Current work package | P4-WP07 is `COMPLETE`; failed P4A findings have production remediations, but P4A remains the first `INCOMPLETE` item pending an independent rerun |
| Current branch | `phase-4-research-platform` |
| Latest accepted phase | P3 – Phase 3 – Desktop GUI, accepted by P3A on 2026-08-10 as `PASS WITH RECORDED LIMITATIONS` |
| Latest version tag | `v0.3.1-audit` (P3A release, 2026-08-10) |
| Current test count | 244 passed (`pytest -q`, 2026-08-11) |
| Next planned work package | Independent P4A – Phase 4 Audit rerun from the exact pushed remediation commit |

## Outstanding technical debt

- License selection is pending; no license was added by this remediation pass.

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
  3D/GPU, production performance, scientific accuracy, or P4A result is
  claimed.
- P4A production remediation adds prospective schema-version 2 execution
  identity and portability. New projects bind the complete built-in registry,
  all five named/versioned model/parameter-set and parameter-source hashes, and
  the canonical explicit zero-plugin set before execution; run requests and
  completion receipts repeat that identity. New archives embed all five exact
  fixture-relative biological parameter documents and execute pending
  multi-condition campaigns from a clean wheel installation. Historical
  completed schema-version 1 projects remain byte-preserved and readable;
  missing provenance is never backfilled. Plugin code/trust, registry
  documents/trust, queue state, SI/calibration boundaries, and the isolated
  acceleration boundary remain unchanged. P4A is not accepted by this
  remediation.

## Update policy

Update this file whenever a work package completes, a remediation completes,
an audit completes, a phase is accepted, or a release tag is created. Refresh
the snapshot from the live branch, tags, test output, and the relevant
status/limitation records; do not infer unverified state.
