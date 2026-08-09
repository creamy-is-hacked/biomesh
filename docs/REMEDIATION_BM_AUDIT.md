# BioMesh repository remediation record

## Scope

This record covers the dedicated remediation pass performed after the clean,
synchronized P3-WP04 baseline `107ad180fe73c65a350de592ec86896240e07704`.
It does not reinterpret P3-WP04 and does not authorize P3-WP05, P3-WP06, or
P3A.

## Finding disposition

| Finding | Disposition | Evidence |
| --- | --- | --- |
| BM-001 | FIXED | Strict finite/nonnegative SoluteField state and candidate-update regressions. |
| BM-002 | FIXED | Safe condition IDs, staged campaign roots, resolved containment, and symlink rejection. |
| BM-003 | FIXED | Hatch wheel/sdist force-includes versioned experiment and parameter resources. |
| BM-004 | FIXED | Atomic sibling-file/directory publication for artifacts, checkpoints, exports, and reports, with retry regressions. |
| BM-005 | FIXED | Python 3.14 CI coverage for version, CLI/GUI entry points, validate-all, GUI smoke, wheel/sdist install, and external cwd. |
| BM-006 | FIXED | RunMetadata accepts only canonical lowercase 64-character SHA-256 text. |
| BM-007 | FIXED | `v0.1.1-audit` identifies accepted P1A commit `c540e9b0a3b304cbb99f215dc911793bfd86b6d3`. |
| BM-008 | DEFERRED | Current contracts do not establish the required behavior; implementation would invent policy. |
| BM-009 | DEFERRED | Current contracts do not establish the required behavior; implementation would invent policy. |
| BM-010 | ACTIVE DEVELOPMENT – RECHECK | No P3 worker/cancellation implementation exists, so ordering is not testable. |

## Verification

- Python 3.14.4: `pytest -q` — 183 passed.
- `ruff check .` — passed.
- `mypy src` — passed in strict mode.
- `python -m biomesh --help`, `python -m biomesh --version`,
  `biomesh-gui --version`, and offscreen GUI smoke — passed.
- `python -m biomesh validate all` — passed for 11 fixtures and 15 conditions.
- `git diff --check` — passed.
- Wheel and sdist built successfully. Each artifact was installed into a
  separate external prefix and exercised from an external working directory
  with `validate all`, a packaged producer fixture, versioned entry points,
  and offscreen GUI startup using the already verified local Python 3.14
  dependency environment.
- A network-isolated attempt at a fully dependency-resolving clean install
  could not reach the package index. The CI workflow performs that check in
  its normal network-enabled runner.

## Boundary

P3 remains unaudited. The first normal next package remains
`P3-WP05 – Controls, checkpoints, and inspection`.
