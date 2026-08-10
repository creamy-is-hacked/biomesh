# Architecture

## Current architecture through P4-WP01

The typed P1 components are composed by a deterministic simulation layer. The
CLI exposes the numerical validators, calibration-placeholder reference run,
and metadata-driven reproduction. P2-WP01 adds an isolated quorum-signal
component and optional signal/history serialization without changing the P1
orchestrator or its default artifacts. P2-WP02 adds an isolated EPS allocation
and local-matrix component; the audited P1 path still uses zero allocation.
P2-WP03 composes those interfaces into categorical producer/nonproducer
competition and optional competition-history output. P2-WP04 adds a centralized
physiological state machine, optional activity fractions at the shared
metabolism boundary, and state-ledger output without changing the P1 path.
P2-WP05 adds waste transport and deterministic shear-exposure detachment.
P2-WP06 supplies the replicated campaign harness and the manufactured P2
application adapter exposed through the CLI.
P3-WP01 adds a synchronous application-service boundary that controls that
same adapter at accepted solver boundaries and returns only immutable values.
P3-WP02 adds UI-only desktop chrome, and P3-WP03 adds a PyQtGraph viewer that
consumes those immutable snapshots without constructing or mutating the engine.
P3-WP04 adds a schema-generated biological-parameter editor whose mutable
draft state can yield only existing immutable validated configuration models.
P3-WP05 adds one background owner for the synchronous service, exact accepted
P2 run selectors, boundary controls, checkpoint interaction, and immutable
cell-click inspection without changing the application or scientific layers.
P3-WP06 adds snapshot-only live analytics and one cancellable completed-run
export command on that existing worker. Canonical fields, tables, and run
metadata still originate only from the public application export operation.
P4-WP01 adds a versioned local project/campaign persistence layer above the
same synchronous public application service. It expands explicit sweep points
and deterministic seed policies into immutable run identities, records atomic
lifecycle transitions, and hash-verifies every completed artifact without
changing any accepted engine or GUI contract.

Dependency direction is intentionally simple:

```text
CLI entry point -> validation + reference replay
validation      -> simulation orchestrator
simulation      -> configuration-owned inputs + completed P1 components
metabolism      -> cells + solutes
mechanics       -> cells
EPS             -> cells + metabolism + solutes + quorum state
competition     -> cells + metabolism + solutes + quorum state + EPS
physiology      -> cells + solutes; supplies activity to metabolism/EPS/competition
outputs         -> cells + solutes + optional quorum/EPS/competition/physiology/waste/shear state
quorum          -> cells + solutes
shear           -> cells + EPS + physiology state labels
waste           -> cells + solutes + optional physiology activity
experiments     -> campaign schema + caller-supplied run executor + aggregation
P2 campaign     -> approved P2 interfaces + experiments + outputs
CLI entry point -> P1 paths + P2 validation/experiment/sweep/report paths
application     -> private P2 adapter state + immutable snapshots/checkpoints/exports
GUI viewer      -> immutable application snapshot value types + PyQtGraph
GUI editor      -> existing parameter schemas + isolated draft/persistence state
GUI controls    -> exact P2 RunRequest values + worker command queue
GUI worker      -> public ApplicationService operations only
GUI inspector   -> immutable CellInspection records only
GUI analytics   -> immutable RunSnapshot metrics only
GUI export      -> public completed export + immutable snapshot history
project/campaign -> public ApplicationService + accepted fixture identities
project state    -> atomic JSON + process lock + append-only audit sequence
tests           -> public component interfaces
```

Documentation and parameter provenance contracts remain separate from runtime
science. No orchestration value overrides the biological manifest.

## P1-WP02 solute fields

`biomesh.solutes` implements independent carbon and oxygen finite-volume
fields. It accepts all transport and boundary-condition values from callers;
the module has no approved biological defaults. Its transport boundary
conditions are constant bulk concentration at the top, no flux at the bottom,
and periodic sides. Cell exchange is a small local data record mapped into
volumetric source terms without importing the future P1 cell or metabolism
modules. Arrays are top-first while physical coordinates use `y = 0 m` at the
bottom; cell lookup reverses the vertical row index explicitly.

```text
P1 caller -> biomesh.solutes
cell exchange record -> source-rate mapping -> carbon and oxygen fields
```

Simulation orchestration consumes this interface without coupling output state
back into transport calculations.

## P1-WP04 metabolism

`biomesh.metabolism` depends on the completed cell and solute interfaces. It
samples both local solute concentrations at the start of a step, integrates
the specified biomass ODE exactly at those fixed concentrations, and maps
growth-associated whole-cell uptake back through the conservative solute
exchange interface. Caller-provided SI parameters contain all kinetic, yield,
and maintenance/death behavior; the module has no biological defaults.

```text
cells + solute fields + metabolism parameters -> biomesh.metabolism
biomesh.metabolism -> updated cells + conservative solute exchanges
```

Mechanics and future simulation/output layers may consume this interface, but
metabolism does not import them.

## P1-WP05 mechanics and attachment

`biomesh.mechanics` consumes and returns the immutable `Cell` records from
`biomesh.cells`; there is no mechanics-specific cell representation. Capsules
interact when the periodic-image distance between their centreline segments is
less than the sum of their radii. The deterministic, translation-only solver
applies pair corrections, maps horizontal centres through the periodic domain,
and enforces the solid bottom at `y = 0 m` after each iteration. Contact search
checks the neighboring periodic segment images rather than assuming the
nearest center image contains the closest capsule geometry.

Initial surface behavior is an explicit `bottom` or `none` configuration.
Bottom-attached cells remain tangent to the surface while retaining horizontal
mobility. Unattached cells cannot cross the bottom. The solver returns the
maximum unresolved overlap in metres on success and includes that metric in a
typed error when its caller-supplied iteration limit is exhausted.

```text
existing cells + mechanics parameters -> attachment/relaxation
attachment/relaxation -> existing cells + maximum-overlap metric
```

No rotational torque, adhesion force law, friction law, shear detachment, or
future-phase behavior is introduced by P1-WP05.

## P1-WP06 outputs

`biomesh.outputs` is a write-only consumer of the completed `Cell` and
`SoluteFields` interfaces. It emits canonical Parquet cell, summary, division,
and mass-balance tables plus deterministic compressed NumPy field archives.
The caller supplies complete run provenance and unit-aware mass-balance terms;
the output layer does not infer model inputs or scientific fluxes. It rejects
snapshots whose supplied balance residual exceeds the configured combined
absolute-plus-relative tolerance. Height is the maximum capsule-top elevation and
roughness is the population standard deviation of capsule-top elevations, both
in metres.

```text
cells + solute fields + run provenance -> biomesh.outputs
biomesh.outputs -> Parquet tables + compressed NumPy fields + metadata JSON
```

Output serialization does not mutate simulation state or feed data back into
the model.

## P1-WP07 orchestration and reproducibility

`biomesh.simulation` applies one recorded update order: coupled metabolism and
solute transport, seeded cell division, deterministic capsule relaxation,
global accounting, then output. It clones caller-owned fields, sorts cells by
identifier, uses one NumPy generator seeded from run metadata, and carries
surface attachment through division.

`biomesh.mass_balance` integrates the prescribed top-boundary finite-volume
flux. Periodic side transfers cancel and the bottom contributes zero flux.
Carbon and oxygen totals include their dry-biomass yield equivalents; death is
an explicit tracked outflow. Output records both the residual and relative
error and enforces the combined absolute-plus-relative tolerance.

`biomesh.provenance` records the Git commit when available, package and runtime
dependency versions, parameter-file identity and SHA-256, seed, platform, and
Python version. `biomesh.reference` copies the exact parameter documents and
byte-compares a metadata-driven replay.

The default reference uses an explicit normalized zero state because the
biological manifest remains `CALIBRATION_REQUIRED`. It exercises configuration,
serialization, provenance, and reproduction only. The full P1 update sequence
is exercised by the manufactured mass-balance validator with inputs labelled
non-scientific.

## P2-WP01 quorum signal

`biomesh.quorum` reuses one `SoluteField` for signal concentration in
`mol m^-3`. Cell-centre lookup and grid orientation are therefore identical to
the audited carbon and oxygen paths. Caller-supplied whole-cell basal and
induced rates are mapped conservatively into the containing control volume.
First-order degradation is combined with diffusion and production in one
explicit update after checking the tighter diffusion-degradation stability
limit.

Feedback production samples the local Hill response at the start of a step.
The accepted end-of-step field is sampled again, producing immutable,
chronological cell-local exposure and activation histories. The continuous
Hill fraction is recorded without inventing a binary activation threshold.
Each step reports signal production, degradation, top-boundary transfer, and a
discrete conservation residual.

`SimulationOutputWriter` accepts quorum state only when explicitly supplied. In
that mode it adds the signal array to each field archive and writes a canonical
`quorum_history.parquet` table. When quorum state is absent, the P1 artifact set
and serialization path are unchanged.

```text
cells + signal field + quorum parameters -> biomesh.quorum
biomesh.quorum -> updated signal + local histories + signal accounting
optional signal + histories -> biomesh.outputs
```

## P2-WP02 EPS model

`biomesh.eps` represents EPS as an immobile density field in `kg m^-3` on the
same top-first grid geometry used by the audited solute and quorum fields. Each
cell deposits EPS in the control volume containing its centre. P2-WP02 adds no
EPS diffusion, decay, recycling, or shear-driven removal because those terms
are not specified for this work package.

The existing continuous quorum activation supplies `Q`. The caller-provided
maximum allocation `f_EPS` gives `a = f_EPS Q`, and the shared metabolism
integrator applies `dX/dt = ((1-a)mu-k_d)X`. Full gross anabolic production is
charged to carbon and oxygen through the existing yield rules; the retained
fraction increases living biomass and the allocated fraction accumulates as
biomass-equivalent EPS. Each step reports both the EPS-pool residual and the
combined living-biomass-plus-EPS residual. P1 calls the same integrator through
its fixed zero-allocation interface, preserving audited behavior.

Local cohesion and attachment strength are exposed as dimensionless
multipliers `1 + sensitivity * EPS density`. This is a monotone mechanical
interaction without inventing an absolute force scale, threshold, or
detachment law. P2-WP05 may consume these modifiers when its separately
specified shear behavior is implemented.

`SimulationOutputWriter` can optionally serialize the EPS density array and a
total-EPS table. Omitting EPS preserves the P1 artifact path.

```text
cells + quorum state + solutes + EPS field -> biomesh.eps
biomesh.eps -> cost-adjusted cells + accumulated EPS + resource accounting
local EPS density + sensitivities -> cohesion and attachment multipliers
optional EPS field -> biomesh.outputs
```

## P2-WP03 competition

`biomesh.competition` assigns caller-named strains to the categorical roles
`producer` and `nonproducer`. Both roles are advanced together through the
existing metabolism and finite-volume resource update. Producers alone pass a
quorum-scaled allocation to the EPS model; nonproducers retain zero allocation
while sampling the same local EPS density and mechanical modifiers as any
co-located producer. The P2-WP02 default remains unchanged: omitting an
explicit producer-cell selection treats every cell as an EPS producer.

Each accepted step derives cell-count and dry-biomass frequencies, strain
summaries, preserved parent IDs, and realized per-capita biomass-change rates
in `s^-1`. Spatial segregation is the mean fraction of exactly equidistant
nearest neighbours with the same strain. Distance uses the existing periodic
horizontal domain and requires no neighbourhood-radius parameter.

`SimulationOutputWriter` optionally writes canonical competition summary,
strain, and cell tables. The cell table includes lineage, local fitness, EPS
allocation, local matrix density, and both relative mechanical modifiers.
Omitting competition state preserves all earlier output paths.

```text
strain roles + cells + quorum state + shared resources + EPS -> competition
competition -> role-specific EPS cost + shared matrix benefit + metrics
optional competition snapshot -> biomesh.outputs
```

## P2-WP04 physiological states

`biomesh.physiology` owns the only strict P2 physiological-state inventory:
active, slow, dormant, dead, and detached. Each cell has an immutable,
chronological history of local carbon and oxygen exposure plus continuous
limitation, dormancy, lethal, and recovery durations. Thresholds, delays, slow
and dormant activity fractions, and optional dead-biomass recycling are all
caller supplied in SI units.

The component returns per-cell activity fractions through the existing shared
metabolism interface. EPS and competition accept the same optional mapping, so
reduced activity consistently scales growth-associated resource consumption and
EPS production. Omitting the mapping preserves all P1 through P2-WP03 behavior.
Quorum production remains unchanged because WP04 specifies no state-dependent
production rule.

Dead cells are terminal and either retain biomass or transfer it by an explicit
first-order rate into a cumulative recycled-biomass ledger. No recycled mass is
silently assigned to a resource field. Detached is also terminal; WP04 accepts
only caller-selected detachments and provides a non-detached mechanics view,
leaving every shear and detachment law to P2-WP05.

Each snapshot partitions counts and retained dry biomass over all five states
and verifies that the totals equal the cell population. Optional canonical
physiology summaries expose active, slow, dormant, dead, detached, retained,
and recycled biomass without changing earlier output modes.

```text
cells + carbon/oxygen history + physiological parameters -> physiology
physiology -> states + activity fractions + dead/recycled/detached ledger
optional physiology snapshot -> biomesh.outputs
```

## P2-WP05 waste and shear

`biomesh.waste` reuses the audited finite-volume `SoluteField` geometry for a
waste concentration in `mol m^-3`. Caller-supplied whole-cell production rates
are mapped to local control volumes and may be scaled by the same physiological
activity mapping consumed by metabolism, EPS, and competition. First-order
removal and the prescribed top boundary are included in the explicit stability
limit and in the discrete molar accounting record. No biomass-to-waste yield or
waste toxicity law is inferred.

`biomesh.shear` accumulates deterministic uniform surface-parallel exposure in
`Pa s`. A non-detached cell is selected when exposure reaches the configured
base threshold multiplied by its caller-declared attachment resistance and its
local P2-WP02 EPS attachment-strength multiplier. The shear component returns
selected IDs and histories; `biomesh.physiology` owns the terminal detached
transition and reconciled biomass ledger. Detached cells are excluded from the
retained mechanics view, and the output layer records waste maps and shear
summaries only when those states are supplied.

```text
cells + activity + waste field + waste parameters -> waste transport + molar accounting
cells + EPS + attachment + shear parameters       -> selected detachment IDs
selected IDs + physiology                         -> terminal detached ledger
optional waste/shear state                        -> biomesh.outputs
```

This is a simplified exposure model, not CFD or a stochastic erosion law. All
seven waste/shear biological inputs remain external, SI-labelled, and
`CALIBRATION_REQUIRED`.

## P2-WP06 campaigns and application path

`biomesh.experiments` owns the strict campaign schema, condition/seed matrix,
raw-run contract, replicate statistics, and observed-range ranking. The
repository's `experiments/p2_wp06_campaign.toml` remains an unresolved
`CALIBRATION_REQUIRED` biological experiment definition; it cannot execute
until its unknown values are supplied with approved provenance.

`biomesh.p2_campaign` is a separate production adapter for manufactured
software validation. Eleven strict root-level JSON-compatible YAML fixtures
cover all 15 executable conditions exactly once: producer and nonproducer
monocultures, 50:50 competition, two inoculation patterns, constitutive and
quorum-controlled EPS, and quorum-threshold, joint nutrient/oxygen, EPS-cost,
and shear sweeps. Every condition runs at fixed seeds 101, 202, and 303.

Each manufactured run composes the approved interfaces in the recorded order:
quorum transport/local sensing, physiology activity, shared-resource
competition and EPS allocation, waste transport, shear selection, physiology
state/ledger update, retained-cell mechanics, and accounting/output. This
adapter introduces no new mutation, evolution, biological constant, or
calibration claim.

The CLI exposes `validate all`, `experiment`, `sweep`, and `report`. Each run
writes canonical P2 Parquet tables and NumPy field archives plus commit, seed,
environment, update-order, parameter-file, and SHA-256 provenance. Campaign
manifests preserve immutable raw artifact hashes. Aggregation writes per-time
replicate means, sample variances, and Student's t confidence intervals, plus
descriptive absolute ranges between specified sweep-condition means. Reports
validate the complete artifact tree before rendering a deterministic PNG.

```text
published fixture -> manufactured P2 adapter -> 3 fixed-seed raw runs per condition
raw runs           -> immutable hashes + replicate statistics + descriptive rankings
validated campaign -> deterministic PNG report
biological TOML records remain separately hashed and CALIBRATION_REQUIRED
```

The rankings characterize only the manufactured conditions supplied to each
sweep. They are not a global sensitivity analysis, biological uncertainty
estimate, or calibrated scientific result.

## P3-WP01 stable application API

`biomesh.application.ApplicationService` starts one condition/seed selected by
an existing P2 fixture, pauses and resumes only at accepted solver boundaries,
and advances exactly one interval per `step` call. The P2 adapter initializer,
single-step operation, and finalizer are shared with the unchanged CLI campaign
path, so both surfaces use the recorded scientific update order, fixed seed,
accounting, output writer, and parameter provenance.

The service owns all mutable cells, fields, histories, solver controls, and the
output writer in a private temporary run. Callers receive frozen cell, metric,
accounting, provenance, and inspection records. Field snapshots are copied to
immutable byte buffers and exposed as read-only NumPy views, so later GUI code
cannot mutate live arrays.

Checkpoints record the absolute fixture identity, fixture SHA-256, biological
parameter labels and SHA-256 values, condition, seed, calibration status, and
accepted step index. Resume verifies those inputs and deterministically replays
to the recorded boundary. It neither invents scientific values nor serializes
mutable solver internals. Export is limited to copying the completed canonical
P2 raw artifact set; additional formats remain P3-WP06.

```text
CLI campaign ----\
                  -> shared P2 initialize/step/finalize -> approved P2 components
application API -/                    |
                                       -> canonical outputs and provenance
private engine state -> immutable snapshot/checkpoint/inspection -> future GUI
```

The P3-WP01 boundary remains synchronous and headless. It imports no PySide,
desktop shell, renderer, experiment editor, worker, cancellation, live
analytics, or new biology.

## P3-WP02 desktop shell

`biomesh.gui` is a PySide6 Qt Widgets shell kept outside the application and
scientific modules. The main window owns only desktop chrome: File, View, and
Help menus; dockable project and error-console panels; a status bar; and an
explicit central placeholder for P3-WP03. It neither constructs an
`ApplicationService` nor imports scientific components.

Project menu entries are opaque absolute paths to existing readable files.
P3-WP02 records and displays these references but does not define a project
format, parse experiments, select parameters, or start a run. Missing files,
directories, unreadable paths, corrupt preferences, and invalid stored Qt
layout bytes produce visible error-console messages instead of fallback
scientific behavior.

The UI preference store uses versioned JSON at
`$XDG_CONFIG_HOME/biomesh/ui-preferences.json` (or the standard `~/.config`
fallback). It strictly permits only recent paths, window geometry, and dock
state, and writes atomically. It is structurally and physically separate from
`parameters/`, experiments, checkpoints, and run artifacts.

```text
desktop shell -> opaque recent paths + UI-only preferences
              -> error console + status bar + dock layout

desktop shell -X-> scientific core or mutable application state
```

Qt imports are confined to GUI modules. Headless widget tests launch them in
offscreen subprocesses, so the non-GUI scientific and reporting process does
not load Qt's bundled graphics libraries. P3-WP02 adds no viewer, editor,
worker, controls, inspection, analytics, or export behavior.

## P3-WP03 simulation viewer

`biomesh.gui.viewer.SimulationViewer` is the central desktop widget. It accepts
only complete immutable `RunSnapshot` values and retains at most the newest
pending snapshot when the configured frame-rate ceiling delays presentation.
It never imports `ApplicationService`, reads private solver state, advances a
simulation, or writes output.

PyQtGraph image items receive the five read-only `FieldSnapshot` arrays without
interpolation or scientific normalization. Capsule paths are rebuilt from the
frozen `CellSnapshot` geometry. Layer visibility is checked before either work
operation, and showing a formerly hidden layer uploads only that layer from the
latest immutable snapshot. Opacity changes affect graphics items only.

The P3-WP01 contract exposes cell geometry in metres and field array shape,
unit, and values, but no physical domain extent. The viewer therefore uses two
separate canvases: SI axes for cells and row/column axes for fields. This avoids
inventing a spatial alignment. Both canvases support mouse zoom and pan plus
explicit zoom, pan, and fit operations; layer controls provide value/unit
legends.

```text
immutable RunSnapshot -> frame limiter -> newest accepted snapshot
                                 |-> visible cells -> SI capsule path
                                 `-> visible fields -> exact grid image values

hidden layer -X-> per-frame path rebuild or image upload
viewer       -X-> application service, solver controls, inspection, or export
```

Headless acceptance tests use the real P2 application path at its reference
scale and compare each displayed scalar image to the canonical exported NumPy
array. P3-WP03 adds no simulation controls, checkpoint UI, cell inspection,
worker, analytics, new export, or scientific behavior.

## P3-WP04 experiment editor

`biomesh.gui.experiment_document` registers the five existing frozen Pydantic
biological-parameter schemas without copying their field rules or creating a
new scientific schema. `ExperimentEditorSession` holds mutable field text and
explicit validation errors separately from `ParameterDocument`, which contains
only an immutable validated schema instance. Invalid draft text has no
validated document and cannot save or become eligible for later run controls.
Schema-valid records retaining unresolved value or provenance fields remain
explicitly `CALIBRATION_REQUIRED` and run-ineligible.

`biomesh.gui.experiment_editor.ExperimentEditor` builds controls from
`BiologicalParameter.model_fields` and the parameter records accepted by the
selected schema. Names and validated SI units are read-only; value, source,
uncertainty, notes, and calibration status remain editable only in draft
sessions. Every validation error is displayed at its field, parameter, or
document boundary. UI preferences stay in their separate versioned JSON store.

Repository parameter files support two explicit modes. Templates create
unsaved editable copies without supplying values. Audited presets verify the
exact SHA-256 values accepted at P2A implementation revision
`6adb5def6f094762cb79ba3a2eddeede6007a2f5`, open read-only, and remain protected
from both direct save and editable-clone overwrite. Valid saves use a temporary
file in the target directory, reload through the same schema to verify equal
semantics, and then replace atomically. Existing user files require explicit
overwrite intent.

```text
existing parameter schema -> immutable ParameterDocument
                                     |
                                     v
                         isolated editable field text
                                     |
                            strict revalidation
                                     |
                 valid -> atomic TOML semantic round-trip
               invalid -> errors + no save/run eligibility

UI preferences -X-> parameter document or editor scientific configuration
GUI editor     -X-> application service, solver, worker, or run controls
```

P3-WP04 changes no biological equation, parameter schema, application request,
fixture, update order, output, or snapshot.

## P3-WP05 controls, checkpoints, and inspection

`biomesh.gui.simulation_worker.SimulationWorker` is the smallest asynchronous
boundary around the frozen synchronous service. One worker thread exclusively
owns one `ApplicationService`; every command calls only its public `run`,
`pause`, `step`, `resume`, `checkpoint`, `inspect`, or `close` operation. The
queue gives commands deterministic order, prioritizes stop over queued work,
and schedules continuous advancement only when neither pause nor stop is
pending. An interval already executing completes at its accepted solver
boundary before stop is accepted; after the worker publishes the stopped state,
no later interval is scheduled. A positive finite speed target changes only the
wall-clock delay between boundaries, never solver time or update order.

`SimulationControls` contains the exact 15 existing P2 fixture/condition pairs
and seeds 101, 202, and 303. `ApplicationService.run` remains the final strict
validator. Run and checkpoint-resume buttons additionally require the current
P3-WP04 document to be valid and fully resolved. That editor document is never
placed in `RunRequest`, so eligibility does not claim that arbitrary parameter
TOML is executable or establish a configuration-to-engine bridge.

The viewer performs deterministic capsule hit-testing against its latest
immutable `RunSnapshot` and emits only a cell ID. The worker verifies that the
selected step is still current through public inspection calls; a stale frame
fails explicitly instead of mixing boundaries. `CellInspector` displays the
returned immutable cell identity/parent, strain, dry biomass in kg,
physiological state, local carbon/oxygen/quorum/waste values, quorum activation,
and local EPS density. The frozen P3-WP01 record exposes no per-cell EPS
production rate, so the UI states that limitation instead of deriving one or
reading private solver state.

```text
exact P2 fixture + condition + seed -> RunRequest -> worker queue
                                                 -> ApplicationService
accepted boundary -> immutable RunSnapshot -> viewer -> cell ID
cell ID + expected step -> public inspect -> immutable CellInspection -> inspector

editor draft -> validation/run-eligibility gate only
editor draft -X-> RunRequest or engine configuration
GUI worker   -X-> private solver state
```

Focused offscreen tests cover button state transitions, deterministic
pause/single-step, stop/cancellation ordering, speed targeting, checkpoint
round-trip, worker error propagation, stale-frame rejection, and exact
inspection-record presentation. Analytics, live plots, new export formats,
campaign/project models, queues, acceleration, plugins, and new biology remain
outside P3-WP05.

## P3-WP06 analytics and export

`biomesh.gui.analytics.AnalyticsHistory` accepts only frozen `RunSnapshot`
values and orders them by solver step. It reads existing scalar metrics without
conversion. Population uses the immutable cell count corresponding to the
canonical summary table; the strain plot is labelled as the existing producer
cell frequency; penetration depth retains separate carbon and oxygen series.
Missing metrics or incorrect units fail explicitly.

`AnalyticsPanel` redraws PyQtGraph curves from that snapshot-only history. It
does not access the application service, mutable arrays, solver state, or
scientific modules. The same immutable records drive export CSV, Parquet, and
PNG values.

At completed state, `SimulationWorker.export_run` invokes
`ApplicationService.export` on its existing background thread. The composer
keeps canonical Parquet and NumPy bytes unchanged, validates stored population,
biomass, producer frequency, EPS, quorum response, thickness, and roughness
against the public records, then adds exact analytics tables and eight plot
PNGs. The manifest records sorted artifact hashes/sizes, seed, Git commit,
fixture hash, biological-parameter hashes, calibration status, and software
versions.

```text
immutable snapshots -> exact metric history -> live PyQtGraph curves
                                      |-> CSV + Parquet + PNG
completed service -> canonical export |-> byte-preserved fields + tables
                                      `-> hashed provenance manifest

cancel/error -> remove sibling staging directory -X-> partial target
success      -> one atomic directory replace
```

Cancellation is a thread-safe event checked between deterministic export
stages, so the Qt event loop remains responsive. This boundary creates no
persistent queue, project/campaign model, plugin, live export stream,
acceleration path, new metric calculation, unit conversion, calibration claim,
or scientific behavior.
