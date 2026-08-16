# BioMesh Planning Package

## Start Here
1. Read `STANDARDS.md`, `AGENTS.md`, `PHASE_STATUS.md`, and `PROJECT_STATE.md`.
2. Execute only the first `INCOMPLETE` work package in phase order.
3. For P5-P9, read `10_PRE_V1_ROADMAP.md` and only the active package section.
4. Use the model-routing table in `00_START_HERE_PROMPT.md` and a fresh task for
   each work package.
5. Run every audit in a fresh reviewer session. A failed audit blocks the next
   phase; only P9A may authorize `v1.0.0`.

## Intended End Product
BioMesh progresses from a verified scientific engine to an independently
audited Linux desktop research platform and version 1 release:

1. **M0 – Repository Bootstrap:** repository, tooling, documentation contracts, CLI shell, tests, and CI.
2. **P1 – Phase 1 – Core Model:** reaction-diffusion and individual-cell core.
3. **P1A – Phase 1 Audit:** independent review of P1.
4. **P2 – Phase 2 – Colony System:** quorum sensing, EPS, competition, physiological states, and detachment.
5. **P2A – Phase 2 Audit:** independent review of P2.
6. **P3 – Phase 3 – Desktop GUI:** configuration, visualization, inspection, analytics, checkpoints, and exports.
7. **P3A – Phase 3 Audit:** independent review of P3.
8. **P4 – Phase 4 – Research Platform:** campaigns, comparisons, plugins, local queueing, portable projects, packaging, and an experimental acceleration boundary.
9. **P4A – Phase 4 Audit:** independent review of P4.
10. **P5/P5A – Security and Distribution Hardening:** threat model, installed-build provenance, archive protection, plugin isolation, installer lifecycle, and independent security audit.
11. **P6/P6A – Portable Operations:** portable queue intent, explicit local rebinding, cross-host recovery, and independent portability audit.
12. **P7/P7A – Calibration and Validation:** evidence governance, licensed datasets, deterministic fitting, held-out validation, registry promotion, and independent scientific audit.
13. **P8/P8A – 3D and Accelerated Computing:** explicit 3D numerical contracts, CPU reference, optional accelerated backend, equivalence/performance evidence, and independent numerical audit.
14. **P9/P9A – Version 1 Release:** contract freeze, migration, release packaging, documentation, release-candidate rehearsal, and the blocking v1 release audit.

Each phase has a blocking audit. Later phases may not weaken earlier validation.

## Documents
- `00_START_HERE_PROMPT.md`
- `01_PHASE_ONE_CORE_MODEL.md`
- `02_PHASE_ONE_AUDIT.md`
- `03_PHASE_TWO_COLONY_SYSTEM.md`
- `04_PHASE_TWO_AUDIT.md`
- `05_GITHUB_LINUX_WORKFLOW.md`
- `06_PHASE_THREE_DESKTOP_GUI.md`
- `07_PHASE_THREE_AUDIT.md`
- `08_PHASE_FOUR_RESEARCH_PLATFORM.md`
- `09_PHASE_FOUR_AUDIT.md`
- `10_PRE_V1_ROADMAP.md`
- `P5_WP01_THREAT_MODEL.md`
- `P5_WP02_INSTALLED_BUILD_PROVENANCE.md`
- `P5_WP03_ARCHIVE_SECURITY_POLICY.md`
- `P5_WP04_ISOLATED_PLUGIN_EXECUTION.md`
- `P5_WP05_INSTALLER_LIFECYCLE.md`
- `11_PHASE_FIVE_AUDIT.md`

## Token Discipline
Load only `AGENTS.md`, `PHASE_STATUS.md`, one work-package section, and affected interfaces/tests. Request patches, store evidence in the repository, summarize logs, and escalate model strength only when a defined gate remains unresolved.
