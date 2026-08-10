# P3A independent audit evidence

P3A independently audited pushed implementation commit
`ed062935552c6a5df639c56474c7854cac91bd69` from a fresh clone of
`origin/phase-3-desktop-gui` on 2026-08-10. The prerequisite
`c2de0acfc1f025492069923f7594443b933e5acd` is an ancestor of that commit.
The result is `PASS WITH RECORDED LIMITATIONS`; no Critical or Major finding
remains.

## Mandatory command evidence

All commands ran in document order in a fresh Python 3.14.4 environment:

| Command | Result |
| --- | --- |
| `pytest -q` | 195 passed in 21.90 s |
| `pytest -q tests/gui tests/integration` | 2 passed |
| `QT_QPA_PLATFORM=offscreen python -m biomesh.gui --smoke-test` | exit 0 |
| `python -m biomesh compare-frontends parameters/phase2_reference.yaml --seed 42` | passed; 0 mismatches; `CALIBRATION_REQUIRED` |
| `python -m biomesh verify-checkpoint outputs/p3a-reference-seed-42` | passed; 15 files; 0 mismatches |

The checkpoint SHA-256 was
`43f8729cdf66afed40ef3884fc339daca49dbef37f777750ae39d2e7100ed872`.
The selector, fixture, and five biological parameter hashes were retained
separately; seed 42 is manufactured deterministic audit input, not biological
evidence or a published desktop seed.

## Complete and direct-path evidence

- `ruff check .`, `mypy src`, `git diff --check`, and
  `python -m biomesh --help` passed. Mypy reported no issues in 37 source
  files.
- A focused P3 application/GUI rerun passed 26 tests. Direct offscreen probes
  exercised the real window, controls, editor, viewer, inspector, worker,
  analytics, cancellation, error propagation, canonical export, and package
  application paths.
- P1 diffusion, growth, mass-balance, reference generation, and byte replay
  passed. Diffusion error was `6.655336877159357e-07`, refinement ratio was
  `0.23887522547268525`, growth error was `0.0 kg`, maximum accounting residual
  was `3.8033812210791496e-16`, maximum relative error was
  `7.52623300477429e-17`, and replay had zero mismatches.
- `validate all` retained all 11 P2 fixtures, 15 conditions, and fixed
  published seeds 101, 202, and 303. No calibration claim was introduced.
- The integrated export contained exact CSV/Parquet analytics, eight PNG plots,
  three canonical NumPy field snapshots, 11 canonical Parquet tables, and
  canonical run metadata. Its manifest recorded seed 101, implementation
  commit, configuration and biological-parameter hashes, Python/platform and
  dependency versions, SI metric units, and `CALIBRATION_REQUIRED`.
- Fresh external Python 3.14.4 environments installed both the wheel and sdist,
  launched GUI smoke from outside the repository, reproduced zero frontend
  mismatches, and verified all 15 checkpoint files. The built wheel SHA-256 was
  `b9c13d5965cd4fe06aed529fca85b4caf1f6069716271b3f46bf0e9b7cf86185`;
  the sdist SHA-256 was
  `73bd4528a03609681f8514c142209e0e85396e6a827c89f678c2eba07e3be07f`.
- Static GUI dependency inspection found no biological equation implementation
  in `src/biomesh/gui`; the GUI consumes immutable public application records
  and delegates execution/export to the application service.
- Generated run, package, and probe outputs remained ignored. Only this audit
  record and the two reference screenshots are retained under `validation/`.

## Responsiveness and display evidence

The real composed window was rendered at the exact supported 1024x720 display
size. Its minimum size hint was 592x532. During a normal manufactured reference
run, the event loop completed 239 processing iterations with a maximum observed
gap of 0.023815248045139015 s; the three-boundary run completed in
0.323156294063665 s and produced four immutable snapshots. Explicit keyboard
focus traversal covered the primary controls in idle, running, and paused
states.

Screenshots:

- `initial-1024x720.png`, SHA-256
  `24d7a87ddb1a8b1b6c21cce557bd0fb853c10893875bb33d35ab840d9a5ca849`
- `completed-reference-1024x720.png`, SHA-256
  `32c8eac1cfdc55053e7d2dc97ac67e37dca1d30d99303826e65613b474b5f663`

## Recorded limitations

- Every biological parameter remains configurable, SI-labelled,
  provenance-complete, and `CALIBRATION_REQUIRED`; all executable audit inputs
  are manufactured software-validation fixtures, not biological evidence.
- Checkpoints are hash-bound deterministic replay positions, not serialized
  mutable solver state.
- At 1024x720, rich dock content can require local scrolling; smaller displays
  are unsupported.
- P3 intentionally provides no P4 project/campaign model, persistent queue,
  plugin system, acceleration boundary, or calibration behavior.
