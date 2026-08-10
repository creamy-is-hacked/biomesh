# BioMesh P3A – Phase 3 Audit

## Purpose
Verify that the desktop workbench is reliable, responsive, scientifically faithful, and reproducible.

## Result
`PASS WITH RECORDED LIMITATIONS` (independent clean-clone rerun, 2026-08-10).

## Critical Checks

### A. Scientific isolation
- [x] GUI does not implement biological equations.
- [x] CLI and GUI match for identical config and seed.
- [x] UI preferences cannot alter scientific defaults.
- [x] P1 – Phase 1 – Core Model and P2 – Phase 2 – Colony System tests still pass.

### B. Run control
- [x] Run, pause, step, stop, checkpoint, and resume work.
- [x] Pause/step occurs at documented solver boundaries.
- [x] Resumed and uninterrupted runs match.
- [x] Cancellation leaves outputs consistent or clearly incomplete.

### C. Visualization
- [x] Cells and field layers map to stored values correctly.
- [x] Legends, units, ranges, and time are visible.
- [x] Layer toggles and opacity do not modify engine state.
- [x] Reference-scale rendering remains responsive.

### D. Configuration and inspection
- [x] Forms derive from validated schemas.
- [x] Invalid values cannot launch runs.
- [x] Parameter units and provenance are shown.
- [x] Cell inspector matches engine state.

### E. Data and errors
- [x] Saves, checkpoints, and exports round-trip.
- [x] Every run includes config, seed, commit, and environment metadata.
- [x] Worker exceptions reach the user with actionable messages.
- [x] Generated outputs remain excluded from Git.

### F. Usability and packaging
- [x] Clean clone installs and launches on supported Linux.
- [x] Keyboard navigation covers primary controls.
- [x] Minimum supported display size is usable.
- [x] User guide reproduces the reference experiment.

## Required Commands
```bash
pytest -q
pytest -q tests/gui tests/integration
QT_QPA_PLATFORM=offscreen python -m biomesh.gui --smoke-test
python -m biomesh compare-frontends parameters/phase2_reference.yaml --seed 42
python -m biomesh verify-checkpoint outputs/<run-id>
```

## Required Evidence
- Full test report.
- CLI/GUI equivalence report.
- Checkpoint verification.
- UI responsiveness measurements.
- Reference screenshots.
- Clean-clone launch log.
- Updated limitations.

## Critical Failures
- GUI changes model outcomes.
- Checkpoint resume diverges without explanation.
- Displayed values disagree with stored data.
- UI freezes during normal reference runs.
- Provenance is missing.

## Audit Record

Audited implementation commit:
`ed062935552c6a5df639c56474c7854cac91bd69`.

Auditor/date/result: Codex / 2026-08-10 /
`PASS WITH RECORDED LIMITATIONS`, using a fresh clone of pushed
`origin/phase-3-desktop-gui` and a fresh Python 3.14.4 environment. The
requested prerequisite `c2de0acfc1f025492069923f7594443b933e5acd` was verified
as an ancestor before the audit.

CLI-GUI equivalence: passed with zero byte mismatches for the manufactured
producer reference at independent seed 42. The checkpoint SHA-256 was
`43f8729cdf66afed40ef3884fc339daca49dbef37f777750ae39d2e7100ed872`.

Checkpoint result: passed; deterministic resume matched all 15 uninterrupted
application files with zero mismatches.

Responsiveness: the exact 1024x720 desktop completed the three-boundary
reference in 0.323156294063665 s while processing 239 event-loop iterations;
the maximum observed event gap was 0.023815248045139015 s.

Critical findings: none. The original audit attempt against `c2de0ac` failed
because four mandatory verification surfaces were absent. Focused remediation
at `45f1847` and `ed06293` supplied those paths and corrected the independently
reproduced display-usability blocker without changing scientific behavior.

Limitations: biological records remain SI-labelled and
`CALIBRATION_REQUIRED`; audit fixtures are manufactured software evidence;
checkpoints are hash-bound replay positions; 1024x720 may require local dock
scrolling; and no P4 feature is present.

Evidence paths: `validation/p3a/README.md`,
`validation/p3a/responsiveness.json`,
`validation/p3a/initial-1024x720.png`, and
`validation/p3a/completed-reference-1024x720.png`.

## Tag
```bash
git tag -a v0.3.1-audit -m "P3A: Phase 3 Audit"
git push origin v0.3.1-audit
```
