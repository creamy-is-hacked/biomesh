# BioMesh P2A – Phase 2 Audit

## Purpose
Verify that communication, EPS, competition, physiological states, and detachment are correctly implemented and scientifically interpretable.

## Audit Result
`PASS WITH RECORDED LIMITATIONS` (independent clean-clone rerun, 2026-08-08).

## Critical Checks

### A. P1 – Phase 1 – Core Model preservation
- [x] P1 – Phase 1 – Core Model regression tests still pass.
- [x] Audited equations and defaults changed only with documented justification.
- [x] P1 – Phase 1 – Core Model reference runs remain reproducible.

### B. Quorum sensing
- [x] Signal diffusion-decay benchmark passes.
- [x] Hill response matches the analytical curve.
- [x] Positive feedback is optional and tested.
- [x] Activation depends on local concentration.

### C. EPS
- [x] EPS allocation has an explicit mass or resource accounting rule.
- [x] Producers pay the configured cost.
- [x] EPS changes adhesion or detachment through documented mechanics.
- [x] No visual-only EPS behavior exists.

### D. Competition
- [x] Neutral controls show no systematic strain advantage.
- [x] Producer cost is measurable in isolation.
- [x] Mixed simulations track strain-specific biomass and lineage.
- [x] Results include multiple stochastic replicates.

### E. Physiological states
- [x] Transition thresholds and delays are unit-tested.
- [x] Dormant metabolism is reduced.
- [x] Dead and detached cells are accounted for.
- [x] Population-state totals reconcile.

### F. Shear and detachment
- [x] Zero-shear control passes.
- [x] Shear-response direction is correct.
- [x] EPS protection is detectable in controlled tests.
- [x] Detached mass is included in accounting.

### G. Sensitivity and uncertainty
- [x] High-impact parameters are identified.
- [x] Calibration-required parameters are clearly marked.
- [x] Conclusions are not based on one seed.
- [x] Results distinguish robust trends from parameter-dependent outcomes.

### H. Reproducibility and release quality
- [x] Clean clone reproduces reference experiments.
- [x] Run manifests contain commit, seed, parameters, and environment.
- [x] Documentation matches current behavior.
- [x] Large generated outputs are not committed accidentally.

## Required Commands
```bash
pytest -q
python -m biomesh validate all
python -m biomesh experiment experiments/producer.yaml
python -m biomesh experiment experiments/nonproducer.yaml
python -m biomesh experiment experiments/competition_50_50.yaml
python -m biomesh sweep experiments/qs_threshold_sweep.yaml
python -m biomesh sweep experiments/eps_cost_sweep.yaml
python -m biomesh sweep experiments/shear_sweep.yaml
python -m biomesh report outputs/<campaign-id>
```

## Required Evidence
- Test report.
- Benchmark plots.
- Parameter provenance table.
- Replicate summary.
- Sensitivity ranking.
- Mass/resource accounting report.
- Known limitations.
- Clean-clone reproduction log.

## Independent Audit Record — 2026-08-08

Audited implementation commit:
`6adb5def6f094762cb79ba3a2eddeede6007a2f5`.

Auditor: Codex, using a fresh clone of `origin/phase-2-colony-system` and a
fresh Python 3.14.4 virtual environment.

Result: `PASS WITH RECORDED LIMITATIONS`.

No Critical or Major finding remains. P2A accepts P2 – Phase 2 – Colony System
at the audited implementation commit.

Evidence:

- The clean clone and its remote-tracking source both resolved exactly to the
  audited commit before the canonical `audit-phase-2` branch was created.
  Editable `.[dev]` installation succeeded in a new Python 3.14.4 environment.
- `python -m biomesh --help`, Ruff, strict mypy, `git diff --check`, and the
  full suite passed; `pytest -q` reported 145 passed. A focused rerun of the P2
  mechanism, campaign, artifact, and statistics tests reported 64 passed.
- All P1 validators passed. Diffusion error was
  `6.655336877159357e-07` against `2e-3`, refinement ratio was
  `0.23887522547268525`, growth error was `0.0 kg`, the maximum P1 accounting
  residual was `3.8033812210791496e-16`, maximum relative error was
  `7.52623300477429e-17`, maximum overlap was `0.0 m`, and reference replay
  reported zero byte mismatches. P1 parameters, references, and unchanged core
  modules match `v0.1.0`; P2 extensions preserve the P1 zero-allocation and
  unit-activity path.
- `validate all` confirmed 11 published fixtures, all 15 conditions, and fixed
  seeds 101, 202, and 303. All seven experiment paths, four sweep paths, and
  11 reports completed twice in separate output trees. All 764 resulting
  files were byte-identical.
- Independent artifact recomputation inspected 45 runs, 675 raw SHA-256/size
  records, 495 readable Parquet files, 135 NumPy field archives, 630 replicate
  statistic rows, and 168 applicable ranking rows. Means, sample variances,
  and 95% Student-t intervals were recomputed from raw observations. Every
  descriptive ranking equalled the observed between-condition mean range.
  The maximum absolute accounting residual was
  `4.199134257027165e-30`; the maximum relative accounting error was
  `2.9056583757232816e-16`.
- Application artifacts reconcile carbon, oxygen, dry biomass, EPS, quorum
  signal, waste, physiological partitions, strain biomass, lineage, and
  detached biomass. Cell-local quorum histories match the analytical Hill
  response. Controlled tests independently verify positive feedback,
  producer EPS cost, neutral competition, reduced dormant metabolism, dead
  and detached ledgers, waste accounting, increasing-shear direction, and EPS
  detachment protection.
- All 45 biological parameter records and all 10 unresolved biological
  campaign overrides are SI-labelled, provenance-complete, and
  `CALIBRATION_REQUIRED`. The 10 executable numeric fixture overrides are
  separately labelled `DERIVED` manufactured software-validation inputs and
  are not presented as calibration, biological uncertainty, or biological
  evidence.
- README, architecture, assumptions, parameter-source, limitation, and phase
  records match the executable surface and interpretation boundaries. Only
  `outputs/.gitkeep` is tracked under `outputs/`; generated campaign and
  reference artifacts remain ignored or outside the repository.

Sensitivity conclusion:

- Rankings identify only the largest observed mean ranges within each
  manufactured sweep, separately by metric and time. They are descriptive,
  use three fixed seeds, and are neither global sensitivity analysis nor
  biological uncertainty or calibration evidence. The joint resource sweep
  cannot attribute effects separately to carbon and oxygen.

Recorded limitations:

- Every biological value remains `CALIBRATION_REQUIRED`; the reference and P2
  campaigns are manufactured software validation, not scientific calibration.
- EPS is an immobile density field rather than explicit polymer mechanics.
- Shear is a deterministic uniform exposure abstraction without CFD or a
  stochastic erosion law.

Release recommendation: accept P2 and execute the canonical accepted-audit
merge and `v0.2.1-audit` tag workflow.

## Failure Rules
Critical failure:
- EPS cost is not actually charged.
- Signal activation uses global population count instead of local concentration.
- Competition conclusions rely on a single run.
- Detached or dead biomass disappears from accounting.
- P1 – Phase 1 – Core Model verification no longer passes.

Noncritical limitation:
- Simplified shear lacks full CFD.
- EPS is represented as a field rather than polymer mechanics.
- Parameters are plausible but not calibrated to a named experiment.

## Audit Report Template
```text
Audit commit:
Auditor:
Date:
Result:

Validated mechanisms:
- quorum sensing:
- EPS:
- competition:
- physiological states:
- shear/detachment:

Critical findings:
1.

Noncritical findings:
1.

Sensitivity conclusions:
1.

Recorded limitations:
1.

Release recommendation:
```

## Release Gate
Release only when:
- No critical finding remains.
- Full suite passes from a clean clone.
- Reference campaigns reproduce.
- Sensitivity results and limitations are documented.
- The audited commit is tagged.

## Tag
Recommended tag:
```bash
git tag -a v0.2.1-audit -m "P2A: Phase 2 Audit"
git push origin v0.2.1-audit
```
