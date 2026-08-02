# BioMesh P1 – Phase 1 – Core Model

## Goal
Build the smallest reproducible 2D biofilm simulator that is numerically verified before adding quorum sensing, EPS, or multi-strain competition.

## Completion Gate
P1 – Phase 1 – Core Model is complete only when all required tests pass, mass-balance error is within the configured tolerance, results reproduce from a fixed seed, and P1A – Phase 1 Audit passes.

## Scope
Implement:
- 2D vertical biofilm cross-section.
- Rod-shaped individual cells.
- Carbon and oxygen reaction-diffusion fields.
- Dual-substrate Monod growth.
- Biomass growth, elongation, division, death, and surface attachment.
- Cell overlap resolution.
- Deterministic seeds.
- Structured parameter files with units and provenance.
- Scientific outputs and validation tests.

Do not implement:
- Quorum sensing.
- EPS regulation.
- Producer/nonproducer competition.
- Shear detachment.
- 3D, GPU acceleration, ML, or polished UI.

## Scientific Model
Growth rate:

\[
\mu=\mu_{max}\frac{S}{K_S+S}\frac{O}{K_O+O}
\]

Biomass:

\[
\frac{dX_i}{dt}=(\mu_i-k_d)X_i
\]

Substrate consumption:

\[
r_S=-\frac{\mu X}{Y_{X/S}}
\]

Solute transport:

\[
\frac{\partial C}{\partial t}=\nabla\cdot(D\nabla C)+R(C,\mathbf{x},t)
\]

Use SI units internally. Any unknown value must be labeled `CALIBRATION_REQUIRED`.

## Repository Layout
```text
biomesh/
├── README.md
├── LICENSE
├── pyproject.toml
├── AGENTS.md
├── docs/
├── src/biomesh/
│   ├── config.py
│   ├── cells.py
│   ├── mechanics.py
│   ├── metabolism.py
│   ├── solutes.py
│   ├── simulation.py
│   └── outputs.py
├── parameters/
├── experiments/
├── validation/
├── tests/
└── outputs/
```

## Work Packages

### P1.1 Repository and configuration
- Create package, tests, linting, typing, and CLI entry point.
- Use the Python version currently resolved under `STANDARDS.md` policy, plus NumPy, SciPy, Numba, Pydantic, PyArrow, Matplotlib, and Pytest.
- Add YAML or TOML parameter files.
- Require units, source, uncertainty, and notes for each biological parameter.

Acceptance:
- Fresh environment installs successfully.
- `python -m biomesh --help` works.
- Invalid parameters fail with clear errors.

### P1.2 Solute fields
- Implement carbon and oxygen grids.
- Use finite differences with explicit stability checks or an implicit sparse solver.
- Boundary conditions: constant bulk concentration at top, no-flux at bottom, periodic sides.
- Add cell-to-grid source/sink mapping.

Acceptance:
- Pure diffusion matches an analytical benchmark.
- No negative concentration beyond numerical tolerance.
- Grid refinement produces convergent results.

### P1.3 Cell model
- Represent cells as 2D capsules.
- Store position, orientation, length, radius, dry biomass, age, state, strain, and parent ID.
- Grow length from biomass.
- Divide above a configurable threshold with small daughter asymmetry.
- Persist lineage IDs.

Acceptance:
- Division conserves biomass within tolerance.
- Fixed seeds reproduce identical lineages.
- Cell geometry remains valid after division.

### P1.4 Metabolism
- Implement dual-substrate Monod kinetics.
- Apply explicit biomass yields and maintenance/death terms.
- Couple local uptake to solute fields.

Acceptance:
- Well-mixed growth matches the expected ODE solution.
- Closed-system mass balance passes.
- Growth halts when either required substrate is absent.

### P1.5 Mechanics and attachment
- Prevent persistent cell overlap.
- Attach initial cells to the bottom surface.
- Relax positions after growth and division.
- Record unresolved overlap as an error metric.

Acceptance:
- Maximum overlap remains below threshold.
- Mechanical solver converges or fails explicitly.
- Cells do not cross the solid boundary.

### P1.6 Outputs
Save:
- Cell snapshots.
- Solute fields.
- Biomass over time.
- Cell count and division events.
- Biofilm height and roughness.
- Mass-balance report.
- Seed, parameters, version, and commit hash.

Use Parquet for tables and compressed NumPy or Zarr-compatible arrays for fields.

## Required Tests
- Parameter validation.
- Pure diffusion benchmark.
- No-flux boundary test.
- Monod limiting cases.
- Well-mixed growth benchmark.
- Biomass conservation during division.
- Closed-system mass balance.
- Deterministic replay.
- Collision relaxation.
- Grid and time-step convergence.

## Codex Execution Prompt
```text
Implement BioMesh P1 – Phase 1 – Core Model only. Read `STANDARDS.md`, then
AGENTS.md and this file first.
Work in small commits. Before coding each package, state equations,
units, assumptions, and tests. Do not add P2 – Phase 2 – Colony System features.

Priorities:
1. Correctness and reproducibility.
2. Tests before visualization.
3. Explicit failures instead of silent clamping.
4. Small modules and typed interfaces.
5. No invented biological constants.

After each work package, run tests, summarize failures, and update
CHANGELOG.md and docs/PHASE_STATUS.md. Stop when P1A – Phase 1 Audit
checklist can be executed.
```

## Token-Efficient Codex Workflow
- Start each session with only `AGENTS.md`, this file, and the relevant module/test files.
- Ask for one work package at a time.
- Request diffs, not full-file rewrites, unless architecture changes.
- Keep `docs/PHASE_STATUS.md` under 150 lines.
- Store equations and conventions once in `AGENTS.md`; reference them elsewhere.
- Require Codex to summarize test output instead of pasting full logs unless failures occur.

## End-of-Phase Update
1. Run full tests and audit prerequisites.
2. Update README, CHANGELOG, parameter provenance, and limitations.
3. Commit code and docs.
4. Push the phase branch.
5. Run `02_PHASE_ONE_AUDIT.md`.
6. Merge only after audit pass.
