"""Linux process identity and resource enforcement for the P4-WP05 queue."""

from __future__ import annotations

import os
import resource
from pathlib import Path
from types import FrameType

from biomesh.local_queue_types import (
    AppliedResourceLimits,
    LocalQueueError,
    QueueItem,
    QueueResourceLimits,
)


class WorkerCancellation(BaseException):
    """Leave accepted execution at its current stable persistence boundary."""


def apply_resource_limits(limits: QueueResourceLimits) -> AppliedResourceLimits:
    """Apply and read back the exact Linux worker CPU/memory limits."""
    available = available_cpu_ids()
    if limits.cpu_cores > len(available):
        raise LocalQueueError(
            f"cpu_cores exceeds the {len(available)} CPUs available at worker start"
        )
    current_virtual_bytes = _current_virtual_memory_bytes()
    if limits.memory_limit_bytes < current_virtual_bytes:
        raise LocalQueueError(
            "memory_limit_bytes is below the worker's current virtual memory "
            f"requirement of {current_virtual_bytes} bytes"
        )
    selected = tuple(available[: limits.cpu_cores])
    try:
        os.sched_setaffinity(0, selected)
        resource.setrlimit(
            resource.RLIMIT_AS,
            (limits.memory_limit_bytes, limits.memory_limit_bytes),
        )
    except (OSError, ValueError) as error:
        raise LocalQueueError(
            f"unable to apply local resource limits: {error}"
        ) from error
    actual_cpu_ids = sorted(os.sched_getaffinity(0))
    actual_memory = resource.getrlimit(resource.RLIMIT_AS)
    if actual_cpu_ids != list(selected) or actual_memory != (
        limits.memory_limit_bytes,
        limits.memory_limit_bytes,
    ):
        raise LocalQueueError("operating system did not retain exact resource limits")
    return AppliedResourceLimits(
        cpu_ids=actual_cpu_ids,
        memory_limit_bytes=actual_memory[0],
    )


def available_cpu_ids() -> list[int]:
    """Return the CPU IDs currently available to this Linux process."""
    try:
        return sorted(os.sched_getaffinity(0))
    except AttributeError as error:
        raise LocalQueueError("local CPU affinity limits require Linux") from error


def cancel_worker(_signum: int, _frame: FrameType | None) -> None:
    """Convert a targeted termination signal into controlled unwinding."""
    raise WorkerCancellation


def process_start_ticks(pid: int) -> int:
    """Read the Linux process-start identity used to prevent PID reuse."""
    try:
        contents = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
        fields = contents.rsplit(") ", 1)[1]
        return int(fields.split()[19])
    except (OSError, ValueError, IndexError) as error:
        raise LocalQueueError(f"unable to verify local worker process {pid}") from error


def worker_identity_is_live(pid: int, start_ticks: int) -> bool:
    """Return whether the exact persisted local process still exists."""
    try:
        return process_start_ticks(pid) == start_ticks
    except LocalQueueError:
        return False


def item_worker_is_live(item: QueueItem) -> bool:
    """Return whether one validated running item retains a live worker."""
    assert item.worker_pid is not None
    assert item.worker_start_ticks is not None
    return worker_identity_is_live(item.worker_pid, item.worker_start_ticks)


def _current_virtual_memory_bytes() -> int:
    try:
        pages = int(Path("/proc/self/statm").read_text(encoding="ascii").split()[0])
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
    except (OSError, ValueError, IndexError) as error:
        raise LocalQueueError("unable to inspect local worker memory usage") from error
    return pages * page_size
