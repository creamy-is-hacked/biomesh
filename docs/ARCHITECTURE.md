# Architecture

## Current P1 architecture

The typed P1 components are composed by a deterministic simulation layer. The
CLI exposes the numerical validators, calibration-placeholder reference run,
and metadata-driven reproduction without adding presentation or Phase 2
behavior.

Dependency direction is intentionally simple:

```text
CLI entry point -> validation + reference replay
validation      -> simulation orchestrator
simulation      -> configuration-owned inputs + completed P1 components
metabolism      -> cells + solutes
mechanics       -> cells
outputs         -> cells + solutes
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
