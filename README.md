# BioMesh

BioMesh is a scientifically grounded 2D bacterial biofilm simulator under
development and a future Linux desktop research platform.

## Status

The independent 2026-08-02 P1A – Phase 1 Audit accepted Phase 1 with recorded
limitations. Executable numerical validations, boundary-aware global
accounting, complete run provenance, and metadata-driven replay all pass. The
default reference remains deliberately a zero-state software fixture: every
biological parameter is `CALIBRATION_REQUIRED`, and no calibrated scientific
result is claimed. Phase 2 may begin; see
[the phase status](docs/PHASE_STATUS.md) for the current gate.

## Development

BioMesh uses the newest stable Python version fully supported by all required
runtime dependencies. The current resolved version is Python 3.14. In that
environment:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m biomesh --help
ruff check .
mypy src
pytest -q
```

Generated simulation output is intentionally not tracked. Project rules,
scientific conventions, and phase boundaries are in [AGENTS.md](AGENTS.md).

## License

License selection is pending.
