"""Persistent, priority-ordered, OS-limited local queue for P4-WP05."""

from __future__ import annotations

import os
import signal
import time
from pathlib import Path

from biomesh.local_queue_runtime import (
    WorkerCancellation,
    apply_resource_limits,
    cancel_worker,
    item_worker_is_live,
    process_start_ticks,
    worker_identity_is_live,
)
from biomesh.local_queue_storage import (
    LocalQueueStore,
    append_transition,
    create_local_queue,
    queue_item,
    replace_item_transition,
)
from biomesh.local_queue_types import (
    AppliedResourceLimits,
    LocalQueueError,
    LocalQueueSnapshot,
    LocalQueueState,
    QueueAuditAction,
    QueueItem,
    QueueItemSnapshot,
    QueueItemStatus,
    QueueRunResult,
)
from biomesh.portable_queue_activation import (
    load_portable_queue_activation,
    portable_trace_for_queue_item,
    validate_portable_queue_state,
)
from biomesh.portable_queue_intent import export_portable_queue_intent
from biomesh.portable_queue_intent_types import PortableQueueIntentResult
from biomesh.project_campaign import CampaignService, CampaignStatus

__all__ = ["LocalQueueError", "LocalQueueService", "create_local_queue"]


class LocalQueueService:
    """Lock-protected persistent scheduler for local campaign processes."""

    def __init__(self, queue_directory: Path) -> None:
        self._queue_reference = queue_directory.absolute()
        self.queue_directory = queue_directory.resolve()
        self._store = LocalQueueStore(self.queue_directory)
        self._portable_activation = load_portable_queue_activation(self.queue_directory)

    def enqueue(
        self, project_directory: Path, campaign_id: str, *, priority: int
    ) -> QueueItem:
        """Persist one campaign request without beginning execution."""
        if self._portable_activation is not None:
            raise LocalQueueError(
                "activated portable queues cannot accept unbound local enqueue"
            )
        if isinstance(priority, bool):
            raise LocalQueueError("priority must be an integer")
        project = project_directory.resolve()
        campaign = CampaignService(project).status(campaign_id)
        if campaign.running:
            raise LocalQueueError("campaign already has a running synchronous run")
        if not campaign.pending:
            raise LocalQueueError("campaign has no pending runs to enqueue")
        with self._store.lock():
            state = self._reconcile(self._store.load())
            duplicate = next(
                (
                    item
                    for item in state.items
                    if item.project_directory == str(project)
                    and item.campaign_id == campaign_id
                    and item.status
                    in {QueueItemStatus.QUEUED, QueueItemStatus.RUNNING}
                ),
                None,
            )
            if duplicate is not None:
                raise LocalQueueError(
                    f"campaign already has active queue item {duplicate.queue_id}"
                )
            sequence = state.next_sequence
            queue_id = f"queue-{sequence:08d}-{campaign_id}"
            item = QueueItem(
                queue_id=queue_id,
                enqueue_sequence=sequence,
                project_directory=str(project),
                campaign_id=campaign_id,
                priority=priority,
                status=QueueItemStatus.QUEUED,
            )
            updated = append_transition(
                state.model_copy(
                    update={
                        "generation": state.generation + 1,
                        "next_sequence": sequence + 1,
                        "items": [*state.items, item],
                    }
                ),
                action="campaign_enqueued",
                item=item,
                detail=f"enqueued with priority {priority}",
            )
            self._store.write(updated)
            return item

    def status(self) -> LocalQueueSnapshot:
        """Reconcile stale workers and return deterministic run-level progress."""
        with self._store.lock():
            state = self._reconcile(self._store.load())
            validate_portable_queue_state(state, self._portable_activation)
            self._store.write_if_changed(state)
        snapshots = tuple(
            QueueItemSnapshot(item=item, campaign=self._campaign_status(item))
            for item in sorted(
                state.items, key=lambda current: current.enqueue_sequence
            )
        )
        return LocalQueueSnapshot(
            queue_directory=self.queue_directory,
            resource_limits=state.resource_limits,
            items=snapshots,
        )

    def export_intent(self, output: Path) -> PortableQueueIntentResult:
        """Publish one verified path-free snapshot of queued campaign intent."""
        return export_portable_queue_intent(self._queue_reference, output)

    def cancel(self, queue_id: str) -> QueueItem:
        """Cancel queued work or request termination of its local worker."""
        worker: tuple[int, int] | None = None
        with self._store.lock():
            state = self._reconcile(self._store.load())
            validate_portable_queue_state(state, self._portable_activation)
            item = queue_item(state, queue_id)
            if item.status is QueueItemStatus.QUEUED:
                cancelled = item.model_copy(
                    update={
                        "status": QueueItemStatus.CANCELLED,
                        "cancel_requested": True,
                    }
                )
                updated = replace_item_transition(
                    state,
                    cancelled,
                    action="campaign_cancelled",
                    detail="cancelled before local execution",
                )
                self._store.write(updated)
                return cancelled
            if item.status is not QueueItemStatus.RUNNING:
                raise LocalQueueError(
                    f"queue item {queue_id} is already {item.status.value}"
                )
            requested = item.model_copy(update={"cancel_requested": True})
            updated = replace_item_transition(
                state,
                requested,
                action="cancellation_requested",
                detail="requested orderly local worker termination",
            )
            self._store.write(updated)
            assert requested.worker_pid is not None
            assert requested.worker_start_ticks is not None
            worker = (requested.worker_pid, requested.worker_start_ticks)
        if worker_identity_is_live(*worker):
            # The queue state becomes RUNNING after prospective execution
            # preflight, while campaign startup still has to reacquire and
            # verify the project. Give that accepted startup a bounded window
            # to persist its first run boundary before delivering SIGTERM.
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                progress = CampaignService(
                    Path(requested.project_directory)
                ).progress(requested.campaign_id)
                if progress.running or not progress.pending:
                    break
                if not worker_identity_is_live(*worker):
                    break
                time.sleep(0.001)
            try:
                os.kill(worker[0], signal.SIGTERM)
            except ProcessLookupError:
                pass
        return requested

    def retry(self, queue_id: str) -> QueueItem:
        """Requeue explicit failed/cancelled work for one deterministic retry."""
        with self._store.worker_lock():
            with self._store.lock():
                state = self._reconcile(self._store.load())
                validate_portable_queue_state(state, self._portable_activation)
                item = queue_item(state, queue_id)
                if item.status not in {
                    QueueItemStatus.FAILED,
                    QueueItemStatus.CANCELLED,
                }:
                    raise LocalQueueError(
                        f"queue item {queue_id} is not retryable: {item.status.value}"
                    )
                campaign = CampaignService(Path(item.project_directory)).status(
                    item.campaign_id
                )
                if not campaign.failed:
                    raise LocalQueueError(
                        f"queue item {queue_id} has no explicit failed campaign runs"
                    )
                queued = item.model_copy(
                    update={
                        "status": QueueItemStatus.QUEUED,
                        "cancel_requested": False,
                        "failure": None,
                    }
                )
                updated = replace_item_transition(
                    state,
                    queued,
                    action="campaign_retry_scheduled",
                    detail="explicit retry scheduled for retained failed runs",
                )
                self._store.write(updated)
                return queued

    def run(self, *, once: bool = False) -> QueueRunResult:
        """Drain queued campaigns locally in priority/FIFO order."""
        with self._store.worker_lock():
            return self._run_locked(once=once)

    def _run_locked(self, *, once: bool) -> QueueRunResult:
        """Run while holding the queue's single-worker resource lease."""
        with self._store.lock():
            state = self._reconcile(self._store.load())
            validate_portable_queue_state(state, self._portable_activation)
            self._store.write_if_changed(state)
            limits = state.resource_limits
        applied = apply_resource_limits(limits)
        executed = completed = failed = cancelled = 0
        while True:
            item = self._claim_next(applied)
            if item is None:
                break
            executed += 1
            outcome = self._execute_claimed(item)
            completed += outcome is QueueItemStatus.COMPLETED
            failed += outcome is QueueItemStatus.FAILED
            cancelled += outcome is QueueItemStatus.CANCELLED
            if once:
                break
        return QueueRunResult(
            executed=executed,
            completed=completed,
            failed=failed,
            cancelled=cancelled,
        )

    def _claim_next(self, applied: AppliedResourceLimits) -> QueueItem | None:
        with self._store.lock():
            state = self._reconcile(self._store.load())
            validate_portable_queue_state(state, self._portable_activation)
            candidates = [
                item for item in state.items if item.status is QueueItemStatus.QUEUED
            ]
            if not candidates:
                self._store.write_if_changed(state)
                return None
            selected = min(
                candidates,
                key=lambda item: (-item.priority, item.enqueue_sequence),
            )
            CampaignService(Path(selected.project_directory)).preflight_execution(
                selected.campaign_id
            )
            started = selected.model_copy(
                update={
                    "status": QueueItemStatus.RUNNING,
                    "worker_pid": os.getpid(),
                    "worker_start_ticks": process_start_ticks(os.getpid()),
                    "applied_resources": applied,
                }
            )
            updated = replace_item_transition(
                state,
                started,
                action="campaign_started",
                detail="started in priority/FIFO order with enforced resource limits",
            )
            self._store.write(updated)
            return started

    def _execute_claimed(self, item: QueueItem) -> QueueItemStatus:
        previous_term = signal.signal(signal.SIGTERM, cancel_worker)
        try:
            execution_failure: str | None = None
            action: QueueAuditAction
            try:
                trace = (
                    None
                    if self._portable_activation is None
                    else portable_trace_for_queue_item(
                        self._portable_activation, item.queue_id, None
                    )
                )
                campaign_service = CampaignService(
                    Path(item.project_directory), portable_trace=trace
                )
                progress = campaign_service.progress(item.campaign_id)
                campaign = (
                    campaign_service.retry(item.campaign_id)
                    if progress.failed
                    else campaign_service.resume(item.campaign_id)
                )
                requested = self._current_item(item.queue_id).cancel_requested
            except WorkerCancellation:
                requested = True
                campaign = CampaignService(
                    Path(item.project_directory)
                ).recover_interrupted(
                    item.campaign_id,
                    cancellation_requested=True,
                )
            except Exception as error:
                requested = False
                execution_failure = (
                    f"local worker error: {str(error) or error.__class__.__name__}"
                )
                try:
                    campaign = CampaignService(
                        Path(item.project_directory)
                    ).recover_interrupted(item.campaign_id)
                except Exception as recovery_error:
                    execution_failure += (
                        "; campaign recovery failed: "
                        f"{str(recovery_error) or recovery_error.__class__.__name__}"
                    )
                    campaign = None
            if execution_failure is not None:
                status = QueueItemStatus.FAILED
                failure = execution_failure
                action = "campaign_failed"
                detail = failure
            elif campaign is not None and campaign.completed == campaign.total:
                status = QueueItemStatus.COMPLETED
                failure = None
                action = "campaign_completed"
                detail = f"completed {campaign.completed} immutable runs"
            elif requested:
                status = QueueItemStatus.CANCELLED
                failure = None
                action = "campaign_cancelled"
                detail = "local worker stopped at a persisted campaign boundary"
            elif campaign is not None and campaign.failed:
                status = QueueItemStatus.FAILED
                failure = f"campaign retained {campaign.failed} explicit failed runs"
                action = "campaign_failed"
                detail = failure
            else:
                status = QueueItemStatus.FAILED
                failure = "campaign worker ended without a terminal campaign state"
                action = "campaign_failed"
                detail = failure
            with self._store.lock():
                state = self._store.load()
                validate_portable_queue_state(state, self._portable_activation)
                current = queue_item(state, item.queue_id)
                terminal = current.model_copy(
                    update={
                        "status": status,
                        "cancel_requested": (
                            requested and status is QueueItemStatus.CANCELLED
                        ),
                        "worker_pid": None,
                        "worker_start_ticks": None,
                        "failure": failure,
                    }
                )
                self._store.write(
                    replace_item_transition(
                        state,
                        terminal,
                        action=action,
                        detail=detail,
                    )
                )
            return status
        finally:
            signal.signal(signal.SIGTERM, previous_term)

    def _current_item(self, queue_id: str) -> QueueItem:
        with self._store.lock():
            state = self._store.load()
            validate_portable_queue_state(state, self._portable_activation)
            return queue_item(state, queue_id)

    def _campaign_status(self, item: QueueItem) -> CampaignStatus:
        service = CampaignService(Path(item.project_directory))
        if item.status is QueueItemStatus.RUNNING and item_worker_is_live(item):
            return service.progress(item.campaign_id)
        return service.status(item.campaign_id)

    def _reconcile(self, state: LocalQueueState) -> LocalQueueState:
        validate_portable_queue_state(state, self._portable_activation)
        current = state
        for item in tuple(current.items):
            if item.status is not QueueItemStatus.RUNNING or item_worker_is_live(item):
                continue
            campaign = CampaignService(
                Path(item.project_directory)
            ).recover_interrupted(
                item.campaign_id,
                cancellation_requested=item.cancel_requested,
            )
            if campaign.completed == campaign.total:
                status = QueueItemStatus.COMPLETED
                failure = None
                detail = "recovered completed campaign after local worker exit"
            elif item.cancel_requested:
                status = QueueItemStatus.CANCELLED
                failure = None
                detail = "recovered cancelled work after local worker exit"
            elif campaign.failed:
                status = QueueItemStatus.FAILED
                failure = f"recovered worker left {campaign.failed} failed runs"
                detail = failure
            else:
                status = QueueItemStatus.QUEUED
                failure = None
                detail = "requeued campaign that had not begun execution"
            recovered = item.model_copy(
                update={
                    "status": status,
                    "cancel_requested": (
                        item.cancel_requested and status is QueueItemStatus.CANCELLED
                    ),
                    "worker_pid": None,
                    "worker_start_ticks": None,
                    "failure": failure,
                }
            )
            current = replace_item_transition(
                current,
                recovered,
                action="worker_recovered",
                detail=detail,
            )
        return current
