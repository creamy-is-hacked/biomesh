# BioMesh Project State

This file is the canonical snapshot of the repository's current development
state. Read it immediately after `docs/STANDARDS.md` before selecting work.
`docs/PHASE_STATUS.md` remains the authoritative ordered work-package tracker.

Snapshot verified: 2026-08-03 for the P2-WP04 completion working tree based on
`38a6e83` (`DOCS: Standardize autonomous Git workflow`).

| Field | Current state |
| --- | --- |
| Current phase | P2 – Phase 2 – Colony System |
| Current work package | P2-WP04 – Physiological states complete; P2-WP05 is the first `INCOMPLETE` package |
| Current branch | `phase/2-colony-system` (noncanonical; the required P2 branch name is `phase-2-colony-system`) |
| Latest accepted phase | P1 – Phase 1 – Core Model, accepted by P1A on 2026-08-02 as `PASS WITH RECORDED LIMITATIONS` |
| Latest version tag | `v0.1.0` (P1 merge, 2026-08-02) |
| Current test count | 127 passed (`pytest -q`, 2026-08-03) |
| Next planned work package | P2-WP05 – Waste and shear |

## Outstanding technical debt

- Align the current branch with the canonical P2 name before an accepted-phase
  handoff; do not rewrite history to do so.
- Create the canonical P1A audit tag `v0.1.1-audit` only through the approved
  accepted-audit workflow. It is not present in the repository.
- Complete the remaining P2 work packages (P2-WP05 through P2-WP06) and the
  P2A audit before Phase 2 can be accepted.

## Known limitations

- Biological parameters remain configurable and `CALIBRATION_REQUIRED`; no
  calibrated biological result is claimed.
- P1's reference is a zero-duration, zero-cell, zero-solute software fixture,
  not a calibrated biological experiment.
- P2-WP04 is component-level and optional-output integration. It adds no waste,
  shear, detachment probability or force, replicated experiments, sensitivity
  analysis, mutation, or evolution. Physiological inputs remain
  `CALIBRATION_REQUIRED`.
- License selection is pending.

## Update policy

Update this file whenever a work package completes, an audit completes, a
phase is accepted, or a release tag is created. Refresh the snapshot from the
live branch, tags, test output, and the relevant status/limitation records;
do not infer unverified state.
