# BioMesh

BioMesh is a scientifically grounded 2D bacterial biofilm simulator under
development and a future Linux desktop research platform.

## Status

The independent 2026-08-08 P2A – Phase 2 Audit accepted Phase 2 with recorded
limitations. P3 – Phase 3 – Desktop GUI has not started; P3-WP01 is the next
work package. The default P1 reference and all published P2 fixtures are
manufactured software-validation evidence: every biological parameter remains
`CALIBRATION_REQUIRED`, and no calibrated scientific result is claimed. See
[the phase status](docs/PHASE_STATUS.md) for the current state.

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

The P2 command surface validates the published fixture set, runs seven
experiment paths and four sweep paths, and renders one report per campaign:

```bash
python -m biomesh validate all
python -m biomesh experiment experiments/producer.yaml
python -m biomesh experiment experiments/nonproducer.yaml
python -m biomesh experiment experiments/competition_50_50.yaml
python -m biomesh experiment experiments/inoculation_intermixed.yaml
python -m biomesh experiment experiments/inoculation_segregated.yaml
python -m biomesh experiment experiments/eps_constitutive.yaml
python -m biomesh experiment experiments/eps_quorum_controlled.yaml
python -m biomesh sweep experiments/qs_threshold_sweep.yaml
python -m biomesh sweep experiments/nutrient_oxygen_sweep.yaml
python -m biomesh sweep experiments/eps_cost_sweep.yaml
python -m biomesh sweep experiments/shear_sweep.yaml
python -m biomesh report outputs/<campaign-directory>
```

Each published condition runs at fixed seeds 101, 202, and 303. Generated
Parquet, NumPy, manifest, statistical, ranking, and PNG artifacts are release
reproducibility evidence only; they are not biological calibration.

Generated simulation output is intentionally not tracked. Project rules,
scientific conventions, and phase boundaries are in [AGENTS.md](AGENTS.md).

## License

License selection is pending.
