# BioMesh Project State

This file is the canonical snapshot of the repository's current development
state. Read it immediately after `docs/STANDARDS.md` before selecting work.
`docs/PHASE_STATUS.md` remains the authoritative ordered work-package tracker.

Snapshot verified: 2026-08-03 for the P2-WP06 completion working tree based on
`7be4178` (`P2: P2-WP05 implement waste and shear`).

| Field | Current state |
| --- | --- |
| Current phase | P2 – Phase 2 – Colony System |
| Current work package | P2-WP06 – Experiments complete; P2A is the first `INCOMPLETE` item |
| Current branch | `phase/2-colony-system` (noncanonical; the required P2 branch name is `phase-2-colony-system`) |
| Latest accepted phase | P1 – Phase 1 – Core Model, accepted by P1A on 2026-08-02 as `PASS WITH RECORDED LIMITATIONS` |
| Latest version tag | `v0.1.0` (P1 merge, 2026-08-02) |
| Current test count | 142 passed (`pytest -q`, 2026-08-03) |
| Next planned work package | P2A – Phase 2 Audit |

## Outstanding technical debt

- Align the current branch with the canonical P2 name before an accepted-phase
  handoff; do not rewrite history to do so.
- Create the canonical P1A audit tag `v0.1.1-audit` only through the approved
  accepted-audit workflow. It is not present in the repository.
- Complete the P2A audit before Phase 2 can be accepted.

## Known limitations

- Biological parameters remain configurable and `CALIBRATION_REQUIRED`; no
  calibrated biological result is claimed.
- P1's reference is a zero-duration, zero-cell, zero-solute software fixture,
  not a calibrated biological experiment.
- P2-WP06 provides a reproducible experiment harness and unresolved campaign
  definition, not calibrated biological results. It delegates the approved P2
  component update order to a typed runner, reports the continuous quorum
  response without inventing a binary threshold, and limits sensitivity
  ranking to descriptive observed sweep effects. It adds no mutation or
  evolution.
- License selection is pending.

## Update policy

Update this file whenever a work package completes, an audit completes, a
phase is accepted, or a release tag is created. Refresh the snapshot from the
live branch, tags, test output, and the relevant status/limitation records;
do not infer unverified state.
