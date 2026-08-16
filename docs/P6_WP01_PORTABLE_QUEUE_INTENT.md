# P6-WP01 Portable Queue Intent

P6-WP01 adds a read-only, versioned export boundary over the accepted P4-WP05
local queue. It transfers deterministic queued campaign intent and provenance;
it does not transfer a runnable queue, import or bind paths, or add remote
execution.

## Schema and canonical bytes

Schema version 1 uses manifest format `biomesh-portable-queue-intent`. Items are
ordered by the accepted P4 rule: descending integer priority and FIFO enqueue
order within equal priority. Each exported item receives a canonical contiguous
`intent_sequence` beginning at zero, so unrelated terminal queue history and
local enqueue counters cannot change equal intent bytes.

Each item carries:

- the complete immutable campaign record, project ID, and priority;
- the selected experiment ID, fixture SHA-256, and unchanged
  `CALIBRATION_REQUIRED` boundary;
- the complete execution identity and its canonical SHA-256, including exact
  registry, model, parameter-set, parameter-source, and zero-plugin identities;
- the exact source project-definition SHA-256; and
- when the project originated from an archive, the durable envelope/payload
  hashes and recorded authenticity/confidentiality provenance. Carried source
  status is explicitly not a destination trust decision.

Canonical serialization is UTF-8 JSON with sorted object keys, ASCII escaping,
compact separators, and one trailing newline. No timestamp, output path, queue
path, or other host-dependent publication metadata enters the bytes.

## Excluded local state

The manifest has no queue ID, local project or queue path, enqueue counter,
queue generation/audit trail, PID, process-start identity, lock, lifecycle
status, cancellation request, failure state, requested CPU/memory policy, or
applied resource receipt. Completed, failed, and cancelled queue history is not
exported. P6-WP02 must define explicit import and local path/resource rebinding;
P6-WP01 creates no imported or runnable item.

## Stable read-only export

Export acquires the existing nonblocking single-worker lease, the queue state
lock, and nonblocking project locks in deterministic path order. An active
worker, active project operation, live item, or stale running item fails before
manifest publication. The locks remain held through complete validation and
atomic publication.

Every queued reference must resolve to one safe regular project without
symlinked path components. Export verifies the strict queue and project
schemas, project definition/state binding, campaign plan, completed artifacts,
pending eligibility, accepted execution identity, fixture bytes, every
parameter-source byte, optional archive-source status, and a final unchanged
queue-state read. Missing, duplicate/ambiguous, unsafe, drifted, legacy,
incompatible, active, or stale references fail explicitly. The output must be
new and outside queue/project directories. Failure removes temporary output
and does not write queue state, project state, or completed artifacts.

## Application path

```text
python -m biomesh queue export-intent QUEUE_DIRECTORY \
  --output NEW_INTENT.json [--dry-run]
python -m biomesh queue migration-status NEW_INTENT.json
```

`--dry-run` performs the same complete read-only validation and stable
revalidation, returns the planned output path, SHA-256, and item count, and
skips publication. `migration-status` canonical-verifies the published record
without mutation. There is no
P6-WP01 import, bind, run, retry, recovery, migration, UI, cloud, remote
scheduler, credential, trust, calibration, science, or acceleration behavior.

## Validation evidence

On Python 3.14.4, 8 focused P6-WP01 tests cover positive CLI export, complete
dependency/source provenance, priority/FIFO ordering, byte determinism across
different local resource policy and terminal history, imported archive hashes,
active/stale/missing/symlinked/drifted/ambiguous rejection, strict forbidden
fields, nonblocking project activity, failure atomicity, existing-output
preservation, and exact queue/project byte immutability. The P4 queue,
portable-project, archive-security, and P6 collection passed 31 tests. The full
suite passed 360 tests with no failures or skips; Ruff, strict mypy over 67
source files, module help, and `git diff --check` also passed.
