# BioMesh Phase 3 — Desktop Scientific Workbench

## Goal
Turn the audited Phase 2 engine into a usable Linux desktop application without coupling scientific logic to the GUI.

## Completion Gate
Phase 3 is complete when users can configure, run, pause, inspect, save, reload, and export validated simulations through the GUI, and the Phase 3 audit passes.

## Scope
Implement:
- PySide6 desktop shell.
- GPU-assisted 2D rendering with PyQtGraph or VisPy.
- Experiment editor backed by existing parameter schemas.
- Layer controls for cells, carbon, oxygen, quorum signal, EPS, waste, state, and strain.
- Run, pause, step, stop, speed, and checkpoint controls.
- Live plots and summary metrics.
- Cell inspector.
- Save/load experiment definitions and checkpoints.
- Export PNG, CSV, Parquet, and run manifests.
- Background simulation worker so the UI remains responsive.

Do not implement:
- New biology.
- 3D rendering.
- Distributed execution.
- Microscope-image calibration.
- Plugin marketplace.

## Architecture Contract
```text
GUI -> application service -> stable engine API -> scientific core
```
The GUI must not directly mutate solver internals. CLI and GUI must produce equivalent results from the same configuration and seed.

## Work Packages

### P3.1 Stable application API
- Add typed run, pause, step, checkpoint, resume, inspect, and export interfaces.
- Define immutable snapshots for GUI consumption.

Acceptance:
- CLI behavior remains unchanged.
- API tests run headlessly.
- Same seed/config yields equivalent CLI and GUI results.

### P3.2 Desktop shell
- Add main window, menus, dockable panels, status bar, recent projects, and error console.
- Store UI preferences separately from scientific parameters.

Acceptance:
- Opens on supported Linux environment.
- Missing/invalid files fail clearly.
- UI state never changes simulation science.

### P3.3 Simulation viewer
- Render cells and scalar-field heatmaps.
- Add zoom, pan, fit, layer opacity, legends, and frame-rate limiting.
- Render from snapshots, never live mutable arrays.

Acceptance:
- Viewer remains responsive at the Phase 2 reference scale.
- Hidden layers consume minimal render work.
- Visual values match exported arrays within tolerance.

### P3.4 Experiment editor
- Generate controls from validated parameter schemas.
- Show units, source, uncertainty, and validation errors.
- Support templates and read-only audited presets.

Acceptance:
- Saved config round-trips without semantic change.
- Invalid values cannot start a run.
- Audited presets cannot be silently overwritten.

### P3.5 Controls, checkpoints, and inspection
- Add run/pause/step/stop, speed target, checkpoint, resume, and cell click inspection.
- Display cell lineage, strain, biomass, state, local solutes, QS activity, and EPS rate.

Acceptance:
- Pause/step is deterministic at solver boundaries.
- Checkpoint resume matches uninterrupted execution.
- Inspector values match engine state.

### P3.6 Analytics and export
- Add live population, biomass, strain ratio, EPS, QS-active fraction, thickness, roughness, and penetration-depth plots.
- Export plots, tables, fields, and manifests.

Acceptance:
- Plot values match stored metrics.
- Exports include seed, commit, parameters, and software versions.
- Long exports do not freeze the UI.

## Required Tests
- Headless GUI startup.
- Schema-generated form validation.
- CLI/GUI equivalence.
- Pause/step determinism.
- Checkpoint round-trip.
- Snapshot immutability.
- Layer-value correctness.
- Export provenance.
- Worker cancellation and error propagation.

## Codex Execution Prompt
```text
Implement BioMesh Phase 3 only. Read AGENTS.md, this plan, the Phase 2
release API, and the relevant files. Preserve scientific behavior.
Work one package at a time; add tests before UI polish. Keep the GUI
thin, schema-driven, and snapshot-based. Run targeted tests, then the
full suite. Update PHASE_STATUS.md and LIMITATIONS.md in under 150 lines.
Do not add Phase 4 features.
```

## Token-Efficient Workflow
- Give Codex one panel or API boundary per session.
- Reference parameter schemas instead of restating fields.
- Use screenshots only for visual defects.
- Request changed-file summaries under 200 words.
- Keep UI test fixtures small and reuse Phase 2 reference runs.

## End-of-Phase Update
1. Run unit, integration, headless GUI, and CLI/GUI equivalence tests.
2. Produce one reproducible demo experiment and screenshots.
3. Update README, user guide, changelog, and limitations.
4. Push `phase/3-desktop-gui`.
5. Execute `07_PHASE_THREE_AUDIT.md`.
6. Merge and tag only after audit pass.
