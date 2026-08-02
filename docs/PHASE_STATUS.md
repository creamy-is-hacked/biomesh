# BioMesh Phase Status

This is the authoritative progress tracker for all BioMesh work packages and
audits. Execute the first `INCOMPLETE` work package in phase order; do not
start an audit until every work package in its phase is complete.

Status values: `COMPLETE`, `INCOMPLETE`, or `BLOCKED`.

## M0 – Repository Bootstrap

All M0 implementation items are complete. The recorded `M0: Repository
Bootstrap` commit (`95e9ab5`) and `v0.0.0-m0` tag satisfy the M0 handoff gate.

| ID | Work package | Status |
| --- | --- | --- |
| M0-WP01 | Package metadata and typed non-simulation CLI shell | COMPLETE |
| M0-WP02 | Package version and module-help tests | COMPLETE |
| M0-WP03 | Linux CI for install, lint, typing, and tests on Python 3.14 | COMPLETE |
| M0-WP04 | Repository rules and scientific provenance documentation contracts | COMPLETE |
| M0-WP05 | Future-use parameter, experiment, validation, and output directories | COMPLETE |
| M0-WP06 | Dependency and required-check validation | COMPLETE |

M0 validation evidence:

- Python 3.14.4; fresh virtual environment and editable development install passed.
- `python -m biomesh --help`, `ruff check .`, `mypy src`, and `pytest -q`
  passed (2 tests).

## P1 – Phase 1 – Core Model

Source: `docs/01_PHASE_ONE_CORE_MODEL.md`.

| ID | Work package | Status |
| --- | --- | --- |
| P1-WP01 | Repository and configuration | COMPLETE |
| P1-WP02 | Solute fields | COMPLETE |
| P1-WP03 | Cell model | INCOMPLETE |
| P1-WP04 | Metabolism | INCOMPLETE |
| P1-WP05 | Mechanics and attachment | INCOMPLETE |
| P1-WP06 | Outputs | INCOMPLETE |
| P1A | Phase 1 Audit | INCOMPLETE |

P1-WP01 validation evidence:

- A fresh Python 3.14 virtual environment installed the editable package with
  `.[dev]` successfully and `python -m biomesh --help` passed.
- `python -m biomesh --help`, `ruff check .`, `mypy src`, and `pytest -q`
  passed in the repository environment (6 tests).
- At the P1-WP01 handoff, `parameters/p1_core_model.toml` passed strict
  TOML/Pydantic validation with five P1 biological quantities. Each used SI
  units and explicitly recorded value, source, and uncertainty as
  `CALIBRATION_REQUIRED`; no constants or citations were added.

P1-WP02 validation evidence:

- Carbon and oxygen field inputs require caller-provided SI transport and
  boundary values. The parameter file records the two effective diffusivities
  and two bulk concentrations as `CALIBRATION_REQUIRED`; no values or sources
  were invented.
- `python -m biomesh --help`, `ruff check .`, `mypy src`, and `pytest -q`
  passed in the repository environment (13 tests). The test suite includes a
  manufactured pure-diffusion benchmark, grid-refinement convergence,
  nonnegative-concentration behavior, explicit stability rejection, and
  conservative cell-to-grid source/sink mapping.

## P2 – Phase 2 – Colony System

Source: `docs/03_PHASE_TWO_COLONY_SYSTEM.md`.

| ID | Work package | Status |
| --- | --- | --- |
| P2-WP01 | Quorum signal | INCOMPLETE |
| P2-WP02 | EPS model | INCOMPLETE |
| P2-WP03 | Competition | INCOMPLETE |
| P2-WP04 | Physiological states | INCOMPLETE |
| P2-WP05 | Waste and shear | INCOMPLETE |
| P2-WP06 | Experiments | INCOMPLETE |
| P2A | Phase 2 Audit | INCOMPLETE |

## P3 – Phase 3 – Desktop GUI

Source: `docs/06_PHASE_THREE_DESKTOP_GUI.md`.

| ID | Work package | Status |
| --- | --- | --- |
| P3-WP01 | Stable application API | INCOMPLETE |
| P3-WP02 | Desktop shell | INCOMPLETE |
| P3-WP03 | Simulation viewer | INCOMPLETE |
| P3-WP04 | Experiment editor | INCOMPLETE |
| P3-WP05 | Controls, checkpoints, and inspection | INCOMPLETE |
| P3-WP06 | Analytics and export | INCOMPLETE |
| P3A | Phase 3 Audit | INCOMPLETE |

## P4 – Phase 4 – Research Platform

Source: `docs/08_PHASE_FOUR_RESEARCH_PLATFORM.md`.

| ID | Work package | Status |
| --- | --- | --- |
| P4-WP01 | Project and campaign model | INCOMPLETE |
| P4-WP02 | Comparison and reports | INCOMPLETE |
| P4-WP03 | Plugin API | INCOMPLETE |
| P4-WP04 | Model and parameter registry | INCOMPLETE |
| P4-WP05 | Local run queue | INCOMPLETE |
| P4-WP06 | Portable projects and packaging | INCOMPLETE |
| P4-WP07 | Experimental acceleration boundary | INCOMPLETE |
| P4A | Phase 4 Audit | INCOMPLETE |

## Next Work Package

`P1-WP03 – Cell model` is the first incomplete work package. Do not begin it
until separately requested.

## Remaining Issues

- The P1 solute-field transport foundation is complete. Cell model,
  metabolism, mechanics, simulation orchestration, and output implementation
  have not begun.
