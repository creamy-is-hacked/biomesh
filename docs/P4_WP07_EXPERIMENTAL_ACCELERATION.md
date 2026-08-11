# P4-WP07 Experimental Acceleration Boundary

P4-WP07 adds a versioned benchmark interface and one explicitly enabled,
CPU-only feasibility candidate. It does not change the accepted simulation,
application, campaign, plugin, registry, queue, archive, package, or desktop
paths.

## Benchmark contract

`biomesh.acceleration_benchmark` defines benchmark API version 1. A case binds
the workload identity, array shape, step count, dimensionless value unit,
fixed-edge boundary, and absolute and relative engineering tolerances. Each
backend declares its stable ID, implementation, experimental status, processor
kind, dimensionality, and whether a GPU was used. Results retain a canonical
little-endian float64 SHA-256, value count, and optional raw elapsed-time
observations. The report also binds the generated input SHA-256 and records the
BioMesh, Python, NumPy, platform, and machine identities needed to interpret
local measurements.

The versioned backend descriptor reserves explicit CPU/GPU and 2D/3D
identities for later reviewed work. That vocabulary is not an implementation
claim: the WP07 runner accepts only a 2D backend for its fixed case, and the
only supplied descriptors are CPU/2D with `gpu_used: false`.

The fixed feasibility case is a deterministic 48 by 48 synthetic
two-dimensional five-point stencil for four steps. It is not a BioMesh model,
biological parameter, scientific result, or three-dimensional workload. The
absolute and relative tolerances are both `1e-12`; they are software
feasibility thresholds for this case only, not experimentally sourced accuracy
requirements.

The scalar-loop CPU implementation is the reference. A candidate must return
the exact declared float64 shape with finite values. The report measures
maximum and mean absolute divergence, maximum relative divergence where
defined, mismatched value count, and `numpy.isclose` equivalence against the
CPU reference. Repeated timing executions must also reproduce their backend's
first result byte-for-byte.

## Disabled-by-default experimental candidate

The command below runs only the CPU reference. The report records
`experimental_default_enabled: false`, `experimental_status: DISABLED`, and no
candidate or divergence record:

```bash
python -m biomesh benchmark acceleration
```

The isolated NumPy slice candidate runs only with the explicit flag:

```bash
python -m biomesh benchmark acceleration --experimental
```

This candidate uses float64 NumPy operations on the CPU. It does not detect,
select, or execute a GPU and is not connected to simulation execution. On the
validated fixed case, all 2,304 values matched the CPU reference with zero
measured absolute or relative divergence at the declared tolerance.

## Artifacts and performance observations

Publish a new atomic report directory with:

```bash
python -m biomesh benchmark acceleration --experimental \
  --output NEW_BENCHMARK_DIRECTORY
```

The directory contains `acceleration_benchmark.json`. Existing targets are
rejected and publication failure leaves no partial target. Timing is separately
opt-in:

```bash
python -m biomesh benchmark acceleration --experimental \
  --timing-samples 3 --output NEW_BENCHMARK_DIRECTORY
```

Elapsed nanoseconds are raw local observations only. The report computes no
speedup, comparison ratio, statistical interval, ranking, or performance
claim. There is no warm-up policy, process isolation, hardware normalization,
transfer-cost measurement, memory benchmark, multi-size scaling study, or
production workload. Results from one host cannot establish performance on
another host.

## Accuracy and scope limitations

- Passing this synthetic case does not establish accuracy for the BioMesh
  solver, any biological model, other shapes, other tolerances, or other
  hardware.
- No 3D field, GPU kernel, GPU runtime, device transfer, parallel campaign
  execution, or production acceleration backend exists in P4-WP07.
- The candidate cannot be selected by a project, campaign, plugin, registry,
  queue, archive, package, or desktop run. Accepted completed artifacts remain
  immutable and use the unchanged CPU execution path.
- Any future 3D or GPU behavior requires separate approved implementation,
  equivalence evidence, limitations, and audit before it can be called
  validated.

There is no earlier benchmark schema or acceleration backend to migrate.
P4-WP07 adds no biological value, citation, calibration result, scientific
claim, cloud behavior, automatic plugin trust, archive identity, queue policy,
P4A audit result, merge, or tag.
