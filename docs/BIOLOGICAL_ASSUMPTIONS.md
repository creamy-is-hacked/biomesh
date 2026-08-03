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

## P1-WP02 solute assumptions

| ID | Statement | Scope | Evidence | Consequence | Validation | Status |
| --- | --- | --- | --- | --- | --- | --- |
| P1-SOL-001 | P1 solutes use a constant bulk concentration at the top, no flux at the solid bottom, and periodic side boundaries. | P1-WP02 transport domain | `docs/01_PHASE_ONE_CORE_MODEL.md`; experiment applicability `CALIBRATION_REQUIRED` | Transport represents the prescribed reference domain and not other reactor boundaries. | Manufactured diffusion, no-flux, and periodic-grid tests | accepted |
| P1-SOL-002 | Each whole-cell exchange is assigned to the single control volume containing the cell center. | P1-WP02 cell-to-grid coupling | Numerical mapping choice; biological applicability `CALIBRATION_REQUIRED` | Uptake is conservative but spatially point-local at the selected grid resolution. | Conservative exchange and physical-coordinate mapping tests | accepted |

## P1-WP03 cell assumptions

| ID | Statement | Scope | Evidence | Consequence | Validation | Status |
| --- | --- | --- | --- | --- | --- | --- |
| P1-CELL-001 | Capsule centerline length is proportional to dry biomass through a configured factor, while radius remains caller supplied. | P1-WP03 growth geometry | `docs/01_PHASE_ONE_CORE_MODEL.md`; empirical mapping `CALIBRATION_REQUIRED` | P1 elongation changes length without an inferred radius law. | Biomass-to-length and parameter-provenance tests | accepted |
| P1-CELL-002 | Division preserves the parent axis and radius, places daughter capsules tangent, and samples bounded biomass asymmetry uniformly from a seeded generator. | P1-WP03 division | P1 deterministic division choice; biological support `CALIBRATION_REQUIRED` | Division conserves dry biomass and is reproducible but omits rotation and morphology change. | Biomass, geometry, lineage, and fixed-seed tests | accepted |

## P1-WP04 metabolism assumptions

| ID | Statement | Scope | Evidence | Consequence | Validation | Status |
| --- | --- | --- | --- | --- | --- | --- |
| P1-MET-001 | Carbon and oxygen limitations multiply in the dual-substrate Monod growth law. | P1-WP04 specific growth rate | `docs/01_PHASE_ONE_CORE_MODEL.md`; empirical support `CALIBRATION_REQUIRED` | Either absent substrate makes growth zero. | Monod limiting-case tests | accepted |
| P1-MET-002 | The configured first-order `death_rate` is the P1 maintenance/death biomass-loss term `k_d`; no separate maintenance-uptake equation is assumed. | P1-WP04 biomass balance | `docs/01_PHASE_ONE_CORE_MODEL.md`; empirical support `CALIBRATION_REQUIRED` | Living dry biomass follows `dX/dt = (mu - k_d) X`, and loss is reported separately in step accounting. | Analytical well-mixed ODE and biomass-balance tests | accepted |
| P1-MET-003 | Carbon and oxygen uptake are growth-associated and use independent explicit biomass yields. | P1-WP04 solute coupling | `docs/01_PHASE_ONE_CORE_MODEL.md`; empirical support `CALIBRATION_REQUIRED` | Each solute has a separate yield-equivalent balance; both yield values require calibration. | Closed-system field and yield-balance tests | accepted |

## P1-WP05 mechanics assumptions

| ID | Statement | Scope | Evidence | Consequence | Validation | Status |
| --- | --- | --- | --- | --- | --- | --- |
| P1-MEC-001 | P1 capsule relaxation is deterministic and translation-only; it does not model torque, friction, or an adhesion force law. | P1-WP05 cell contact | `docs/01_PHASE_ONE_CORE_MODEL.md`; force-law evidence `CALIBRATION_REQUIRED` | Capsule overlap is resolved geometrically without changing orientation. | Collision, deterministic replay, and capsule-validity tests | accepted |
| P1-MEC-002 | The bottom at `y = 0 m` is solid; configured bottom-attached initial cells remain surface-tangent but may move horizontally. | P1-WP05 boundary and attachment | `docs/01_PHASE_ONE_CORE_MODEL.md`; adhesion evidence `CALIBRATION_REQUIRED` | Cells cannot cross the bottom, while no unapproved adhesion strength is introduced. | Attachment and boundary tests | accepted |
