# BioMesh

BioMesh is a planned, scientifically grounded 2D bacterial biofilm simulator
and future Linux desktop research platform.

## Status

M0 – Repository Bootstrap provides repository tooling, documentation contracts,
a package shell, and continuous integration. No biological or numerical model
is implemented yet. See [the phase status](docs/PHASE_STATUS.md) for the
current gate.

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
