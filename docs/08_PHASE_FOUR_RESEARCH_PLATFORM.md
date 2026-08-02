# BioMesh P4 – Phase 4 – Research Platform

## Goal
Evolve BioMesh from a single desktop simulator into an extensible microbial-experiment platform while preserving audited models and reproducibility.

## Completion Gate
P4 – Phase 4 – Research Platform is complete when campaigns, plugins, comparison workflows, packaging, and a documented extension example work from a clean install and P4A – Phase 4 Audit passes.

## Scope
Implement:
- Experiment projects and campaign manager.
- Batch replicates and parameter sweeps.
- Run comparison and report generation.
- Versioned plugin interfaces for species, kinetics, fields, metrics, and exporters.
- Model/parameter registry with provenance and compatibility checks.
- Queue for local background runs.
- Reproducible project archive import/export.
- Linux application packaging.
- Optional 3D/GPU feasibility prototype behind an experimental flag.

Do not implement:
- Cloud service.
- Clinical claims.
- Automatic biological parameter invention.
- Unreviewed third-party plugin execution.
- Full CFD or production 3D unless separately audited.

## Work Packages

### P4-WP01 Project and campaign model
- Define project, experiment, campaign, run, artifact, and audit records.
- Support replicate counts, seed policies, and sweep matrices.

Acceptance:
- Campaigns resume safely.
- Runs remain immutable after completion.
- Partial failures are explicit and retryable.

### P4-WP02 Comparison and reports
- Compare conditions, replicates, distributions, effect sizes, and uncertainty.
- Generate HTML/PDF-ready report data without embedding scientific conclusions in UI code.

Acceptance:
- Report metrics trace to raw runs.
- Single-seed claims are flagged.
- Missing runs are visible, not silently dropped.

### P4-WP03 Plugin API
- Version interfaces for model components and metadata.
- Run plugins in a controlled loading path with compatibility validation.
- Provide one example species/kinetics plugin.

Acceptance:
- Core works with zero plugins.
- Incompatible plugins fail before simulation.
- Plugin provenance appears in manifests.

### P4-WP04 Model and parameter registry
- Store named, versioned models and parameter sets.
- Distinguish measured, literature-derived, fitted, assumed, and calibration-required values.

Acceptance:
- Audited presets are immutable.
- Compatibility and unit checks run before launch.
- Citations and uncertainty survive export/import.

### P4-WP05 Local run queue
- Add queued campaigns, priorities, resource limits, progress, cancellation, and restart recovery.
- Keep execution local.

Acceptance:
- Queue survives app restart.
- Failed runs do not corrupt completed runs.
- CPU and memory limits are respected.

### P4-WP06 Portable projects and packaging
- Export a self-describing project archive containing configs, manifests, compact results, and checksums.
- Package for Linux using a documented build path.

Acceptance:
- Archive reproduces on a clean clone or installation.
- Checksums detect corruption.
- Installer does not bundle generated research data.

### P4-WP07 Experimental acceleration boundary
- Define benchmark interfaces for later 3D/GPU work.
- Optional prototype must reproduce a CPU reference within tolerance.

Acceptance:
- Experimental path is disabled by default.
- No unsupported performance claim appears in releases.
- Divergence is measured and documented.

## Required Tests
- Campaign resume and retry.
- Seed-policy correctness.
- Report traceability.
- Plugin compatibility and isolation.
- Registry immutability and units.
- Queue recovery.
- Archive checksum and reproduction.
- Clean package install.
- CPU/experimental equivalence if prototype exists.

## Codex Execution Prompt
```text
Implement BioMesh P4 – Phase 4 – Research Platform only. Preserve the audited engine and GUI.
Read `STANDARDS.md`, then AGENTS.md, this plan, and the P3 – Phase 3 – Desktop GUI public interfaces. Complete
one work package at a time with tests and migration notes. Prefer
versioned schemas and narrow plugin contracts. Do not add cloud,
clinical, or unaudited biological claims. Summaries stay under 250 words.
```

## Token-Efficient Workflow
- Work from interfaces and issue IDs, not full repository dumps.
- Reuse manifests, schemas, and reference campaigns.
- Keep plugin examples minimal.
- Store benchmark outputs as artifacts; paste only failures.
- Separate required platform work from experimental acceleration.

## End-of-Phase Update
1. Run full regression, campaign, plugin, archive, and packaging tests.
2. Reproduce a multi-condition campaign from a clean installation.
3. Update architecture, extension guide, user guide, changelog, and limitations.
4. Push `phase-4-research-platform`.
5. Execute `09_PHASE_FOUR_AUDIT.md`.
6. Merge and tag only after audit pass.
