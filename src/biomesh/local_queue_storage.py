"""Atomic persistence and locks for the P4-WP05 local queue."""

from __future__ import annotations

import fcntl
import os
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from pydantic import ValidationError

from biomesh.local_queue_runtime import available_cpu_ids
from biomesh.local_queue_types import (
    QUEUE_LOCK,
    QUEUE_STATE,
    QUEUE_WORKER_LOCK,
    LocalQueueError,
    LocalQueueState,
    QueueAuditAction,
    QueueAuditRecord,
    QueueItem,
    QueueResourceLimits,
)


def create_local_queue(
    queue_directory: Path, *, cpu_cores: int, memory_limit_bytes: int
) -> Path:
    """Atomically create one persistent local-only queue."""
    limits = QueueResourceLimits(
        cpu_cores=cpu_cores,
        memory_limit_bytes=memory_limit_bytes,
    )
    available = available_cpu_ids()
    if limits.cpu_cores > len(available):
        raise LocalQueueError(
            f"cpu_cores exceeds the {len(available)} CPUs available to this process"
        )
    if queue_directory.exists() or queue_directory.is_symlink():
        raise LocalQueueError(f"queue directory already exists: {queue_directory}")
    if not queue_directory.parent.is_dir():
        raise LocalQueueError("queue directory parent must exist")
    state = LocalQueueState(
        schema_version=1,
        generation=0,
        next_sequence=0,
        resource_limits=limits,
        items=[],
        audit=[
            QueueAuditRecord(
                sequence=0,
                action="queue_created",
                detail="created persistent local queue with OS resource limits",
            )
        ],
    )
    temporary = Path(
        tempfile.mkdtemp(
            prefix=f".{queue_directory.name}.", dir=queue_directory.parent
        )
    )
    try:
        _write_bytes(temporary / QUEUE_STATE, state_bytes(state))
        (temporary / QUEUE_LOCK).touch()
        (temporary / QUEUE_WORKER_LOCK).touch()
        os.replace(temporary, queue_directory)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return queue_directory


class LocalQueueStore:
    """Small lock and atomic-state boundary for one local queue directory."""

    def __init__(self, queue_directory: Path) -> None:
        self.queue_directory = queue_directory

    @contextmanager
    def lock(self) -> Iterator[None]:
        """Serialize short queue-state reads and replacements."""
        lock_path = self.queue_directory / QUEUE_LOCK
        if (
            not self.queue_directory.is_dir()
            or not lock_path.is_file()
            or lock_path.is_symlink()
        ):
            raise LocalQueueError(
                f"not a BioMesh local queue directory: {self.queue_directory}"
            )
        try:
            with lock_path.open("r+") as lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                yield
        except OSError as error:
            raise LocalQueueError(f"unable to lock local queue: {error}") from error

    @contextmanager
    def worker_lock(self) -> Iterator[None]:
        """Acquire the queue's single-worker resource lease."""
        worker_lock_path = self.queue_directory / QUEUE_WORKER_LOCK
        if not worker_lock_path.is_file() or worker_lock_path.is_symlink():
            raise LocalQueueError("local queue worker lock is missing or is a symlink")
        try:
            with worker_lock_path.open("r+") as lock_file:
                try:
                    fcntl.flock(
                        lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB
                    )
                except BlockingIOError as error:
                    raise LocalQueueError(
                        "local queue already has an active worker"
                    ) from error
                yield
        except OSError as error:
            raise LocalQueueError(
                f"unable to lock local queue worker: {error}"
            ) from error

    def load(self) -> LocalQueueState:
        """Load one strict state only from the queue's regular state file."""
        state_path = self.queue_directory / QUEUE_STATE
        if not state_path.is_file() or state_path.is_symlink():
            raise LocalQueueError("local queue state is missing or is a symlink")
        try:
            return LocalQueueState.model_validate_json(
                state_path.read_text(encoding="utf-8")
            )
        except (OSError, ValidationError) as error:
            raise LocalQueueError(f"invalid local queue state: {error}") from error

    def write(self, state: LocalQueueState) -> None:
        """Atomically replace queue state with one validated model."""
        _atomic_write_bytes(
            self.queue_directory / QUEUE_STATE,
            state_bytes(state),
        )

    def write_if_changed(self, state: LocalQueueState) -> None:
        """Avoid a state replacement when restart reconciliation was a no-op."""
        path = self.queue_directory / QUEUE_STATE
        contents = state_bytes(state)
        if path.read_bytes() != contents:
            _atomic_write_bytes(path, contents)


def queue_item(state: LocalQueueState, queue_id: str) -> QueueItem:
    """Resolve one exact queue item or fail explicitly."""
    try:
        return next(item for item in state.items if item.queue_id == queue_id)
    except StopIteration as error:
        raise LocalQueueError(f"local queue has no item {queue_id!r}") from error


def append_transition(
    state: LocalQueueState,
    *,
    action: QueueAuditAction,
    item: QueueItem,
    detail: str,
) -> LocalQueueState:
    """Append one contiguous deterministic audit record."""
    audit = list(state.audit)
    audit.append(
        QueueAuditRecord(
            sequence=len(audit),
            action=action,
            queue_id=item.queue_id,
            detail=detail,
        )
    )
    return state.model_copy(update={"audit": audit})


def replace_item_transition(
    state: LocalQueueState,
    item: QueueItem,
    *,
    action: QueueAuditAction,
    detail: str,
) -> LocalQueueState:
    """Replace one item and append its transition as one state generation."""
    replaced = state.model_copy(
        update={
            "generation": state.generation + 1,
            "items": [
                item if current.queue_id == item.queue_id else current
                for current in state.items
            ],
        }
    )
    return append_transition(replaced, action=action, item=item, detail=detail)


def state_bytes(state: LocalQueueState) -> bytes:
    """Serialize one canonical persistent state payload."""
    validated = LocalQueueState.model_validate_json(state.model_dump_json())
    return (validated.model_dump_json(indent=2) + "\n").encode()


def _write_bytes(path: Path, contents: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(contents)
        stream.flush()
        os.fsync(stream.fileno())


def _atomic_write_bytes(path: Path, contents: bytes) -> None:
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
