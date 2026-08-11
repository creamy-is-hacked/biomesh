# BioMesh

BioMesh is a deterministic, 2D bacterial biofilm simulation platform under
development. It combines a configurable scientific-model core with
reproducible validation and experiment-fixture workflows, and is being shaped
into a Linux desktop research platform.

## Current status

The latest accepted phase is **P3 – Phase 3 – Desktop GUI**. Its independent
2026-08-10 audit passed with recorded limitations and is represented by the
`v0.3.1-audit` tag. The P4-WP01 – Project and campaign model through P4-WP06 –
Portable projects and packaging work packages are complete on the Phase 4
branch. P4-WP07 – Experimental acceleration boundary is the next incomplete
work package.

The current desktop GUI has menus, docks, status, recent project references, an
error console, separate UI preferences, a snapshot-only simulation viewer, a
schema-generated biological-parameter editor, solver-boundary controls,
checkpoint interaction, and immutable cell inspection. A small background
worker owns the synchronous application API and controls only the existing
manufactured P2 fixture path. Snapshot-only live plots show the existing
population, biomass, producer-frequency, EPS, quorum-response, thickness,
roughness, and penetration-depth metrics. Completed runs export atomically as
PNG plots, exact CSV/Parquet analytics, canonical Parquet tables and NumPy
fields, and a provenance-complete run manifest.

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
  status reporting, recent file references, and UI-only XDG preferences; and
- the P3-WP03 PyQtGraph viewer for immutable cell geometry and scalar fields,
  with zoom, pan, fit, layer visibility/opacity, legends, and frame limiting;
  and
- the P3-WP04 editor for the existing validated biological-parameter schemas,
  with provenance display, explicit validation, semantic TOML round-trip,
  editable templates, and hash-bound read-only audited presets; and
- the P3-WP05 worker, exact P2 fixture/condition/seed controls, deterministic
  pause/step/stop behavior, speed target, checkpoint/resume interaction, and
  snapshot-based cell inspection; and
- the P3-WP06 immutable-snapshot analytics panel and cancellable background
  export bundle with PNG, CSV, Parquet, canonical fields/tables, hashes,
  calibration status, seed, commit, and software-version provenance; and
- deterministic P3 frontend-equivalence and checkpoint-replay verification
  commands over a manufactured `CALIBRATION_REQUIRED` reference selector; and
- the P4 versioned local project/campaign model plus presentation-neutral
  comparison/report JSON and CSV with raw-run hash/row traceability, explicit
  missing-run coverage, and single-seed warnings; and
- the P4 versioned plugin boundary for species, kinetics, fields, metrics, and
  exporters, with whole-set compatibility/trust preflight, deterministic
  provenance manifests, zero-plugin operation, and a packaged uncalibrated
  species/kinetics example; and
- the P4 named/versioned model and parameter registry with hash-bound immutable
  audited presets, explicit provenance categories, citations and uncertainty,
  deterministic import/export, SI compatibility checks, and exact reviewed
  plugin preflight; and
- the P4 persistent local campaign queue with deterministic priorities,
  run-level progress, exact Linux CPU/memory enforcement, targeted
  cancellation, and restart recovery that preserves immutable completed runs;
- deterministic portable project export/verification/import with embedded
  hash-bound fixtures, exact completed-run artifacts, per-file SHA-256, and
  clean-install reproduction; and
- a reproducible Linux wheel-installer bundle whose build gate rejects
  generated project, queue, report, raw-run, and research-result data.

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

The minimum supported desktop display is 1024×720. Rich dock contents remain
scrollable at that size. Standard Tab/Shift+Tab navigation reaches the run
selectors, every lifecycle/checkpoint control when enabled, speed target,
viewer controls, and editor inputs. Standard Alt menu navigation reaches the
project and export actions; Ctrl+O opens a project reference and Ctrl+Q exits.

The reproducible P3 verification reference runs the existing producer fixture
at independent deterministic seed 42. It adds no biological value and does not
expand the desktop's accepted P2 seed choices:

```bash
python -m biomesh compare-frontends parameters/phase2_reference.yaml --seed 42
python -m biomesh verify-checkpoint outputs/p3a-reference-seed-42
```

The first command atomically writes byte-identical CLI and application-service
artifact trees, a hash-bound checkpoint, and `frontend_equivalence.json`. The
second reconstructs that checkpoint and byte-compares the replay with the
stored uninterrupted application artifacts. Both outputs remain manufactured
software-verification evidence and preserve `CALIBRATION_REQUIRED` status.

For a completed P4 project campaign, generate a new comparison/report data
directory with:

```bash
python -m biomesh campaign report PROJECT_DIRECTORY CAMPAIGN_ID \
  --output NEW_REPORT_DIRECTORY
```

The report contains deterministic JSON plus CSV coverage, observations,
condition summaries, and pairwise comparisons. Each value retains raw artifact
hash and row provenance. Missing runs and single-seed limitations remain
visible; the report does not generate a scientific conclusion or calibration
claim. See [the P4-WP01 project model](docs/P4_WP01_PROJECT_CAMPAIGN.md) and
[the P4-WP02 report contract](docs/P4_WP02_COMPARISON_REPORTS.md).

Verify the zero-plugin core contract and the exact reviewed packaged example
with:

```bash
python -m biomesh plugins verify
python -m biomesh plugins verify --output NEW_DIRECTORY
```

The optional output is atomically published as `plugin_manifest.json` with the
plugin API/version, distribution and entry-point identity,
selection/metadata SHA-256, review reference, calibration status, limitations,
and deterministic self-check. A plugin manifest alone is not trusted:
incompatible or unreviewed sets fail before any entry point is loaded. See
[the P4-WP03 plugin contract](docs/P4_WP03_PLUGIN_API.md).

Verify or exchange the deterministic model/parameter registry with:

```bash
python -m biomesh registry verify
python -m biomesh registry export --output NEW_REGISTRY_DIRECTORY
python -m biomesh registry import REGISTRY_FILE_OR_DIRECTORY \
  --output NEW_REGISTRY_DIRECTORY
```

The built-in catalog hash-verifies the five accepted biological-parameter
TOML files, preserves every SI unit and provenance placeholder, and prevents
modified or relabelled records from acquiring audited status. Preflight can
check an exact model/parameter-set version and its zero/reviewed plugin set
before any caller launches work; it emits only traceable content hashes and
does not itself execute a simulation. See
[the P4-WP04 registry contract](docs/P4_WP04_MODEL_PARAMETER_REGISTRY.md).

Create and operate one local queue with explicit worker resource limits:

```bash
python -m biomesh queue create QUEUE_DIRECTORY \
  --cpu-cores CPU_COUNT --memory-limit-bytes BYTES
python -m biomesh queue enqueue QUEUE_DIRECTORY PROJECT_DIRECTORY CAMPAIGN_ID \
  --priority PRIORITY
python -m biomesh queue status QUEUE_DIRECTORY
python -m biomesh queue run QUEUE_DIRECTORY
python -m biomesh queue cancel QUEUE_DIRECTORY QUEUE_ID
```

The worker applies exact Linux CPU affinity and an address-space byte cap before
claiming work. Higher priorities run first and equal priorities remain FIFO.
Queue status exposes campaign run counts during execution; cancellation and
restart recovery retain completed artifact bytes and leave interrupted work as
an explicit retryable failure. Queue references remain local absolute paths.
See [the P4-WP05 queue contract](docs/P4_WP05_LOCAL_RUN_QUEUE.md).

Exchange a project without depending on its original fixture location:

```bash
python -m biomesh project export PROJECT_DIRECTORY \
  --output NEW_PROJECT_ARCHIVE.biomesh
python -m biomesh project verify-archive PROJECT_ARCHIVE.biomesh
python -m biomesh project import PROJECT_ARCHIVE.biomesh \
  NEW_PROJECT_DIRECTORY
```

The archive carries strict self-description, embedded hash-verified fixture
configuration, project/campaign manifests, exact completed-run artifacts and
receipts, and a per-file size/SHA-256 inventory. Pending and failed work remains
explicit. Plugin trust, registry identity, and local queue state are neither
embedded nor inferred; imported projects must be intentionally re-enqueued.
See [the P4-WP06 portability and packaging contract](docs/P4_WP06_PORTABLE_PROJECTS_PACKAGING.md).

Build the documented Linux application installer bundle after creating the
wheel and sdist:

```bash
python -m hatchling build --clean -d dist
python -m biomesh package linux --wheel dist/*.whl \
  --output dist/linux-installer
tar -xzf dist/linux-installer/biomesh-*-linux-*.tar.gz
cd biomesh-*-linux-*
./install.sh
```

The bundle contains the wheel, installer documentation, and checksums. It
requires Linux and Python 3.14, and deliberately excludes generated projects,
archives, queues, reports, raw runs, and research results.

The Simulation Controls dock selects only the 15 existing manufactured P2
fixture conditions and fixed seeds 101, 202, or 303. Run and checkpoint-resume
remain disabled while the Experiment Editor document is invalid or retains
`CALIBRATION_REQUIRED` values or provenance. The editor document is a UI
eligibility gate only: it is not passed to the frozen application API and no
configuration-to-engine bridge is implied. Pause, step, stop, speed target,
checkpoint, and resume operate at accepted solver boundaries. Clicking a cell
shows its immutable public inspection record; values unavailable from that
record are not inferred from private state.

The Analytics dock plots only immutable public snapshots and their existing
stored metrics. “Strain ratio” is explicitly the stored dimensionless producer
cell frequency; penetration depth retains the separate stored carbon and oxygen
series. File → Export Completed Run creates a new directory containing plot
PNGs, exact long-form CSV and Parquet tables, byte-preserved canonical fields
and tables, canonical run metadata, and a hash-indexed run manifest. Export can
be cancelled before atomic publication; failures leave no partial target.

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

P3 is accepted. P4-WP01 through P4-WP06 are complete on the Phase 4 branch;
P4-WP07 – Experimental acceleration boundary is next. The remaining P4 items
are roadmap work, and BioMesh is not called v1.

## License

License selection is pending; no license has been added yet.
