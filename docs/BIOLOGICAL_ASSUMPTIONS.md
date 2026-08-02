# Biological Assumptions

This register contains only assumptions introduced by completed work packages.
An accepted model assumption is not evidence that its biological parameters
have been calibrated.

## Assumption record

| Field | Required content |
| --- | --- |
| ID | Stable assumption identifier |
| Statement | Explicit biological assumption |
| Scope | Affected model component and phase |
| Evidence | Source or `CALIBRATION_REQUIRED` |
| Consequence | Expected effect or limitation |
| Validation | Test, benchmark, or unresolved validation need |
| Status | Proposed, accepted, superseded, or rejected |

## P1-WP04 metabolism assumptions

| ID | Statement | Scope | Evidence | Consequence | Validation | Status |
| --- | --- | --- | --- | --- | --- | --- |
| P1-MET-001 | Carbon and oxygen limitations multiply in the dual-substrate Monod growth law. | P1-WP04 specific growth rate | `docs/01_PHASE_ONE_CORE_MODEL.md`; empirical support `CALIBRATION_REQUIRED` | Either absent substrate makes growth zero. | Monod limiting-case tests | accepted |
| P1-MET-002 | The configured first-order `death_rate` is the P1 maintenance/death biomass-loss term `k_d`; no separate maintenance-uptake equation is assumed. | P1-WP04 biomass balance | `docs/01_PHASE_ONE_CORE_MODEL.md`; empirical support `CALIBRATION_REQUIRED` | Living dry biomass follows `dX/dt = (mu - k_d) X`, and loss is reported separately in step accounting. | Analytical well-mixed ODE and biomass-balance tests | accepted |
| P1-MET-003 | Carbon and oxygen uptake are growth-associated and use independent explicit biomass yields. | P1-WP04 solute coupling | `docs/01_PHASE_ONE_CORE_MODEL.md`; empirical support `CALIBRATION_REQUIRED` | Each solute has a separate yield-equivalent balance; both yield values require calibration. | Closed-system field and yield-balance tests | accepted |
