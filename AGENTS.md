## BioMesh repository rules

- M0 – Repository Bootstrap contains only repository infrastructure; do not add scientific behavior
  before the applicable approved work package.
- Use the newest stable Python version fully supported by every required runtime
  dependency. The current resolved version is Python 3.14; do not change it
  without reporting a compatibility issue and recommending the newest fully
  supported version. Run `python -m biomesh --help`, `ruff check .`, `mypy src`,
  and `pytest -q` before declaring a package complete.
- Use SI units internally. Record the unit, source, uncertainty, notes, and
  calibration status for every biological parameter.
- Never invent biological constants, citations, calibration results, or
  benchmark outcomes. Unknown values are `CALIBRATION_REQUIRED`.
- Write focused tests before or alongside every feature. Preserve deterministic
  behavior when a feature introduces stochasticity.
- Prefer explicit validation errors to silent correction, coercion, clamping,
  or fallback behavior.
- Keep modules small, typed, and directed from interfaces to lower-level
  utilities; avoid importing future model components into current code.
- Update `CHANGELOG.md` and `docs/PHASE_STATUS.md` with validation evidence at
  each completed work package. Never commit, push, merge, tag, or release.

## Phase boundary

P1 – Phase 1 – Core Model is specified in `docs/01_PHASE_ONE_CORE_MODEL.md`.
M0 – Repository Bootstrap uses branch `m0-repository-bootstrap` and must be
reviewed and committed manually with the `M0:` prefix before P1 begins.
