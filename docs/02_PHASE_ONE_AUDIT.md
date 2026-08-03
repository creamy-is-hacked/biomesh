# BioMesh P1A – Phase 1 Audit

## Purpose
Verify that P1 – Phase 1 – Core Model is numerically correct, reproducible, traceable, and ready for P2 – Phase 2 – Colony System.

## Audit Result
`PASS WITH RECORDED LIMITATIONS` (independent rerun, 2026-08-02).

A failed critical item blocks P2 – Phase 2 – Colony System.

## Critical Checks

### A. Reproducibility
- [x] A fresh Python 3.14 virtual environment installs from the documented
      command and passes the complete gate.
- [x] Fixed seed reproduces identical outputs.
- [x] Output metadata includes the parameter file, seed, parameters, package
      and dependency versions, Git commit when available, platform, and Python
      version.
- [x] Metadata-driven reproduction reports zero byte mismatches in the recorded
      environment.
- [x] Tests pass on the supported Linux environment.

### B. Scientific traceability
- [x] Every biological parameter has units.
- [x] Every parameter has a source or `CALIBRATION_REQUIRED`.
- [x] Assumptions are documented.
- [x] No hidden defaults alter scientific behavior.

### C. Numerical verification
- [x] Pure diffusion benchmark passes.
- [x] Well-mixed growth benchmark passes.
- [x] Closed-system mass balance passes.
- [x] Grid refinement shows convergence.
- [x] Time-step refinement shows convergence.
- [x] Negative concentrations remain within tolerance only.
- [x] Global accounting includes the prescribed top-boundary transfer and zero
      transfer at periodic sides and the no-flux bottom.

### D. Cell model
- [x] Division conserves biomass.
- [x] Daughter placement is geometrically valid.
- [x] Lineage tracking is intact.
- [x] Cells remain outside the solid boundary.
- [x] Maximum overlap stays below threshold.

### E. Software quality
- [x] Core modules have tests.
- [x] Public functions are typed.
- [x] Errors are explicit and actionable.
- [x] Simulation logic is separated from visualization.
- [x] Generated data is excluded from Git by default.

## Required Audit Commands
```bash
python -m pip install -e '.[dev]'
pytest -q
python -m biomesh validate diffusion
python -m biomesh validate growth
python -m biomesh validate mass-balance
python -m biomesh run
python -m biomesh reproduce
```

The default `run` and `reproduce` commands exercise the P1-WP07 deterministic
software reference. Its biological manifest remains `CALIBRATION_REQUIRED`, so
the audit must not interpret the reference artifact as a calibrated biological
experiment. Numerical validation commands use declared manufactured or
analytical cases, not invented biological constants.

## Review Metrics
Record:

| Metric | Required value | Actual |
|---|---:|---:|
| Test failures | 0 | 0 (71 passed) |
| Mass-balance relative error | `1e-12` | `7.52623300477429e-17` |
| Maximum persistent overlap | `1e-12 m` | `0.0 m` |
| Diffusion benchmark error | `2e-3` | `6.655336877159357e-07` |
| Growth benchmark error | `1e-12 kg` | `0.0 kg` |
| Reproduction mismatch | 0 | 0 |

## Independent Audit Record — 2026-08-02

Result: `PASS WITH RECORDED LIMITATIONS`.

No Critical or Major findings remain. The current branch name is noncanonical,
and the audited worktree still requires the user-owned commit/tag handoff; Git
was intentionally not modified by this audit. All biological parameters remain
`CALIBRATION_REQUIRED`, so the reproducibility reference is a non-scientific
zero-state fixture rather than a calibrated biological experiment.

Evidence:

- Fresh Python 3.14.4 virtual environment: editable `.[dev]` install and all
  required checks passed; `pytest -q` reported 71 passed.
- Required diffusion, growth, mass-balance, run, and reproduce CLI paths passed.
- Reference reproduction reported zero byte mismatches.
- The manufactured mass-balance path reported maximum residual
  `3.8033812210791496e-16` and relative error `7.52623300477429e-17`.
- Independent 25-step accounting reported maximum residual
  `5.342948306008566e-16`; time refinement reduced error from
  `3.022994986134897e-04` to `1.4105256608698546e-04`.
- A 20,000-case independent periodic-capsule probe had maximum overlap-method
  disagreement `8.898992653882942e-13 m`; no acceptance-threshold violation
  was found.

## Failure Rules
Critical failure:
- Mass is not conserved without explanation.
- Results cannot be reproduced.
- Units are inconsistent.
- Solver instability is hidden by clamping.
- Cells cross boundaries or overlap persistently.
- Orchestration silently substitutes a number for `CALIBRATION_REQUIRED`.

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
