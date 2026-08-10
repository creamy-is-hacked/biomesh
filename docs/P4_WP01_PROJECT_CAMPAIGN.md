# P4-WP01 Project and Campaign Model

P4-WP01 adds a local, synchronous persistence boundary above the accepted P3
`ApplicationService`. It does not change the P1–P3 engine, GUI, biological
parameter schemas, update order, artifacts, or calibration status.

## Versioned records

`project.json` is an immutable, strict JSON `schema_version = 1` definition:

- `ProjectRecord` stores project identity, title, and purpose.
- `ExperimentRecord` binds an experiment to an exact fixture SHA-256 and keeps
  its overall status `CALIBRATION_REQUIRED`.
- `CampaignRecord` identifies the experiment, replicate count, seed policy,
  and explicit sweep matrix.
- `SweepPoint` names one accepted fixture condition and repeats its exact
  SI-labelled, source-, uncertainty-, notes-, and calibration-status-complete
  parameter overrides. A mismatch fails before project creation or execution.

`campaign_state.json` is mutable only through an atomic sibling-file replace:

- `RunRecord` carries a deterministic run ID, point, replicate index, seed,
  status, attempt count, artifacts, and an explicit retryable failure.
- `ArtifactRecord` binds every completed output file to its contained relative
  path, byte size, and SHA-256.
- `AuditRecord` is an append-only, contiguous sequence of lifecycle actions.
  It avoids wall-clock values so equal action sequences remain deterministic.

The project directory also contains `.campaign.lock` and `artifacts/<run-id>`.
The lock serializes process mutations; it is not a P4-WP05 run queue.

## Seeds and sweep matrix

An `explicit` seed policy requires exactly one unique nonnegative seed per
replicate. A `sequence` policy requires a nonnegative start and positive step.
Run planning expands sweep points in definition order and replicates in seed
order, then derives stable path-safe run IDs from the complete plan identity.

P4-WP01 does not create arbitrary configuration-to-engine behavior. Every
sweep point must select an existing condition from its hash-bound accepted P2
fixture, and its parameter records must equal that condition's existing
overrides byte-for-semantics. Unknown biological records remain configurable
and `CALIBRATION_REQUIRED`; manufactured fixture values are not calibration or
biological evidence.

## Resume, completion, and retry

Before a run, state is atomically persisted as `running`. The executor writes
to a sibling staging directory. Successful output is hashed, a completion
receipt is written, and the directory is atomically published before state is
marked `completed`.

On resume, a prior `running` record with no published receipt becomes an
explicit `interrupted` failure. A published receipt is accepted only when its
run identity, attempt, file set, sizes, and hashes all validate. Completed runs
are never scheduled by resume or retry, and any later artifact change fails
closed. Failed runs retain their error and attempt count until `campaign retry`
is explicitly requested.

## CLI application paths

```text
python -m biomesh project create DEFINITION.json PROJECT_DIRECTORY
python -m biomesh campaign status PROJECT_DIRECTORY CAMPAIGN_ID
python -m biomesh campaign resume PROJECT_DIRECTORY CAMPAIGN_ID
python -m biomesh campaign retry PROJECT_DIRECTORY CAMPAIGN_ID [--run-id RUN_ID]
```

`resume` and `retry` execute sequentially through the public P3 service and
preserve its exact fixture, deterministic seed, solver-boundary, and canonical
raw-export contracts. A failed run does not stop independent pending runs, but
either operation returns exit status 1 while retryable failures remain. Input,
schema, or persistence errors return exit status 2.

## Migration and scope boundary

There is no earlier project schema to migrate. P3 recent-project entries remain
opaque paths, and existing standalone run directories are not silently adopted
or rewritten. Portable archive import/export belongs to P4-WP06.

P4-WP01 includes no comparison/report metrics, persistent background queue,
priorities, cancellation, plugins, model/parameter registry, Linux packaging,
archive transport, GPU/3D path, cloud behavior, or new scientific mechanism.
