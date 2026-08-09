# BioMesh

BioMesh is a deterministic, 2D bacterial biofilm simulation platform under
development. It combines a configurable scientific-model core with
reproducible validation and experiment-fixture workflows, and is being shaped
into a Linux desktop research platform.

## Current status

The latest accepted phase is **P2 – Phase 2 – Colony System**. Its independent
2026-08-08 audit passed with recorded limitations and is represented by the
`v0.2.1-audit` tag. **P3 – Phase 3 – Desktop GUI** is in progress: P3-WP01,
the stable headless application API, is complete locally, and P3-WP02 – Desktop
shell is complete locally. P3-WP03 – Simulation viewer is next. P3 has not
been audited.

The current desktop GUI is shell-only: menus, docks, status, recent project
references, an error console, and separate UI preferences. Its central viewer
area is intentionally a placeholder. The application API remains synchronous
and controls the existing manufactured P2 fixture path independently.

See [the authoritative phase tracker](docs/PHASE_STATUS.md) and the
[current project state](docs/PROJECT_STATE.md) for the live status.

## What is implemented

The repository currently provides:

- a configurable P1 core for carbon and oxygen finite-volume fields, capsule
  cells, metabolism, mechanics, accounting, deterministic outputs, and replay;
- P2 colony-system components for quorum signal, EPS, producer/nonproducer
  competition, physiological states, waste, and simplified shear exposure;
- strict experiment and sweep fixtures with fixed seeds, provenance manifests,
  raw Parquet/NumPy artifacts, replicate statistics, descriptive rankings, and
  report plots;
- CLI validation, reference-run reproduction, experiment/sweep execution, and
  campaign reporting;
- the P3-WP01 typed, synchronous application-service boundary for run, pause,
  step, checkpoint/resume, inspection, snapshots, and canonical export; and
- the P3-WP02 PySide6 desktop shell with menus, dockable project/error panels,
  status reporting, recent file references, and UI-only XDG preferences.

These are software capabilities and reproducibility contracts. They do not by
themselves establish that the model is biologically calibrated or experimentally
validated.

## Validation and scientific scope

The P1 and P2 independent audits accepted the implemented software paths with
recorded limitations. The repository verifies deterministic behavior,
validation cases, accounting, provenance, artifact schemas, and byte-identical
replay for the published fixture workflows.

All biological values remain configurable and `CALIBRATION_REQUIRED`. The
reference run and published P2 fixtures are manufactured software-validation
inputs, not biological calibration data or experimental results. In particular,
the repository does not claim biological calibration, experimental or clinical
validation, clinical suitability, or production readiness. P2's EPS field is
immobile, shear is a simplified non-CFD exposure abstraction, and sensitivity
rankings are descriptive observed ranges rather than global sensitivity
analysis.

Read [LIMITATIONS.md](LIMITATIONS.md) for the complete limitations record and
[the biological assumptions](docs/BIOLOGICAL_ASSUMPTIONS.md) for the documented
model assumptions.

## Installation

BioMesh currently requires Python **3.14** (`>=3.14,<3.15`) and targets Linux.
The development install includes the runtime and verification tools:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

The project uses the newest stable Python version fully supported by all
required dependencies. Do not silently substitute another Python version if a
dependency compatibility problem appears.

## Quick start

From the repository root, confirm the CLI and run the core validation paths:

```bash
python -m biomesh --help
python -m biomesh validate diffusion
python -m biomesh validate growth
python -m biomesh validate mass-balance
python -m biomesh run
python -m biomesh reproduce
```

To validate the published fixture definitions and run one complete manufactured
P2 experiment, use a new output directory:

```bash
python -m biomesh validate all
python -m biomesh experiment experiments/producer.yaml \
  --output outputs/producer-experiment-demo
python -m biomesh report outputs/producer-experiment-demo
```

The experiment command prints the generated campaign directory. The report
command validates that directory and writes `report.png` inside it. Output
directories must not already exist; generated contents under `outputs/` are
ignored by Git and should not be committed.

Launch the shell on Linux with `biomesh-gui` or `python -m biomesh.gui`. A
headless startup check is available for development and CI:

```bash
QT_QPA_PLATFORM=offscreen python -m biomesh.gui --smoke-test
```

The shell does not yet display or control a simulation. Recent project entries
are UI-only references, not parsed experiment or scientific configuration.

## Experiment fixtures

The root `experiments/` directory contains the executable manufactured fixture
surface. Use `experiment` for:

- `producer.yaml`, `nonproducer.yaml`, and `competition_50_50.yaml`;
- `inoculation_intermixed.yaml` and `inoculation_segregated.yaml`; and
- `eps_constitutive.yaml` and `eps_quorum_controlled.yaml`.

Use `sweep` for `qs_threshold_sweep.yaml`, `nutrient_oxygen_sweep.yaml`,
`eps_cost_sweep.yaml`, and `shear_sweep.yaml`. Each published condition runs at
fixed seeds 101, 202, and 303. These fixture inputs and their outputs are
software-validation evidence only; the unresolved campaign definition and
biological parameter records remain separately provenance-labelled and
`CALIBRATION_REQUIRED`.

## Repository guide

Useful entry points for users and developers:

| Location | Purpose |
| --- | --- |
| `src/biomesh/` | Typed implementation and CLI entry point |
| `tests/` | Focused behavior, validation, and replay tests |
| `experiments/` | Published fixture commands and unresolved campaign definition |
| `parameters/` | SI-labelled parameter records and provenance |
| `outputs/` | Ignored generated runs; only `.gitkeep` is tracked |
| `docs/ARCHITECTURE.md` | Component boundaries and data flow |
| `docs/STANDARDS.md` | Development, scientific, verification, and Git rules |
| `docs/PHASE_STATUS.md` | Authoritative work-package and audit status |
| `docs/PROJECT_STATE.md` | Current branch snapshot and known limitations |

For contribution and change-management rules, read [AGENTS.md](AGENTS.md) and
[the standards](docs/STANDARDS.md) before editing. Keep scientific behavior,
parameters, experiments, and audit evidence within their approved phase
boundaries.

## Roadmap

At a high level, the remaining P3 work is the simulation viewer, experiment
editor, controls/checkpoints/inspection, worker, and analytics/export surface,
followed by the P3A audit. P4 then covers the broader research platform. These
are roadmap items, not completed functionality. BioMesh is not called v1; no
v1 milestone has been reached.

## License

License selection is pending; no license has been added yet.
