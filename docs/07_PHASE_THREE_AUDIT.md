# BioMesh Phase 3 Audit

## Purpose
Verify that the desktop workbench is reliable, responsive, scientifically faithful, and reproducible.

## Result
`PASS`, `PASS WITH RECORDED LIMITATIONS`, or `FAIL`.

## Critical Checks

### A. Scientific isolation
- [ ] GUI does not implement biological equations.
- [ ] CLI and GUI match for identical config and seed.
- [ ] UI preferences cannot alter scientific defaults.
- [ ] Phase 1–2 tests still pass.

### B. Run control
- [ ] Run, pause, step, stop, checkpoint, and resume work.
- [ ] Pause/step occurs at documented solver boundaries.
- [ ] Resumed and uninterrupted runs match.
- [ ] Cancellation leaves outputs consistent or clearly incomplete.

### C. Visualization
- [ ] Cells and field layers map to stored values correctly.
- [ ] Legends, units, ranges, and time are visible.
- [ ] Layer toggles and opacity do not modify engine state.
- [ ] Reference-scale rendering remains responsive.

### D. Configuration and inspection
- [ ] Forms derive from validated schemas.
- [ ] Invalid values cannot launch runs.
- [ ] Parameter units and provenance are shown.
- [ ] Cell inspector matches engine state.

### E. Data and errors
- [ ] Saves, checkpoints, and exports round-trip.
- [ ] Every run includes config, seed, commit, and environment metadata.
- [ ] Worker exceptions reach the user with actionable messages.
- [ ] Generated outputs remain excluded from Git.

### F. Usability and packaging
- [ ] Clean clone installs and launches on supported Linux.
- [ ] Keyboard navigation covers primary controls.
- [ ] Minimum supported display size is usable.
- [ ] User guide reproduces the reference experiment.

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
```text
Audit commit:
Auditor/date/result:
CLI-GUI equivalence:
Checkpoint result:
Responsiveness:
Critical findings:
Limitations:
Evidence paths:
```

## Tag
```bash
git tag -a v0.3.0 -m "BioMesh audited desktop scientific workbench"
git push origin v0.3.0
```
