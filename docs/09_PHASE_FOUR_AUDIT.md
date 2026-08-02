# BioMesh Phase 4 Audit

## Purpose
Verify that BioMesh functions as an extensible, reproducible local research platform without compromising audited science.

## Result
`PASS`, `PASS WITH RECORDED LIMITATIONS`, or `FAIL`.

## Critical Checks

### A. Regression and provenance
- [ ] Phase 1–3 audits remain valid.
- [ ] Completed runs are immutable and fully identified.
- [ ] Model, parameter, plugin, seed, commit, and environment versions are recorded.

### B. Campaigns and statistics
- [ ] Replicate and seed policies are correct.
- [ ] Resume/retry does not duplicate completed runs.
- [ ] Missing/failed runs remain visible.
- [ ] Reports trace every metric to source runs.

### C. Plugins and registry
- [ ] Core runs without plugins.
- [ ] Compatibility and unit checks occur before execution.
- [ ] Audited presets cannot be overwritten.
- [ ] Plugin provenance and limitations are exported.
- [ ] Untrusted plugin risk is documented.

### D. Queue and recovery
- [ ] Queue survives restart.
- [ ] Cancellation and failure preserve consistent state.
- [ ] Resource limits are enforced.
- [ ] Concurrent runs do not mix artifacts.

### E. Portability and packaging
- [ ] Project archives verify checksums.
- [ ] Clean install imports and reproduces the reference campaign.
- [ ] Package version matches manifests.
- [ ] Generated data is not bundled or committed unintentionally.

### F. Experimental acceleration
- [ ] Experimental features are disabled by default.
- [ ] CPU equivalence is measured where applicable.
- [ ] Accuracy and performance limitations are explicit.
- [ ] No 3D/GPU feature is called validated without a separate audit.

## Required Commands
```bash
pytest -q
python -m biomesh validate all
python -m biomesh campaign run experiments/platform_reference.yaml
python -m biomesh campaign verify outputs/<campaign-id>
python -m biomesh plugins verify
python -m biomesh project export outputs/<campaign-id> biomesh-reference.bmz
python -m biomesh project reproduce biomesh-reference.bmz
python -m build
```

## Required Evidence
- Regression report.
- Campaign manifest and replicate summary.
- Report-to-run traceability table.
- Plugin compatibility report.
- Queue restart test.
- Archive checksum/reproduction log.
- Clean package installation log.
- Updated threat model and limitations.

## Critical Failures
- Completed results mutate.
- Reports silently omit failures.
- Plugins bypass validation or provenance.
- Archives cannot reproduce the reference campaign.
- Packaging changes model behavior.
- Experimental results are presented as validated science.

## Audit Record
```text
Audit commit:
Auditor/date/result:
Reference campaign:
Archive reproduction:
Plugin verification:
Queue recovery:
Critical findings:
Limitations:
Release recommendation:
```

## Tag
```bash
git tag -a v0.4.0 -m "BioMesh audited reproducible research platform"
git push origin v0.4.0
```
