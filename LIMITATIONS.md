# Limitations

## Pre-v1 roadmap

- `docs/10_PRE_V1_ROADMAP.md` plans security/distribution hardening, portable
  operations, calibration/validation, 3D/acceleration, and v1 release gates.
  Planning does not close any P4A limitation; each remains in force until its
  implementation phase passes an independent audit.
- P7 cannot be completed by software work alone. It requires suitable licensed
  source data, predeclared methods, and qualified independent domain review.
- No new UI, cloud, clinical, automatic-parameter, post-v1, calibrated-science,
  GPU, 3D, or performance claim is authorized by the roadmap itself.

## P6 – Portable operations

- P6 transfers queued campaign intent, not live queue state. Source PID/process
  identity, locks, local paths, cancellation/running/failure state, terminal
  history, enqueue counters, and requested/applied resource receipts do not
  transfer. Activation always creates fresh destination scheduler identity.
- P4 archive import intentionally rewrites external fixture paths into a
  contained portable project definition. A clean-install migration therefore
  requires an explicit archive-imported source staging project/queue before
  intent export. Direct export binds only to destinations whose definition,
  state, dependency bytes, and archive provenance are already identical.
- Intent, import, binding, and activation schema 1 require the exact BioMesh
  0.6.0 record version. There is no negotiation, forward-schema handling,
  automatic upgrade/downgrade, reverse conversion, or direct P4 queue copy.
- `--dry-run` validates and revalidates without publication. Read-only
  `queue migration-status` verifies portable records and activated queue
  identity/resource policy but does not reconcile workers; `queue status`
  retains the accepted P4 recovery side effects.
- Destination paths and CPU/memory policy are operator supplied. Archive
  authenticity is provenance only; credentials, keys, trust, authorization,
  plugin/registry approval, and calibration status do not transfer. P6 remains
  local Linux operation with no cloud/remote scheduler, automatic path
  guessing, UI workflow, or performance recommendation.
- P6 implementation is frozen by `v0.6.0` only as an audit prerequisite.
  Phase 6 remains unaccepted until a fresh independent P6A passes.

## P5-WP01 – Threat model and security requirements

- `docs/P5_WP01_THREAT_MODEL.md` version 1.0.0 maps the P4A installed-build
  provenance, archive authenticity/confidentiality, plugin sandboxing, and
  installer lifecycle limitations to explicit controls, owners, verification,
  and residual risk. At the P5-WP01 baseline it defined requirements only; the
  owning P5 work packages and the 2026-08-15 P5A acceptance have since closed
  those mapped limitations within their documented residual-risk boundaries.
- P5-WP01 adds no installed provenance, signature, encryption, key material,
  sandbox, lifecycle behavior, incident evidence, or security guarantee.
  Checksums remain integrity evidence rather than signatures; provenance,
  authenticity, confidentiality, authorization, trust, and sandboxing remain
  separate properties.
- Residual risks include trusted-host/kernel compromise, unauthenticated legacy
  archive origin under explicit compatibility policy, deceptive but
  schema-valid sandboxed plugin output, bounded denial of service, and the
  inability of build provenance or archive signatures to establish scientific
  validity or calibration. Queue portability, biological validation, and
  3D/acceleration limitations remain assigned to P6-P8.

## P5-WP02 – Installed-build provenance

- A publishable P5 build now requires one complete wheel/sdist/Linux-installer
  publication directory and canonical manifest. The manifest and embedded
  records identify exact clean source and final artifact bytes, but SHA-256
  provenance is integrity evidence, not distributor authenticity,
  authorization, or trust. A consistently repackaged self-asserted set still
  requires an external release/authenticity policy.
- Build identity depends on the declared trusted Git, Python 3.14, Hatchling,
  and BioMesh builder toolchain. Root, host, runtime, or build-tool compromise
  is outside the control boundary.
- The embedded record is generated distribution metadata and therefore is not
  part of the committed source-tree identity. The external publication
  manifest carries each final raw artifact hash because an artifact cannot
  embed its own final raw hash without changing those bytes.
- Source-run metadata additionally records the exact commit, a domain-separated
  source/working-tree identity, and whether the source is clean or modified.
  The commit alone therefore is not treated as a complete identity for a
  modified source run. Dependency metadata is the complete declared direct
  runtime inventory from `pyproject.toml`; transitive host dependencies remain
  outside that labeled inventory.
- P5-WP02 adds no signature, key, confidentiality, archive envelope, plugin
  sandbox, upgrade, rollback, uninstall, automatic update, or broader
  installer supply-chain policy. Those remain P5-WP03 through P5-WP05 and must
  pass P5A before Phase 5 is accepted.

## P5-WP03 – Signed and optionally confidential archives

- Policy 1.0.0 selects only `BMAS-SIG-1-ED25519` and the optional
  `BMAS-ENC-1-HPKE-X25519-HKDF-SHA256-AES256GCM` suite. Schema or algorithm
  transitions require explicit new policy/code and host opt-in; there is no
  negotiation, fallback, guessing, downgrade, or transparent replacement.
- A verified signature authenticates exact archive/security bytes to one
  signer/key binding only after explicit out-of-band host trust. It does not
  authorize execution, grant plugin or registry trust, establish sandboxing,
  validate science, or promote `CALIBRATION_REQUIRED`. P5A still independently
  determines whether the Phase 5 controls are accepted.
- Confidentiality is separately requested and ends after authorized
  decryption. It protects only the declared archive envelope and does not
  protect plaintext from the authorized recipient, a compromised host, root,
  memory inspection, or later copying. Private-key custody remains outside
  BioMesh.
- Replay decisions are host-owned. BioMesh supplies an authenticated stable
  replay binding, a prohibited-binding set, and a pre-import policy hook; it
  does not invent a global replay store or retention policy. Replay-store
  unavailability and host-policy compromise remain residual risks.
- Legacy raw P4 archives remain readable only with explicit
  `--allow-unauthenticated` policy and receive durable `UNAUTHENTICATED` and
  `PLAINTEXT` status. Their historical origin cannot be proven or backfilled.
- Processing retains the accepted P4 100,000-member and 64 GiB expanded-size
  ceilings. These bounds do not guarantee availability under host-wide
  resource exhaustion. Python 3.14, `cryptography`, OpenSSL, the OS CSPRNG, and
  the supported local host remain in the trusted computing base.

## P5-WP04 – Isolated plugin execution

- Reviewed non-empty plugins now execute only through Linux Bubblewrap policy
  1.0.0, util-linux `prlimit`, and libseccomp. Linux, those enforcement tools,
  Python, the kernel, and explicitly mounted read-only runtime dependencies
  remain trusted; root, kernel, runtime, or same-account host compromise is
  outside the boundary.
- The sandbox denies project/host files, caller environment secrets, host
  network, mutable engine/completed state, and undeclared process capabilities.
  It does not make reviewed code benign or prevent deceptive but schema-valid
  output. Review, authorization, containment, calibration, and scientific
  validity remain separate.
- Wall, CPU, address-space, message/output, file-descriptor, and process limits
  bound one operation but cannot guarantee availability under host-wide
  exhaustion. A bounded plugin failure remains possible and explicit.
- Empty plugin selection starts no process and retains the accepted zero-plugin
  identity/path. No plugin is embedded in or trusted by project archives, and
  no UI was added. P5A accepted this boundary on 2026-08-15.
- The reviewed distribution root is content-bound: the selected entry-point
  module/package's regular-file inventory is rechecked before each operation
  for built-in and external plugins. Only the exact BioMesh package and its
  metadata, the selected plugin payload, and individual package roots from the
  declared runtime dependency inventory are mounted. The containing
  site-packages/environment/prefix and arbitrary distribution siblings are not
  mounted. This does not make reviewed code benign or remove the trusted
  runtime/kernel boundary.

## P5-WP05 – Installer lifecycle and supply-chain verification

- The lifecycle verifies exact P5-WP02 wheel/build/artifact-binding identities
  and owned installed bytes. SHA-256 provenance remains integrity evidence, not
  distributor authenticity. A consistently substituted self-asserted bundle,
  compromised host/root account, Python/pip compromise, or compromised build
  tool remains outside this control.
- Installation targets Linux x86_64/aarch64 and Python 3.14. Declared dependency
  availability and compatibility remain external; automatic update, system
  package integration, remote distribution, and cloud behavior are absent.
- Versions install side by side and one manifest-bound symlink activates them.
  Rollback can select only a retained exact verified version. Normal uninstall
  refuses modified/missing/extra state; explicit path acknowledgement retains
  the complete changed tree in a recovery quarantine and does not silently
  reclaim disk space or make that tree executable.
- Projects, archives, parameter files, queues, reports, configuration,
  completed artifacts, research data, and source datasets remain user-owned and
  outside removal. The lifecycle does not migrate or reinterpret any of them.
- Prefix preflight now rejects symlinks in `PREFIX`, `PREFIX/lib`,
  `PREFIX/bin`, and all lifecycle roots before writes. Recovery validates the
  journal's operation, phase, version/manifest identity, and derived stage
  names before constructing or deleting any path; recovery deletion remains
  limited to validated children of the transaction root.
- Transaction journal schema 2 binds exact source and target version,
  manifest, wheel, and provenance identities before smoke or any recovery side
  effect. Rollback recognizes only exact recorded source/target states. A
  mismatched or legacy schema-1 interrupted journal fails closed and remains
  available for explicit operator diagnosis.
- P5-WP05 adds no scientific validation, calibration, archive/plugin trust,
  queue portability, new UI behavior, release acceptance, or guarantee against
  storage exhaustion and interruption below filesystem atomicity. P5A accepted
  Phase 5 on 2026-08-15 without changing those boundaries.

## P4A – Phase 4 Audit

- The independent 2026-08-11 rerun accepted Phase 4 with recorded limitations
  from exact pushed prerequisite
  `b5bb3cf8ce12e67f6d80048aab2545e89bfcabe4`. No Critical or Major finding
  remains; `P4A-001`, `P4A-002`, and `P4A-003` are closed by fresh evidence.
- `experiments/platform_reference.yaml` is a manufactured two-condition,
  three-fixed-seed software-validation project. Its SI/provenance records and
  deterministic completion do not make it a biological experiment, calibration
  result, benchmark, or scientific conclusion.
- P4A recorded that installed distributions reported `commit_hash` as
  `UNKNOWN`. P5-WP02 closes that prospective installed-provenance limitation
  for verified BioMesh 0.5.0 publication sets by embedding the exact commit;
  historical P4 artifacts remain unchanged and are not backfilled.

## P4-WP07 – Experimental acceleration boundary

- The fixed benchmark is a synthetic dimensionless 48 by 48 two-dimensional
  software stencil. It does not execute or validate the BioMesh model and is
  not a biological, scientific, three-dimensional, or production workload.
- Experimental execution is disabled by default. The only opt-in candidate is
  NumPy float64 slice evaluation on the CPU; no GPU is detected, selected,
  exercised, supported, or claimed.
- CPU equivalence is limited to the declared case and `1e-12` absolute and
  relative engineering tolerances. The validated case measured zero divergence
  across 2,304 values, but this is not evidence for other inputs, models,
  hardware, precision, or scientific accuracy.
- Timing is optional and records raw local elapsed nanoseconds only. There is
  no warm-up, controlled environment, statistical inference, speedup ratio,
  transfer-cost study, scaling study, production performance claim, or hardware
  comparison.
- The benchmark module is not imported by accepted model execution. It cannot
  alter completed runs, projects, reports, plugin trust, registry identities,
  queue limits/recovery, archives, packages, or desktop behavior. Any future
  3D/GPU path requires separate implementation and audit.

## P4-WP06 – Portable projects and packaging

- Portable archives contain exact hash-verified project configurations,
  embedded manufactured fixtures, every required biological parameter
  document, completed artifact bytes, and completion receipts. They can execute
  a pending accepted software campaign on another clean clone or installation;
  they do not establish biological calibration, experimental validity, or
  scientific conclusions.
- Per-file SHA-256 and ZIP integrity detect accidental corruption. Archives are
  not digitally signed, encrypted, confidential, or proof of author identity.
  Import does not grant plugin trust or reinterpret registry identities.
- Queue state is local scheduler metadata and is not portable. Import creates a
  new project path; callers must explicitly enqueue it under separately chosen
  local CPU/memory limits. No cancellation or stale-worker state is migrated.
- New project/receipt schema version 2 records exact built-in registry,
  named/versioned model and parameter-set, and canonical empty plugin-set
  identities. These are provenance only: no registry bundle, registry trust,
  plugin code, or plugin approval is transferred. Legacy version 1 completed
  projects remain verifiable but cannot resume unfinished work or acquire
  backfilled provenance.
- The documented Linux bundle targets x86_64 or aarch64 Linux with Python 3.14.
  P4-WP06 originally supplied only a fresh installer. P5-WP05 supersedes that
  lifecycle limitation with verified upgrade, rollback, recovery, and
  ownership-safe uninstall while retaining the absence of automatic update and
  system-package integration. Generated projects, archives, reports, queues,
  and research data remain excluded.
- P4-WP06 adds no GUI archive action, cloud exchange, archive signing,
  acceleration, new biological value, calibration behavior, or P4-WP07/P4A
  result.

## P4-WP03 – Plugin API

- The accepted P1--P3 engine, P4 campaign runner, raw artifacts, and reports
  remain the zero-plugin path. P4-WP03 defines and verifies extension
  interfaces; it does not silently compose plugins into audited simulations or
  reinterpret completed runs.
- The complete plugin-set SHA-256 explicitly identifies an empty selection.
  This proves which set was selected; it is not approval, sandboxing, or
  evidence that any plugin code ran.
- The packaged species/kinetics plugin is a software extension example. Its
  species identity is non-taxonomic, all numeric kinetics inputs remain
  caller-supplied and provenance-complete, and its status remains
  `CALIBRATION_REQUIRED`. Passing its self-check is not biological validation,
  calibration, or benchmark evidence.
- Compatibility preflight validates the complete set before loading any entry
  point, including exact API, metadata hash, distribution/version,
  entry-point, and explicit review-policy identities. This prevents accidental
  incompatible or unreviewed loading; it is not a security sandbox.
- Approved Python plugin code executes with the BioMesh process's permissions.
  P4-WP03 automatically trusts only the packaged example. Third-party review,
  containment, revocation, signing, and permission isolation are not claimed.
- No model/parameter registry, persistent queue, portable archive, Linux
  application packaging, or acceleration behavior is added by P4-WP03.

## P3A – Phase 3 Audit

- The independent 2026-08-10 clean-clone rerun accepted Phase 3 with recorded
  limitations; no Critical or Major finding remains.
- Real desktop, worker, export, checkpoint, package, provenance, keyboard, and
  minimum-display application paths passed. This is software validation, not
  evidence of biological calibration or experimental validity.

- `parameters/phase2_reference.yaml` is a strict selector for the existing
  manufactured producer fixture. Seed 42 is an independent deterministic
  verification seed, not a biological parameter, calibration value, or an
  additional desktop campaign choice. The published P2 campaign and GUI remain
  restricted to seeds 101, 202, and 303.
- Frontend equivalence compares canonical bytes emitted by the P2 CLI runner
  boundary with bytes exported through the public P3 application service.
  Checkpoints remain hash-bound replay positions rather than serialized mutable
  solver state. Passing these commands proves software equivalence and replay,
  not biological validity.
- P3A accepts the frontend-equivalence and deterministic checkpoint-replay
  contracts at implementation commit
  `ed062935552c6a5df639c56474c7854cac91bd69`.
- The minimum supported desktop display is 1024×720. At that size, dock
  contents may require their local scroll bars; smaller displays are not
  claimed usable. Keyboard focus follows explicit lifecycle-control order and
  standard Qt navigation for the remaining widgets and menus.

## P3-WP06 – Analytics and export

- Live analytics retain only immutable public snapshots received during the
  current desktop session. Population is the exact stored cell count; “strain
  ratio” is the existing producer cell frequency, not a newly defined quotient.
  Carbon and oxygen penetration depth remain separate stored metric series.
- The application API exposes no physical field extent or additional
  penetration calculation. P3-WP06 therefore performs no unit conversion,
  spatial inference, resampling, thresholding, or missing-metric fallback.
- Completed export preserves canonical Parquet tables, NumPy fields, and run
  metadata byte-for-byte. PNG and exact long-form CSV/Parquet analytics are
  derived only from received immutable metric snapshots. A run resumed in a
  fresh desktop session can plot/export only public metric snapshots observed
  after that resume; missing earlier analytics are not reconstructed from
  private solver state.
- Export runs on the existing worker thread and accepts cancellation before
  atomic directory publication. It is a single completed-run operation, not a
  persistent queue, campaign/project model, plugin exporter, or live-streaming
  export service. P3A accepted these as recorded scope limitations.
- Biological parameters and campaign inputs remain `CALIBRATION_REQUIRED`.
  Plots and exports are software representations, not calibration evidence or
  biological validation. P3A accepted this bounded representation contract.

## P3-WP05 – Controls, checkpoints, and inspection

- Desktop runs remain limited to the 15 existing manufactured P2 fixture
  conditions and fixed seeds 101, 202, and 303. The editor document gates UI
  eligibility but is never passed to `RunRequest`; arbitrary edited parameter
  documents are not executable and no configuration-to-engine bridge exists.
- The worker serializes only public `ApplicationService` operations. Stop waits
  for an already executing interval to finish at an accepted solver boundary,
  then closes the service; no further boundary is scheduled after stop is
  accepted. Speed target affects wall-clock pacing only.
- Cell selection uses the latest immutable snapshot. Inspection is rejected if
  that frame is stale, and displayed values come only from immutable public
  records. P3-WP01 exposes local EPS density but no per-cell EPS production
  rate, so the inspector reports the value and explicitly marks the rate as
  unavailable rather than reading or deriving private state.
- P3-WP05 itself added no analytics, live plots, new export format,
  project/campaign model, persistent run queue, plugin, acceleration,
  calibration, or biology. P3-WP06 adds only the bounded analytics/export
  surface described above; P3A accepted this scope boundary.

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
  execution path. P3-WP05 wraps the unchanged service in a GUI worker without
  adding a configuration-to-engine bridge.

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
  `v0.1.1-audit` tag now identifies the accepted P1A commit through the
  approved accepted-audit workflow.

## Post-P3-WP04 repository remediation

- BM-008 and BM-009 remain deferred because the current repository contracts do
  not specify their required behavior sufficiently for a safe implementation.
- BM-010 is closed by P3A. Direct clean-clone worker, stop, export-cancellation,
  responsiveness, and actionable-error probes passed without a Critical or
  Major finding.

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
