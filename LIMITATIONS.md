# Limitations

## P1A – Phase 1 Audit

- The independent 2026-08-02 rerun accepted Phase 1 with the limitations below.
- Every biological value in the P1 manifest remains `CALIBRATION_REQUIRED`; no
  value, citation, calibration, or benchmark outcome has been invented.
- The default reference is a zero-duration, zero-cell, zero-solute software
  fixture. It proves configuration/output/replay behavior and must not be used
  as evidence of calibrated biological dynamics.
- The manufactured validators use declared synthetic SI inputs to verify the
  equations and full update path; those values are not biological defaults.
- Byte-identical reproduction is gated to the recorded parameter file and
  execution environment. A changed parameter hash is rejected explicitly.
- License selection is pending.
- The inspected branch name is noncanonical under `docs/STANDARDS.md`, and the
  audited worktree still requires the user-owned commit and audit-tag handoff.

## P2-WP01 – Quorum signal

- All seven quorum parameters remain `CALIBRATION_REQUIRED`; manufactured test
  inputs verify software equations and are not biological values or benchmark
  claims.
- Production is represented as a whole-cell rate and cell-local sensing uses
  the containing control volume. Biomass-dependent production or spatial
  interpolation requires separate evidence and approval.
- The response is a continuous Hill fraction. No binary quorum-active threshold
  is approved or inferred.
- Transport uses explicit time integration and the Phase 1 boundary model. The
  timestep must satisfy the combined diffusion-degradation stability limit.
- P2-WP01 does not couple activation to EPS, competition, physiological state,
  waste, shear, or the Phase 1 orchestration loop; those remain later work
  packages or need an explicitly specified integration order.
