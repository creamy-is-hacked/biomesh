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
