# P4-WP05 Local Run Queue

P4-WP05 adds a persistent local scheduler around the accepted P4-WP01
campaign service. It changes neither campaign plans nor the P3 application
execution path and does not create a new scientific or plugin-loading path.

## Persistent records and ordering

A queue is a dedicated local directory containing strict schema-version 1
`queue_state.json`, a state lock, and a separate worker lock. State replacement
is atomic and every queue transition has a contiguous audit sequence. Each item
binds an absolute local project directory, campaign ID, caller-supplied integer
priority, stable enqueue sequence, lifecycle, worker identity, and exact
resource-limit receipt.

The single local worker selects the highest integer priority first. Equal
priorities retain FIFO enqueue order. Terminal items remain in queue history;
enqueueing never changes project state. A campaign may have at most one active
queue item, and only campaigns with pending runs are eligible.

## Resource boundary

Queue creation requires both a CPU-core count and memory limit in bytes. Before
claiming work, the worker applies Linux CPU affinity to exactly that many CPUs
and sets both the soft and hard `RLIMIT_AS` address-space limit to the requested
byte count. It reads both settings back and records the exact CPU IDs and memory
bytes on the queue item. Work does not start if the requested CPUs are no longer
available, the memory cap is already below the worker's current virtual-memory
requirement, or the operating system does not retain the exact limits.

A nonblocking worker lease permits only one drain process per queue, so the
declared CPU and memory boundary applies to the complete active queue worker,
not to an unbounded number of concurrent children. Execution stays on the
local machine; there is no remote service or cloud fallback.

## Progress, cancellation, and recovery

Queue status joins each persistent item to an atomic P4-WP01 campaign-state
snapshot. It exposes completed/failed/pending/running counts and an exact
completed-run numerator over planned-run denominator without waiting for a
running campaign lock. Every terminal status uses the full campaign verifier,
including completed artifact hashes and completion receipts.

Queued cancellation changes only queue state. Running cancellation records the
request, verifies the worker PID plus Linux process-start identity, and sends
`SIGTERM` only to that exact local process. The worker stops through a dedicated
base exception so a broad run-failure handler cannot continue later runs.
Publication already completed at the accepted atomic boundary remains
completed and immutable; an unpublished running run becomes an explicit
retryable `cancelled` campaign failure, while later planned runs remain pending.

On every status, enqueue, or drain operation, a persisted `running` item whose
exact worker identity is no longer live is reconciled. A published run is
recovered only from its hash-verified completion receipt. An unpublished run
becomes an explicit retryable `interrupted` failure. Completed artifacts are
reverified and never rerun or rewritten. Unstarted queued work remains queued
across application restarts.

## Application paths

```text
python -m biomesh queue create QUEUE_DIRECTORY \
  --cpu-cores CPU_COUNT --memory-limit-bytes BYTES
python -m biomesh queue enqueue QUEUE_DIRECTORY PROJECT_DIRECTORY CAMPAIGN_ID \
  [--priority INTEGER]
python -m biomesh queue status QUEUE_DIRECTORY
python -m biomesh queue run QUEUE_DIRECTORY [--once]
python -m biomesh queue cancel QUEUE_DIRECTORY QUEUE_ID
```

`queue run` is the local worker process; a desktop or shell may launch it in
the background. `--once` executes at most one selected campaign and is useful
for supervised workers. A drain returns failure status when any executed
campaign retains explicit failed runs. Use the existing intentional
`campaign retry` path before enqueueing retry work.

## Migration and scope boundary

There is no earlier persistent queue schema to migrate. Existing P4-WP01
project definitions, campaign state, completion receipts, raw artifacts,
P4-WP02 reports, P4-WP03 plugin identities/trust policy, and P4-WP04 registry
identities remain byte-compatible. Queue progress is orchestration metadata and
does not alter SI values, provenance, uncertainty, calibration status, raw-run
hashes, or report row/column traceability.

Queue project references are intentionally local absolute paths. Portable
project archives and path rebinding belong to P4-WP06. P4-WP05 adds no GUI,
archive, installer, acceleration, model equation, biological parameter,
automatic retry, automatic plugin trust, calibration claim, or cloud execution.
