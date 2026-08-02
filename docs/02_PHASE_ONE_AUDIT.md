# BioMesh P1A – Phase 1 Audit

## Purpose
Verify that P1 – Phase 1 – Core Model is numerically correct, reproducible, traceable, and ready for P2 – Phase 2 – Colony System.

## Audit Result
Choose one:
- `PASS`
- `PASS WITH RECORDED LIMITATIONS`
- `FAIL`

A failed critical item blocks P2 – Phase 2 – Colony System.

## Critical Checks

### A. Reproducibility
- [ ] Clean clone installs from documented commands.
- [ ] Fixed seed reproduces identical outputs.
- [ ] Output metadata includes seed, parameters, package version, and commit hash.
- [ ] Tests pass on the supported Linux environment.

### B. Scientific traceability
- [ ] Every biological parameter has units.
- [ ] Every parameter has a source or `CALIBRATION_REQUIRED`.
- [ ] Assumptions are documented.
- [ ] No hidden defaults alter scientific behavior.

### C. Numerical verification
- [ ] Pure diffusion benchmark passes.
- [ ] Well-mixed growth benchmark passes.
- [ ] Closed-system mass balance passes.
- [ ] Grid refinement shows convergence.
- [ ] Time-step refinement shows convergence.
- [ ] Negative concentrations remain within tolerance only.

### D. Cell model
- [ ] Division conserves biomass.
- [ ] Daughter placement is geometrically valid.
- [ ] Lineage tracking is intact.
- [ ] Cells remain outside the solid boundary.
- [ ] Maximum overlap stays below threshold.

### E. Software quality
- [ ] Core modules have tests.
- [ ] Public functions are typed.
- [ ] Errors are explicit and actionable.
- [ ] Simulation logic is separated from visualization.
- [ ] Generated data is excluded from Git by default.

## Required Audit Commands
```bash
python -m pip install -e '.[dev]'
pytest -q
python -m biomesh validate diffusion
python -m biomesh validate growth
python -m biomesh validate mass-balance
python -m biomesh run parameters/phase1_reference.yaml --seed 42
python -m biomesh reproduce outputs/<run-id>
```

## Review Metrics
Record:

| Metric | Required value | Actual |
|---|---:|---:|
| Test failures | 0 | |
| Mass-balance relative error | configured tolerance | |
| Maximum persistent overlap | configured tolerance | |
| Diffusion benchmark error | configured tolerance | |
| Growth benchmark error | configured tolerance | |
| Reproduction mismatch | 0 | |

## Failure Rules
Critical failure:
- Mass is not conserved without explanation.
- Results cannot be reproduced.
- Units are inconsistent.
- Solver instability is hidden by clamping.
- Cells cross boundaries or overlap persistently.

Noncritical limitation:
- Performance is slow but correct.
- Visualization is minimal.
- Some parameters remain explicitly uncalibrated.

## Audit Report Template
```text
Audit commit:
Auditor:
Date:
Result:

Critical findings:
1.

Noncritical findings:
1.

Required fixes:
1.

Recorded limitations:
1.

Evidence paths:
- test report:
- benchmark outputs:
- parameter manifest:
```

## Audit Fix Cycle
1. Create issue for each failed item.
2. Fix on the P1 – Phase 1 – Core Model branch, `phase-1-core-model`.
3. Add or strengthen a regression test.
4. Re-run only affected checks, then the full suite.
5. Update the audit report.
6. Repeat until no critical failures remain.

## Phase Gate
P2 – Phase 2 – Colony System may start only when:
- Audit result is `PASS` or `PASS WITH RECORDED LIMITATIONS`.
- All critical checks pass.
- Limitations are documented in `LIMITATIONS.md`.
- The audited commit is tagged.

## Tag
Recommended tag:
```bash
git tag -a v0.1.1-audit -m "P1A: Phase 1 Audit"
git push origin v0.1.1-audit
```
