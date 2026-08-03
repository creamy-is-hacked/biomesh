# Architecture

## Current architecture through P2-WP03

The typed P1 components are composed by a deterministic simulation layer. The
CLI exposes the numerical validators, calibration-placeholder reference run,
and metadata-driven reproduction. P2-WP01 adds an isolated quorum-signal
component and optional signal/history serialization without changing the P1
orchestrator or its default artifacts. P2-WP02 adds an isolated EPS allocation
and local-matrix component; the audited P1 path still uses zero allocation.
P2-WP03 composes those interfaces into categorical producer/nonproducer
competition and optional competition-history output.

Dependency direction is intentionally simple:

```text
CLI entry point -> validation + reference replay
validation      -> simulation orchestrator
simulation      -> configuration-owned inputs + completed P1 components
metabolism      -> cells + solutes
mechanics       -> cells
EPS             -> cells + metabolism + solutes + quorum state
competition     -> cells + metabolism + solutes + quorum state + EPS
outputs         -> cells + solutes + quorum state + optional EPS/competition state
quorum          -> cells + solutes
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
