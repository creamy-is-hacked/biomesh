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

## P2-WP01 quorum-signal assumptions

| ID | Statement | Scope | Evidence | Consequence | Validation | Status |
| --- | --- | --- | --- | --- | --- | --- |
| P2-QS-001 | Basal and induced signal production are configurable whole-cell rates in `mol s^-1`, mapped to the control volume containing each cell centre. | P2-WP01 production and cell-grid coupling | `docs/03_PHASE_TWO_COLONY_SYSTEM.md`; production scaling and applicability `CALIBRATION_REQUIRED` | Production is conservative on the grid and depends on the number and location of cells; no unapproved biomass scaling is introduced. | Production, source accounting, and geometry tests | accepted |
| P2-QS-002 | Signal transport uses the audited periodic sides, no-flux bottom, and a configurable prescribed top bulk concentration. | P2-WP01 transport boundary | Reuse of the P1 finite-volume domain; experiment applicability `CALIBRATION_REQUIRED` | Signal may enter or leave through the open top boundary and uses the same coordinate convention as other fields. | Diffusion-decay benchmark and discrete balance test | accepted |
| P2-QS-003 | A cell senses the signal concentration in the control volume containing its centre and records the continuous Hill response without a binary active threshold. | P2-WP01 cell-local sensing | P2 Hill abstraction; interpolation choice and biological applicability `CALIBRATION_REQUIRED` | Activation changes with local geometry and transport; a later mechanism may not infer an active/inactive threshold without an approved parameter. | Uniform Hill-curve and equal-count geometry tests | accepted |
| P2-QS-004 | Positive feedback uses start-of-step local activation; the accepted end-of-step field supplies the next exposure and activation history record. | P2-WP01 deterministic update order | Explicit numerical coupling choice; biological timing `CALIBRATION_REQUIRED` | Feedback, transport, degradation, and sensing have a reproducible order and no hidden iteration. | History, stale-state rejection, and deterministic replay tests | accepted |

## P2-WP02 EPS assumptions

| ID | Statement | Scope | Evidence | Consequence | Validation | Status |
| --- | --- | --- | --- | --- | --- | --- |
| P2-EPS-001 | EPS is an immobile density in `kg m^-3`; each cell deposits allocated biomass-equivalent mass in the control volume containing its centre. | P2-WP02 matrix representation and accumulation | `docs/03_PHASE_TWO_COLONY_SYSTEM.md`; transport or loss evidence `CALIBRATION_REQUIRED` | EPS accumulates conservatively without an unapproved diffusion, decay, or recycling term. | Local production, accumulation, mass-balance, and replay tests | accepted |
| P2-EPS-002 | The allocation fraction is `f_EPS Q`, gross anabolic production remains charged to substrate, and only the unallocated fraction increases living biomass. | P2-WP02 quorum coupling and producer cost | Equations in `docs/03_PHASE_TWO_COLONY_SYSTEM.md`; parameter values `CALIBRATION_REQUIRED` | Higher configured allocation lowers isolated producer growth while living biomass plus EPS retains the biomass-equivalent resource accounting. | Quorum scaling, isolated growth-cost, substrate-yield, and conservation tests | accepted |
| P2-EPS-003 | Local EPS increases relative cohesion and attachment strength through linear dimensionless multipliers `1 + sensitivity * density`. | P2-WP02 EPS-mediated mechanical interaction | Required monotonic interaction in `docs/03_PHASE_TWO_COLONY_SYSTEM.md`; functional form and sensitivities `CALIBRATION_REQUIRED` | The model exposes a deterministic monotone interaction without inventing an absolute force scale, adhesion threshold, or shear law. | Controlled monotonic-density tests | accepted |
