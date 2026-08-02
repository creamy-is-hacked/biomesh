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

Mechanics, simulation orchestration, and scientific outputs remain
unimplemented planned P1 components. They must avoid coupling presentation or
output layers back into scientific calculations.

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
