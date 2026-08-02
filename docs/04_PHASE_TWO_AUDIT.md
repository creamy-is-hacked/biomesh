# BioMesh Phase 2 Audit

## Purpose
Verify that communication, EPS, competition, physiological states, and detachment are correctly implemented and scientifically interpretable.

## Audit Result
Choose one:
- `PASS`
- `PASS WITH RECORDED LIMITATIONS`
- `FAIL`

## Critical Checks

### A. Phase 1 preservation
- [ ] Phase 1 regression tests still pass.
- [ ] Audited equations and defaults changed only with documented justification.
- [ ] Phase 1 reference runs remain reproducible.

### B. Quorum sensing
- [ ] Signal diffusion-decay benchmark passes.
- [ ] Hill response matches the analytical curve.
- [ ] Positive feedback is optional and tested.
- [ ] Activation depends on local concentration.

### C. EPS
- [ ] EPS allocation has an explicit mass or resource accounting rule.
- [ ] Producers pay the configured cost.
- [ ] EPS changes adhesion or detachment through documented mechanics.
- [ ] No visual-only EPS behavior exists.

### D. Competition
- [ ] Neutral controls show no systematic strain advantage.
- [ ] Producer cost is measurable in isolation.
- [ ] Mixed simulations track strain-specific biomass and lineage.
- [ ] Results include multiple stochastic replicates.

### E. Physiological states
- [ ] Transition thresholds and delays are unit-tested.
- [ ] Dormant metabolism is reduced.
- [ ] Dead and detached cells are accounted for.
- [ ] Population-state totals reconcile.

### F. Shear and detachment
- [ ] Zero-shear control passes.
- [ ] Shear-response direction is correct.
- [ ] EPS protection is detectable in controlled tests.
- [ ] Detached mass is included in accounting.

### G. Sensitivity and uncertainty
- [ ] High-impact parameters are identified.
- [ ] Calibration-required parameters are clearly marked.
- [ ] Conclusions are not based on one seed.
- [ ] Results distinguish robust trends from parameter-dependent outcomes.

### H. Reproducibility and release quality
- [ ] Clean clone reproduces reference experiments.
- [ ] Run manifests contain commit, seed, parameters, and environment.
- [ ] Documentation matches current behavior.
- [ ] Large generated outputs are not committed accidentally.

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

## Failure Rules
Critical failure:
- EPS cost is not actually charged.
- Signal activation uses global population count instead of local concentration.
- Competition conclusions rely on a single run.
- Detached or dead biomass disappears from accounting.
- Phase 1 verification no longer passes.

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
git tag -a v0.2.0 -m "BioMesh audited quorum, EPS, and competition model"
git push origin v0.2.0
```
