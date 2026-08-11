# BioMesh P4A – Phase 4 Audit

## Purpose
Verify that BioMesh functions as an extensible, reproducible local research platform without compromising audited science.

## Result
`PASS`, `PASS WITH RECORDED LIMITATIONS`, or `FAIL`.

## Critical Checks

### A. Regression and provenance
- [ ] P1A – Phase 1 Audit, P2A – Phase 2 Audit, and P3A – Phase 3 Audit remain valid.
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
python -m biomesh --help
ruff check .
mypy src
pytest -q
git diff --check
python -m biomesh validate all
python -m biomesh validate diffusion
python -m biomesh validate growth
python -m biomesh validate mass-balance
python -m biomesh run --output outputs/p4a-p1-reference
python -m biomesh reproduce outputs/p4a-p1-reference
python -m biomesh compare-frontends parameters/phase2_reference.yaml --seed 42 \
  --output outputs/p4a-p3-reference
python -m biomesh verify-checkpoint outputs/p4a-p3-reference
QT_QPA_PLATFORM=offscreen python -m biomesh.gui --smoke-test
pytest -q tests/gui tests/integration
pytest -q tests/test_local_queue.py
python -m biomesh project create experiments/platform_reference.yaml \
  outputs/p4a-platform-reference-source
python -m biomesh campaign status \
  outputs/p4a-platform-reference-source platform-reference
python -m biomesh project export outputs/p4a-platform-reference-source \
  --output outputs/p4a-platform-reference-pending.biomesh
python -m biomesh project verify-archive \
  outputs/p4a-platform-reference-pending.biomesh
python -m biomesh project import \
  outputs/p4a-platform-reference-pending.biomesh \
  outputs/p4a-platform-reference-imported
python -m biomesh campaign resume \
  outputs/p4a-platform-reference-imported platform-reference
python -m biomesh campaign status \
  outputs/p4a-platform-reference-imported platform-reference
python -m biomesh campaign report \
  outputs/p4a-platform-reference-imported platform-reference \
  --output outputs/p4a-platform-reference-report
python -m biomesh plugins verify --output outputs/p4a-plugin-verification
python -m biomesh registry verify
python -m biomesh benchmark acceleration
python -m biomesh benchmark acceleration --experimental
python -m hatchling build --clean -d dist
```

Also execute and report all 11 accepted P2 `experiment`/`sweep` fixture paths
listed in `README.md` under new output directories. Generate each corresponding
report with `python -m biomesh report OUTPUT_DIRECTORY`.

Run archive import, campaign resume/status/report, CLI help, and the offscreen
GUI smoke path again outside the clone from the newly built wheel installation.
Use new output paths. The pending archive is intentional: completion after
import proves that every required configuration resource is archive-contained.

## Tracked reference campaign

`experiments/platform_reference.yaml` is the sole P4A platform reference. It is
a JSON-compatible, schema-version 2 project definition over the accepted
`qs_threshold_sweep.yaml` manufactured fixture. It contains two fixed
conditions and seeds 101, 202, and 303, for six deterministic runs. Every sweep
value remains SI-labelled with source, uncertainty, notes, and calibration
status; all biological parameter documents and the project remain
`CALIBRATION_REQUIRED`. This is software-validation evidence, not a biological
experiment, calibration result, or scientific conclusion.

The audit must inspect each completed `run_request.json` and completion receipt
for the exact named/versioned model and parameter-set records, complete registry
SHA-256, and canonical zero-plugin-set SHA-256. A separate independent P4A task
must execute this authority from the exact pushed remediation commit.

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
git tag -a v0.4.1-audit -m "P4A: Phase 4 Audit"
git push origin v0.4.1-audit
```
