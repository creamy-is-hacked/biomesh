# P6-WP03 Resume, Retry, and Recovery Across Hosts

P6-WP03 activates only a complete P6-WP02 `BOUND_NONRUNNABLE` record. It does
not change the canonical P6-WP01 manifest or P6-WP02 import/binding bytes.
Activation is an explicit destination operation that creates a fresh local P4
queue; import and binding remain non-runnable.

## Versioned activation boundary

The schema-version 1 `biomesh-portable-queue-activation` record is published
as `portable_activation.json` inside the new queue. It embeds the exact
canonical binding and its import/manifest hashes, the verified destination
resource policy, and one ordered mapping from each portable intent sequence to
a newly allocated local queue ID. It contains no source PID, process-start
identity, lock, cancellation/running/failure state, old queue ID/counter,
source resource receipt, local source queue path, authorization, trust grant,
or calibration promotion.

`queue activate-intent BOUND.json DESTINATION_QUEUE` validates the complete
binding, every bound project/campaign/fixture/execution/parameter/archive
identity, pending eligibility, and stable source/bound inputs while holding
all bound project locks. It then stages the P4 queue state, queue locks, worker
lock, and activation record and publishes the new queue atomically. Existing
targets, unsafe paths, incompatible/canonicality failures, changed inputs, or
publication races fail without a target. An activated queue cannot accept an
unbound local enqueue or mix another project.

`queue activate-intent BOUND.json DESTINATION_QUEUE --dry-run` performs the
same complete validation and stable revalidation without creating the queue.
After publication, `queue migration-status DESTINATION_QUEUE` read-only
verifies the canonical activation record against local queue identity and
resource policy; it does not perform worker recovery.

## Execution, retry, and recovery

After activation, the existing P4 worker lock, queue-state lock, project
campaign lock, OS CPU/memory enforcement, campaign resume, immutable artifact
publication, stale-worker reconciliation, cancellation, and explicit failed
run records remain the only execution boundaries. The destination queue gets
new scheduler IDs and receipts; source scheduler identity is not reused.

`queue retry DESTINATION_QUEUE QUEUE_ID` only requeues an explicit failed or
cancelled queue item with retained failed campaign runs. The next worker
invocation calls the existing campaign retry boundary, which schedules failed
runs only and never rewrites or reruns completed artifacts. Terminal completed
items are not retryable. Stale workers produce deterministic queue and campaign
audit transitions through the existing recovery path.

New destination run requests and completion receipts carry a strict portable
trace containing the portable manifest/item, source project-definition and
archive provenance, project/campaign/experiment/fixture, execution/model/
parameter/plugin identities, and run identity. Optional report generation can
receive the canonical binding with `campaign report --portable-binding`; its
portable traceability section keeps those identities separate from destination
host/platform/Python/project environment metadata.

## Validation evidence

On Python 3.14.4, the focused P6-WP03 collection passed 4 tests covering clean
CLI activation, atomic publication and conflicts, concurrent activation,
queue/project separation, completed-artifact retry immutability, tampered
binding failure atomicity, run receipt traceability, and report traceability.
The complete suite passed 372 tests with no failures, skips, or errors.
Ruff, strict mypy over 71 source files, module help, and `git diff --check`
passed in the isolated Python 3.14 environment. The P4 queue/project/report/
archive and P6-WP01/P6-WP02 regression tests are included in that full gate.

P6-WP04 operational migration documentation and P6A independent audit remain
incomplete. No cloud/remote scheduler, credential transfer, UI, scientific
change, calibration promotion, or 3D/acceleration behavior is included.
