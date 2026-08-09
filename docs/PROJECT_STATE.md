# BioMesh Project State

This file is the canonical snapshot of the repository's current development
state. Read it immediately after `docs/STANDARDS.md` before selecting work.
`docs/PHASE_STATUS.md` remains the authoritative ordered work-package tracker.

Snapshot verified: 2026-08-08 after the independent P2A clean-clone audit
accepted P2 – Phase 2 – Colony System at implementation commit
`6adb5def6f094762cb79ba3a2eddeede6007a2f5` with recorded limitations. The
Python 3.14 full gate passes 145 tests; every required campaign and report path
reproduces byte-identically.

| Field | Current state |
| --- | --- |
| Current phase | P3 – Phase 3 – Desktop GUI (not started) |
| Current work package | P3-WP01 – Stable application API is the first `INCOMPLETE` item |
| Current branch | `main` after the accepted-audit workflow |
| Latest accepted phase | P2 – Phase 2 – Colony System, accepted by P2A on 2026-08-08 as `PASS WITH RECORDED LIMITATIONS` |
| Latest version tag | `v0.2.1-audit` (P2A release, 2026-08-08) |
| Current test count | 145 passed (`pytest -q`, 2026-08-08) |
| Next planned work package | P3-WP01 – Stable application API |

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
- License selection is pending.

## Update policy

Update this file whenever a work package completes, an audit completes, a
phase is accepted, or a release tag is created. Refresh the snapshot from the
live branch, tags, test output, and the relevant status/limitation records;
do not infer unverified state.
