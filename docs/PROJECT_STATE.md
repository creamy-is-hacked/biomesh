# BioMesh Project State

This file is the canonical snapshot of the repository's current development
state. Read it immediately after `docs/STANDARDS.md` before selecting work.
`docs/PHASE_STATUS.md` remains the authoritative ordered work-package tracker.

Snapshot verified: 2026-08-10 after P3-WP06 implementation and validation. P2
remains the latest audited and accepted phase at
implementation commit `6adb5def6f094762cb79ba3a2eddeede6007a2f5`; P3 is in
progress and has not been audited. The Python 3.14 full gate passes 190 tests.

| Field | Current state |
| --- | --- |
| Current phase | P3 – Phase 3 – Desktop GUI (in progress) |
| Current work package | P3A – Phase 3 Audit is the first `INCOMPLETE` item |
| Current branch | `phase-3-desktop-gui` |
| Latest accepted phase | P2 – Phase 2 – Colony System, accepted by P2A on 2026-08-08 as `PASS WITH RECORDED LIMITATIONS` |
| Latest version tag | `v0.2.1-audit` (P2A release, 2026-08-08) |
| Current test count | 190 passed (`pytest -q`, 2026-08-10) |
| Next planned work package | P3A – Phase 3 Audit |

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
  positions, and export preserves the existing completed raw artifact set.
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
  acceleration, calibration behavior, and new biology remain absent. P3
  remains unaudited.
- License selection is pending.
- The post-P3-WP04 remediation fixes BM-001, BM-002, BM-003, BM-004, BM-005,
  BM-006, and BM-007. BM-008 and BM-009 remain deferred because their required
  behavior is not established by the current contracts; BM-010 remains an
  active-development recheck item for P3A; P3-WP05 now makes its
  worker/cancellation ordering contract independently testable.

## Update policy

Update this file whenever a work package completes, a remediation completes,
an audit completes, a phase is accepted, or a release tag is created. Refresh
the snapshot from the live branch, tags, test output, and the relevant
status/limitation records; do not infer unverified state.
