# P6-WP02 Explicit Import and Local Rebinding

P6-WP02 adds a strict two-step destination boundary for a canonical P6-WP01
portable queue-intent manifest. Import produces only explicit `UNBOUND` state.
Rebinding produces only complete `BOUND_NONRUNNABLE` state. Neither operation
creates, updates, or activates a P4 local queue; execution, retry, and recovery
across hosts remain exclusively P6-WP03 work.

## Import record

Schema version 1 uses import format `biomesh-portable-queue-import`. The input
must be the exact canonical P6-WP01 byte encoding for the compatible BioMesh
version. Import validates the complete strict manifest, canonical order,
integer priorities, campaign and dependency identities, project/archive source
provenance, uniqueness, policies, and SHA-256 before publishing anything.

The deterministic import record embeds the complete source manifest and its
SHA-256. Every item repeats its complete portable intent under status
`UNBOUND`. It contains no local path, local resource policy, queue ID or
counter, PID/process-start identity, lock, cancellation/running/failure state,
or applied resource receipt. It grants no archive, plugin, registry, or other
destination trust and cannot be consumed by the P4 queue worker.

## Complete local binding

Binding requires exactly one explicit `PROJECT_ID=/absolute/local/project/path`
for every distinct source project and a new positive integer CPU-core and
memory-limit policy. Partial, duplicate, extra, ambiguous, relative,
traversing, symlinked, missing, or reused project paths fail before
publication. The requested core count must also fit the CPUs available to the
current process.

While holding every project campaign lock in deterministic path order, binding
verifies the complete project layout, definition/state binding, pending and
non-running campaign state, exact project/campaign/experiment/fixture identity,
complete accepted zero-plugin execution identity, parameter-source bytes,
completed artifacts, project-definition SHA-256, and optional archive-source
provenance. It repeats input, project, fixture, parameter, and archive checks
immediately before publication so changed-during-validation input fails.

The resulting schema-version 1
`biomesh-portable-queue-local-binding` record preserves the source manifest
order, priorities, campaign and dependency identities, hashes, and provenance.
It adds only the caller-supplied verified local paths and new local resource
policy. Every item has status `BOUND_NONRUNNABLE`, and the lifecycle policy
requires a future P6-WP03 activation step. No queue ID, enqueue counter, worker
identity, lock, terminal state, source policy, or source resource receipt is
transported or inferred.

Source archive authentication/confidentiality status remains provenance only.
The binding records `NOT_GRANTED` independently for destination archive trust,
plugin trust, registry trust, and authorization. Calibration remains exactly
`CALIBRATION_REQUIRED`.

## Atomic and path-safe publication

Both commands require a new regular-file target under a real non-symlinked
directory. Canonical bytes are staged, flushed, and atomically linked without
clobbering an existing target. Binding output is forbidden inside any bound
project. Validation or publication failure removes temporary state, leaves no
partial target, and does not change the source manifest, import record, local
projects, P4 queue state, or completed artifact bytes.

## Application paths

```text
python -m biomesh queue import-intent PORTABLE_INTENT.json \
  --output UNBOUND_IMPORT.json [--dry-run]

python -m biomesh queue bind-intent UNBOUND_IMPORT.json \
  --output BOUND_NONRUNNABLE.json \
  --project-binding PROJECT_A=/absolute/local/project-a \
  --project-binding PROJECT_B=/absolute/local/project-b \
  --cpu-cores 2 \
  --memory-limit-bytes 8589934592 [--dry-run]

python -m biomesh queue migration-status UNBOUND_IMPORT.json
python -m biomesh queue migration-status BOUND_NONRUNNABLE.json
```

`--dry-run` performs complete input/path/resource validation and stable
revalidation but skips publication. `migration-status` canonical-verifies and
identifies either record without mutation. P6-WP02 adds no bind guessing,
automatic trust, queue activation, execution,
retry, recovery, remote/cloud scheduler, credential transfer, UI, migration
matrix, scientific change, calibration promotion, or acceleration behavior.

## Validation evidence

On Python 3.14.4, 8 focused P6-WP02 tests cover positive CLI import and
complete rebinding, strict `UNBOUND`/`BOUND_NONRUNNABLE` separation, complete
identity/order/priority/provenance retention, deterministic bytes, archive and
calibration trust boundaries, malformed/incompatible/forbidden fields,
partial/duplicate/unsafe bindings, missing/drifted sources, target conflicts,
changed-during-validation input, failure atomicity, and exact source/queue/
project immutability. The focused P6/P4 queue/project/archive collection passed
49 tests. The complete suite passed 368 tests with no failures or skips; Ruff,
strict mypy, module help, and `git diff --check` also passed on 2026-08-16.
