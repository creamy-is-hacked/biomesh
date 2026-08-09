# Limitations

## P3-WP04 – Experiment editor

- The editor covers only the five existing biological-parameter TOML schemas.
  It does not define a P4 project/campaign model, change the immutable P3-WP01
  request type, or make arbitrary edited parameters executable through the
  accepted manufactured fixture path.
- Repository templates preserve all unresolved values and provenance exactly;
  no defaults, constants, sources, uncertainties, citations, or calibration
  results are supplied. A schema-valid document containing any
  `CALIBRATION_REQUIRED` value or provenance remains run-ineligible.
- P2A presets are SHA-256-bound to the accepted implementation revision and
  read-only. Users may create editable copies, but neither direct preset views
  nor copies may overwrite the protected repository records.
- Editor text and validation errors are UI state. Only an immutable existing
  Pydantic schema instance is accepted as scientific configuration. Saves are
  atomic, require a valid draft, and are reloaded before replacement to prove
  semantic round-trip; overwriting other user files requires explicit intent.
- P3-WP04 adds no run/pause/step/stop controls, checkpoint UI, cell inspection,
  worker, analytics, additional export, or scientific behavior.

## P3-WP03 – Simulation viewer

- The PyQtGraph viewer consumes only immutable P3-WP01 snapshots; it does not
  read live solver arrays, construct an application service, or change any
  scientific parameter or update path.
- The frozen snapshot contract contains cell coordinates in metres and scalar
  array shapes/values, but no physical field width or height. Cells and fields
  therefore use separate coordinate-faithful canvases rather than an invented
  overlay transform. Fields are labelled by row and column index.
- Layer legends report the exact displayed minimum, maximum, and snapshot unit.
  A uniform field receives a display-only color-range margin; its image values
  remain unchanged. No interpolation or scientific normalization is applied.
- Frame limiting retains only the newest pending immutable snapshot. It does
  not create a worker or simulation speed control. Hidden layers remain in the
  scene but skip per-snapshot cell-path rebuilds and field-image uploads.
- Run controls, checkpoint interaction, inspection, workers, analytics, and
  additional export remain later P3 work packages.

## P3-WP02 – Desktop shell

- The PySide6 shell supplies desktop chrome around the P3-WP03 viewer.
  Simulation controls, checkpoints, inspection, workers, analytics, and
  additional exports remain later P3 work packages.
- Recent projects are opaque readable-file references because P3-WP02 defines
  no project schema. Selecting one updates only the shell label, status, recent
  menu, and UI preference record; it does not load or alter scientific state.
- UI preferences are strict versioned JSON containing only recent absolute
  paths and base64-encoded Qt window geometry/dock state. A missing file uses
  first-run defaults; invalid state is shown in the error console. Preferences
  are not biological parameters, experiment definitions, or provenance.
- Widget tests run in offscreen subprocesses so Qt's bundled graphics
  libraries do not enter the scientific/reporting test process. Supported
  interactive Linux display environments still require a functioning Qt
  platform plugin.

## P3-WP01 – Stable application API

- The application service controls only the accepted manufactured P2 fixture
  path. It does not turn unresolved `CALIBRATION_REQUIRED` biological campaign
  definitions into executable science or add any calibrated value.
- Pause, step, checkpoint, and resume operate only at the three existing P2
  solver boundaries. Checkpoints store hashes and a deterministic replay
  position rather than serialized mutable solver arrays; changed fixture or
  biological-parameter bytes are rejected.
- Export preserves the existing completed raw Parquet, NumPy, and provenance
  artifacts. Additional formats, live export, and analytics belong to later P3
  work packages.
- P3-WP01 remains synchronous and independent of PySide. P3-WP03 provides only
  a snapshot consumer, and P3-WP04 does not alter the application request or
  execution path; the shell does not yet connect a worker, cancellation, or
  simulation controls.

## P2A – Phase 2 Audit

- The independent 2026-08-08 clean-clone rerun accepted Phase 2 with recorded
  limitations; no Critical or Major finding remains.
- All 45 biological parameter records and the 10 unresolved biological
  campaign overrides remain SI-labelled, provenance-complete, and
  `CALIBRATION_REQUIRED`. The executable numeric fixtures are manufactured
  software validation and provide no calibrated biological result.
- EPS remains an immobile density field with relative cohesion and attachment
  multipliers rather than explicit polymer mechanics or an absolute force law.
- Shear remains a deterministic uniform exposure abstraction rather than CFD,
  resolved hydrodynamics, or a stochastic erosion model.
- Sensitivity rankings are descriptive observed ranges over three fixed-seed
  manufactured conditions. They are not global sensitivity analysis,
  biological uncertainty, or calibration evidence, and the joint
  nutrient/oxygen sweep cannot attribute effects to either resource alone.

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
- The historical P1A inspection used a noncanonical branch. The canonical
  `v0.1.1-audit` tag remains outstanding and must only be created through its
  approved accepted-audit workflow.

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

## P2-WP02 – EPS model

- All three EPS parameters remain `CALIBRATION_REQUIRED`; manufactured SI
  inputs verify allocation, accumulation, accounting, and monotonic direction
  but are not biological values or benchmark claims.
- EPS is an immobile local density field. P2-WP02 specifies no matrix
  diffusion, degradation, recycling, or redistribution, so none is inferred.
- EPS mass is the biomass-equivalent fraction of gross anabolic production in
  the specified allocation equation. No unapproved EPS yield or composition
  conversion is introduced.
- Cohesion and attachment are relative dimensionless strength multipliers.
  An absolute adhesion force law, detachment threshold, and shear response
  remain outside P2-WP02 and must not be inferred from these modifiers.
- EPS is coupled through the component interface and optional output path; the
  Phase 1 reference orchestrator remains unchanged.

## P2-WP03 – Competition

- P2-WP03 adds no numeric biological values. Strain roles are categorical
  experiment configuration; all reused metabolism, quorum, and EPS values
  retain their existing provenance and `CALIBRATION_REQUIRED` status.
- The matrix benefit is limited to the existing local relative cohesion and
  attachment multipliers. No survival protection, force law, phenotype
  switching, dispersal, detachment, mutation, or evolution is inferred.
- Realized local fitness is a one-step per-capita biomass-change rate, not a
  calibrated selection coefficient. Nearest-neighbour segregation is a
  deterministic descriptive metric and has no inferred biological radius.
- The controlled tests establish software neutrality, configured production
  cost, conservation, and replay. They are not biological competition
  benchmarks or organism-specific outcome claims.
- Competition is exposed through the component and optional output interfaces;
  the Phase 1 reference orchestrator remains unchanged. Replicated competition
  experiments and sensitivity analysis remain P2-WP06.

## P2-WP04 – Physiological states

- All 13 physiological thresholds, delays, activity fractions, and recycling
  inputs remain `CALIBRATION_REQUIRED`; manufactured SI inputs validate the
  state machine and accounting but are not biological values or benchmarks.
- Either carbon or oxygen can drive limitation, dormancy, or death after its
  configured continuous delay. Recovery requires both solutes above the slow
  thresholds. This compact abstraction is not an organism-specific stress
  response or gene-regulatory model.
- The slow and dormant fractions scale both gross growth and the existing P1
  maintenance/death term. Dead and detached cells have zero metabolic activity.
  Quorum signal production remains the P2-WP01 whole-cell rule because P2-WP04
  specifies no state-dependent signal-production parameter.
- Recycled dead biomass transfers to a separately reported biomass ledger; it
  is not returned to carbon, oxygen, or EPS because composition and conversion
  yields are unspecified. Persisting dead biomass remains spatially retained.
- WP04 accepts only an explicit caller-selected detachment transition and
  excludes detached records from mechanics through a filter. It introduces no
  shear, force, exposure, attachment, EPS-resistance, or probability law from
  P2-WP05. The Phase 1 reference orchestrator remains unchanged.

## P2-WP05 – Waste and shear

- All seven waste and shear inputs remain `CALIBRATION_REQUIRED`; synthetic SI
  controls validate direction, accounting, and replay but are not biological
  calibration or benchmark evidence.
- Waste production is an explicit whole-cell source optionally scaled by the
  existing physiology activity fraction. No biomass-to-waste conversion,
  organism-specific toxic effect, or waste-feedback state transition is
  inferred.
- The uniform surface-parallel stress abstraction accumulates deterministic
  `Pa s` exposure. It is not a resolved velocity, force, hydrodynamic, or
  stochastic detachment model.
- Attachment and EPS only scale the configured exposure threshold through the
  declared attached-cell multiplier and existing local relative EPS attachment
  multiplier. No absolute adhesion force or unapproved EPS-removal rule is
  inferred.
- Shear selects IDs for the existing terminal physiology transition and output
  interface; the P1 reference orchestrator remains unchanged. P2-WP06
  experiments and sensitivity analysis remain out of scope.

## P2-WP06 – Experiments

- The repository campaign is a `CALIBRATION_REQUIRED` experiment definition;
  its unknown sweep levels are not biological values or completed calibration
  results. The harness is verified with explicitly synthetic fixed-seed inputs.
- The harness intentionally accepts a typed run executor instead of inventing
  a coupled P2 update order. Every executor must preserve the approved
  component contracts and emit the complete standard P2 raw artifact set.
- P2-WP06 supplies a production adapter and CLI binding for manufactured
  software-validation fixtures only. This remediated `P2A-001`; the independent
  2026-08-08 P2A rerun subsequently accepted the coupled application path.
- The published adapter has 11 strict root-level fixtures that expose all 15
  executable conditions exactly once, including separate intermixed and
  segregated inoculation paths, separate constitutive and quorum-controlled EPS
  paths, and the joint nutrient/oxygen sweep. This closes the P2-WP06 release
  surface identified by `P2A-002`; the independent 2026-08-08 P2A rerun
  subsequently accepted that release surface.
- Manufactured fixture values and outputs use SI labels but are deliberately
  separate from biological parameter records. They are not calibration,
  benchmark, or biological-result evidence. Fixture bytes are hashed as the
  campaign configuration, while the five biological TOML records remain
  separately hashed, provenance-complete, and `CALIBRATION_REQUIRED`.
- The reported quorum-active fraction is the population summary of the
  continuous P2-WP01 Hill activation response. No binary active/inactive
  threshold is inferred.
- Confidence intervals use a caller-recorded confidence level and Student's
  t interval over fixed-seed replicates. They describe replicate variation,
  not biological uncertainty or calibration quality.
- Sensitivity ranking is descriptive and limited to the absolute range of
  replicate means across the specified sweep conditions for each metric and
  time. It is not a global sensitivity model; the joint nutrient/oxygen sweep
  cannot attribute effects to either resource independently.
- P2-WP06 introduces no new biological mechanism, GUI, or P2A audit claim.
