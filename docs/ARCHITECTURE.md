# Architecture

## M0 – Repository Bootstrap implementation

The current codebase contains a minimal `biomesh` Python package and a
typed command-line entry point. The command-line interface provides package
help and version discovery only; it has no simulation behavior.

Dependency direction is intentionally simple:

```text
CLI entry point -> biomesh package metadata
tests           -> public package/module command
```

Documentation and parameter provenance contracts are separate from runtime
code. CI installs the package and runs linting, type checking, and tests.

## P1-WP02 solute fields

`biomesh.solutes` implements independent carbon and oxygen finite-volume
fields. It accepts all transport and boundary-condition values from callers;
the module has no approved biological defaults. Its transport boundary
conditions are constant bulk concentration at the top, no flux at the bottom,
and periodic sides. Cell exchange is a small local data record mapped into
volumetric source terms without importing the future P1 cell or metabolism
modules.

```text
P1 caller -> biomesh.solutes
cell exchange record -> source-rate mapping -> carbon and oxygen fields
```

Simulation orchestration and scientific outputs remain unimplemented planned
P1 components. They must avoid coupling presentation or output layers back
into scientific calculations.

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
and enforces the solid bottom at `y = 0 m` after each iteration.

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
