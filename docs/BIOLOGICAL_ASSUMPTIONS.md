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

## P2-WP03 competition assumptions

| ID | Statement | Scope | Evidence | Consequence | Validation | Status |
| --- | --- | --- | --- | --- | --- | --- |
| P2-COMP-001 | Producer and nonproducer strains consume carbon and oxygen through one simultaneous start-of-step resource update; only producers apply the existing quorum-scaled EPS allocation. | P2-WP03 resource competition and production cost | `docs/03_PHASE_TWO_COLONY_SYSTEM.md`; strain identities and parameter values `CALIBRATION_REQUIRED` | With zero EPS allocation, role labels are neutral; configured allocation creates the specified producer cost without a hidden strain-specific growth law. | Neutral, well-mixed cost, shared-resource, ordering, and conservation tests | accepted |
| P2-COMP-002 | Every cell samples EPS and its relative mechanical modifiers from the control volume containing its centre, regardless of whether that cell produced EPS. | P2-WP03 shared matrix benefit | Nearby-matrix requirement in `docs/03_PHASE_TWO_COLONY_SYSTEM.md`; cell-grid coupling inherited from P2-WP02 | A nonproducer can share a local matrix benefit with zero EPS allocation; no protection, force, dispersal, or detachment behavior is inferred. | Co-located producer/nonproducer controlled test | accepted |
| P2-COMP-003 | Realized local fitness is per-capita dry-biomass change per second, and spatial segregation is the mean same-strain fraction among exactly equidistant nearest neighbours using periodic horizontal distance. | P2-WP03 fitness and spatial tracking | Deterministic derived metrics; biological interpretation and experiment applicability `CALIBRATION_REQUIRED` | Metrics add no neighbourhood radius or fitness parameter and should not be interpreted as calibrated selection coefficients. | Frequency, lineage, segregation, fixed-seed, and byte-replay tests | accepted |

## P2-WP04 physiological-state assumptions

| ID | Statement | Scope | Evidence | Consequence | Validation | Status |
| --- | --- | --- | --- | --- | --- | --- |
| P2-PHY-001 | A living cell accumulates limitation, dormancy, or lethal exposure when either local carbon or oxygen is at or below the corresponding threshold; recovery accumulates only when both exceed the slow thresholds. | P2-WP04 state transitions | Explicit thresholds and delays required by `docs/03_PHASE_TWO_COLONY_SYSTEM.md`; values and organism applicability `CALIBRATION_REQUIRED` | Active-to-slow, slow-to-dormant, living-to-dead, and slow/dormant-to-active transitions are deterministic and history-dependent without a hidden threshold or delay. | Inclusive threshold, continuous delay, reset, recovery, and replay tests | accepted |
| P2-PHY-002 | Active metabolic activity is the reference fraction one; configured slow and dormant fractions scale both growth and the existing P1 maintenance/death term, while dead and detached activity is zero. | P2-WP04 metabolism, EPS, and competition coupling | Dormant-consumption requirement in `docs/03_PHASE_TWO_COLONY_SYSTEM.md`; fractions and biological scaling `CALIBRATION_REQUIRED` | Dormant cells consume less than active cells under identical conditions; EPS allocation and competition use the same effective anabolic production. | Controlled uptake, growth-rate, EPS, and competition tests | accepted |
| P2-PHY-003 | Dead biomass either persists or follows a configured first-order transfer into an explicit recycled-biomass ledger; recycled mass does not enter a solute or EPS pool. | P2-WP04 dead-biomass disposition | Explicit-rule requirement in `docs/03_PHASE_TWO_COLONY_SYSTEM.md`; rate, composition, and resource conversion `CALIBRATION_REQUIRED` | Retained plus recycled dead biomass reconciles without inventing a carbon, oxygen, or EPS conversion yield. | Persistence, analytical first-order recycling, and ledger tests | accepted |
| P2-PHY-004 | Detachment is a terminal state selected explicitly by the caller in WP04; no shear or detachment probability is inferred. | P2-WP04 state inventory and mechanics boundary | Detached state required by `docs/03_PHASE_TWO_COLONY_SYSTEM.md`; mechanism deferred to P2-WP05 | Detached biomass remains in the population ledger but is excluded from retained mechanics; WP04 adds no shear behavior. | Terminal-state, activity, mechanics-filter, and output tests | accepted |

## P2-WP05 waste and shear assumptions

| ID | Statement | Scope | Evidence | Consequence | Validation | Status |
| --- | --- | --- | --- | --- | --- | --- |
| P2-WS-001 | Waste is a diffusing concentration in `mol m^-3` with caller-provided whole-cell production in `mol s^-1`, optional physiology activity scaling, first-order removal in `s^-1`, and a prescribed top concentration. | P2-WP05 waste transport | `docs/03_PHASE_TWO_COLONY_SYSTEM.md`; production/removal values and biological scaling `CALIBRATION_REQUIRED` | Waste accounting is conservative across cell production, explicit removal, and top-boundary transfer; no biomass-composition conversion or toxicity law is inferred. | Production/removal balance, stability, and replay tests | accepted |
| P2-WS-002 | Simplified surface-parallel shear is a uniform stress in `Pa`; a cell accumulates deterministic exposure in `Pa s` and detaches only when positive current stress reaches a configurable threshold. | P2-WP05 detachment | `docs/03_PHASE_TWO_COLONY_SYSTEM.md`; stress and threshold values `CALIBRATION_REQUIRED` | Zero shear creates no shear-driven detachment, without a stochastic probability law, resolved flow field, or hidden numerical threshold. | Zero-shear and monotone-shear controlled tests | accepted |
| P2-WS-003 | The effective detachment threshold is the configured base exposure threshold multiplied by the caller-declared attached-state resistance and the existing local EPS attachment-strength multiplier. | P2-WP05 attachment and EPS coupling | Required EPS-dependent detachment behavior; functional form and multipliers `CALIBRATION_REQUIRED` | Stronger EPS and configured surface attachment monotonically raise resistance; selected IDs are handed to the existing terminal detached-state ledger. | EPS, attachment, population-ledger, output, and replay tests | accepted |

## P2-WP06 experiment assumptions

| ID | Statement | Scope | Evidence | Consequence | Validation | Status |
| --- | --- | --- | --- | --- | --- | --- |
| P2-EXP-001 | Campaign orchestration expands a complete condition matrix over multiple fixed seeds but delegates the already-approved component update order to a typed run executor. | P2-WP06 experiment harness | `docs/03_PHASE_TWO_COLONY_SYSTEM.md`; coupled update order not specified | The harness cannot introduce a hidden biological mechanism or silently alter completed component contracts. | Complete-matrix, condition/seed-manifest, and explicit-failure tests | accepted |
| P2-EXP-002 | Quorum-active fraction summarizes the population's continuous P2-WP01 Hill activation response without a new binary threshold. | P2-WP06 quorum result | P2-QS-003; biological applicability `CALIBRATION_REQUIRED` | Replicate summaries preserve the approved continuous response and make no active/inactive classification claim. | Required-metric/unit and deterministic-statistics tests | accepted |
| P2-EXP-003 | Replicate confidence intervals use the campaign-recorded confidence level and Student's t distribution over fixed seeds. | P2-WP06 result statistics | Explicit statistical reporting choice; not a biological parameter | Mean, sample variance, and confidence bounds are reproducible descriptors and not calibration uncertainty. | Known-value statistics and byte-replay tests | accepted |
| P2-EXP-004 | Sensitivity ranks only the absolute range of replicate means observed across each specified sweep family, separately for every metric and time. | P2-WP06 sensitivity result | Required P2 output; no fitted or global sensitivity model | Rankings identify result-dependent sweep effects without comparing unlike units or separating the joint nutrient/oxygen factor. | Complete-family and deterministic-ranking tests | accepted |
