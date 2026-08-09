# BioMesh Project State

This file is the canonical snapshot of the repository's current development
state. Read it immediately after `docs/STANDARDS.md` before selecting work.
`docs/PHASE_STATUS.md` remains the authoritative ordered work-package tracker.

Snapshot verified: 2026-08-09 after P3-WP01 completed its local acceptance
gate. P2 remains the latest audited and accepted phase at implementation commit
`6adb5def6f094762cb79ba3a2eddeede6007a2f5`; P3 is in progress and has not been
audited. The Python 3.14 full gate passes 151 tests.

| Field | Current state |
| --- | --- |
| Current phase | P3 – Phase 3 – Desktop GUI (in progress) |
| Current work package | P3-WP02 – Desktop shell is the first `INCOMPLETE` item |
| Current branch | `phase-3-desktop-gui` |
| Latest accepted phase | P2 – Phase 2 – Colony System, accepted by P2A on 2026-08-08 as `PASS WITH RECORDED LIMITATIONS` |
| Latest version tag | `v0.2.1-audit` (P2A release, 2026-08-08) |
| Current test count | 151 passed (`pytest -q`, 2026-08-09) |
| Next planned work package | P3-WP02 – Desktop shell |

## Outstanding technical debt

- Create the canonical P1A audit tag `v0.1.1-audit` only through the approved
  accepted-audit workflow. It is not present in the repository.

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
  P3 remains unaudited, and no desktop shell or later P3 behavior is present.
- License selection is pending.

## Update policy

Update this file whenever a work package completes, an audit completes, a
phase is accepted, or a release tag is created. Refresh the snapshot from the
live branch, tags, test output, and the relevant status/limitation records;
do not infer unverified state.
