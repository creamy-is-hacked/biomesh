# BioMesh Project State

This file is the canonical snapshot of the repository's current development
state. Read it immediately after `docs/STANDARDS.md` before selecting work.
`docs/PHASE_STATUS.md` remains the authoritative ordered work-package tracker.

Snapshot verified: 2026-08-03 after the P2-WP06 remediation commit `8ac6551`;
a clean Python 3.14 editable-install clone reproduced its fixture path and all
144 tests. The historical independent P2A failure was against `d0c80c5`.

| Field | Current state |
| --- | --- |
| Current phase | P2 – Phase 2 – Colony System |
| Current work package | P2-WP06 – Experiments is `COMPLETE`; P2A is the first `INCOMPLETE` item and must rerun independently |
| Current branch | `phase/2-colony-system` (noncanonical; the required P2 branch name is `phase-2-colony-system`) |
| Latest accepted phase | P1 – Phase 1 – Core Model, accepted by P1A on 2026-08-02 as `PASS WITH RECORDED LIMITATIONS` |
| Latest version tag | `v0.1.0` (P1 merge, 2026-08-02) |
| Current test count | 144 passed (`pytest -q`, 2026-08-03) |
| Next planned work package | P2A – Phase 2 Audit |

## Outstanding technical debt

- Align the current branch with the canonical P2 name before an accepted-phase
  handoff; do not rewrite history to do so.
- Create the canonical P1A audit tag `v0.1.1-audit` only through the approved
  accepted-audit workflow. It is not present in the repository.
- Rerun P2A independently against the P2-WP06 remediation; do not infer audit
  acceptance from implementation-path evidence.

## Known limitations

- Biological parameters remain configurable and `CALIBRATION_REQUIRED`; no
  calibrated biological result is claimed.
- P1's reference is a zero-duration, zero-cell, zero-solute software fixture,
  not a calibrated biological experiment.
- P2-WP06 supplies a deterministic campaign adapter and required CLI surface
  using manufactured SI-labelled software-validation fixtures. Existing
  biological records remain provenance-complete and `CALIBRATION_REQUIRED`;
  fixtures and their outputs are not calibration or biological evidence. P2A
  has not independently revalidated this remediation, despite clean-clone
  application-path reproduction. It adds no mutation or evolution.
- License selection is pending.

## Update policy

Update this file whenever a work package completes, an audit completes, a
phase is accepted, or a release tag is created. Refresh the snapshot from the
live branch, tags, test output, and the relevant status/limitation records;
do not infer unverified state.
