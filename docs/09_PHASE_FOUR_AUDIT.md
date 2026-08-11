# BioMesh P4A – Phase 4 Audit

## Purpose
Verify that BioMesh functions as an extensible, reproducible local research platform without compromising audited science.

## Result
`PASS WITH RECORDED LIMITATIONS` (independent rerun, 2026-08-11).

## Critical Checks

### A. Regression and provenance
- [x] P1A – Phase 1 Audit, P2A – Phase 2 Audit, and P3A – Phase 3 Audit remain valid.
- [x] Completed runs are immutable and fully identified.
- [x] Model, parameter, plugin, seed, commit, and environment versions are recorded.

### B. Campaigns and statistics
- [x] Replicate and seed policies are correct.
- [x] Resume/retry does not duplicate completed runs.
- [x] Missing/failed runs remain visible.
- [x] Reports trace every metric to source runs.

### C. Plugins and registry
- [x] Core runs without plugins.
- [x] Compatibility and unit checks occur before execution.
- [x] Audited presets cannot be overwritten.
- [x] Plugin provenance and limitations are exported.
- [x] Untrusted plugin risk is documented.

### D. Queue and recovery
- [x] Queue survives restart.
- [x] Cancellation and failure preserve consistent state.
- [x] Resource limits are enforced.
- [x] Concurrent runs do not mix artifacts.

### E. Portability and packaging
- [x] Project archives verify checksums.
- [x] Clean install imports and reproduces the reference campaign.
- [x] Package version matches manifests.
- [x] Generated data is not bundled or committed unintentionally.

### F. Experimental acceleration
- [x] Experimental features are disabled by default.
- [x] CPU equivalence is measured where applicable.
- [x] Accuracy and performance limitations are explicit.
- [x] No 3D/GPU feature is called validated without a separate audit.

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

Audit prerequisite commit:
`b5bb3cf8ce12e67f6d80048aab2545e89bfcabe4`, verified as the exact pushed
`origin/phase-4-research-platform` tip before creating `audit-phase-4`.

Auditor/date/result: Codex / 2026-08-11 /
`PASS WITH RECORDED LIMITATIONS`, using a clean independent worktree, a fresh
Python 3.14.4 environment, and new external wheel, sdist, and installer
locations.

Reference campaign: the tracked SHA-256
`5fc03a16d48c454d678b3f1f55cac57db297900277059e845281a65c85acbe2c`
definition expanded to both conditions at seeds 101, 202, and 303. All six
runs completed. Their six requests and six schema-version 2 receipts carried
the same five-model execution identity
`cd8515f0a4aa59b3bf63985c4db423a2ce5f8c589e1d9e4f0e70564303a00a22`
and explicit empty-plugin-set identity
`1919457d222318dd73626ea9b92a26b0697d1b96230dff5ed254842ca9b310a0`.

Archive reproduction: the strict eight-file pending inventory contained the
fixture and all five exact parameter resources and reproduced at
`ed10fa93f1fa07dc4c515804908d35cc756f4133b73bbbc727f99a174edf1f0d`.
A clean installed wheel completed it outside the clone. The resulting
110-file completed archive reproduced at
`3795db669511cf04c67964aba65ca756475e6c0d6a3751a8c270601574844c37`;
completed export/import preserved the entire 111-file project tree exactly.
Real CLI probes rejected both checksum corruption and path traversal.

Report traceability: all 288 observations were independently retraced to raw
artifact SHA-256, size, Parquet row, column, and value. Coverage contained all
six completed runs, 96 condition summaries, 48 pairwise comparisons, and no
missing run.

Plugin and registry verification: zero-plugin core behavior, reviewed example
provenance, incompatible/unreviewed pre-load rejection, exact SI compatibility,
five immutable built-in parameter sets, and all 45 unresolved parameter
boundaries passed. Plugin code/trust, registry data/trust, and queue state were
absent from the portable inventory.

Queue recovery: priority/FIFO restart ordering, exact Linux CPU/address-space
receipts, queued and running cancellation, single-worker exclusion, retry, and
stale-worker recovery passed while preserving completed bytes.

Distribution evidence: repeated wheel, sdist, and Linux installer bytes were
identical at SHA-256
`12e69544f3e145b1c184ec8b1993574b1d799b780b256d7e9cccac65b1bceffb`,
`c70ca7459a6c440b26f14729f995385ae4b22e31af160c404e0660f94866424f`,
and `4ff5aedc298640d27b66ca46acb89ef57b78386142099489752bfecc22eff69d`.
Fresh wheel and sdist application paths and the checksum-verified installer
CLI/GUI paths passed outside the clone.

Critical findings: none. `P4A-001`, `P4A-002`, and `P4A-003` are closed by
direct independent evidence. Historical completed schema-version 1 results
remained readable and byte-unchanged; unfinished legacy execution and
provenance backfilling failed explicitly.

Recorded limitations: all biological values remain `CALIBRATION_REQUIRED`;
the platform reference is manufactured software-validation evidence only;
approved Python plugins are reviewed but not sandboxed; archives detect
corruption but are not signed or confidential; queue state remains local;
the Linux installer has the documented update/rollback limitations; and the
experimental candidate remains an isolated CPU-only 2D synthetic feasibility
path with no performance, GPU, 3D, scientific-accuracy, or biological claim.
An installed wheel records `UNKNOWN` when Git metadata is unavailable; the
audited wheel SHA-256 and package/dependency/environment versions identify that
external execution, while exact Git provenance remains available in clone
executions.

Release recommendation: accept P4 and execute the canonical `audit-phase-4`
merge and `v0.4.1-audit` tag workflow.

## Tag
```bash
git tag -a v0.4.1-audit -m "P4A: Phase 4 Audit"
git push origin v0.4.1-audit
```
