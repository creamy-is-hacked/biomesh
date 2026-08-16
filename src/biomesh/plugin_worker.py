"""Single-message plugin worker entered only through the Linux sandbox."""

from __future__ import annotations

import ctypes
import ctypes.util
import importlib
import os
import signal
import sys
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

from biomesh.plugin_components import (
    BasePlugin,
    ExporterPlugin,
    ExportRequest,
    FieldPlugin,
    FieldStepRequest,
    KineticsPlugin,
    KineticsRequest,
    MetricPlugin,
    MetricRequest,
    SpeciesPlugin,
)
from biomesh.plugin_sandbox_types import (
    PLUGIN_SANDBOX_POLICY_VERSION,
    PluginSandboxRequest,
    PluginSandboxResponse,
    canonical_message_bytes,
    message_sha256,
)

_SCMP_ACT_ALLOW = 0x7FFF0000
_SCMP_ACT_TRAP = 0x00030000
_DENIED_SYSCALLS = (
    "accept",
    "accept4",
    "bind",
    "bpf",
    "clone",
    "clone3",
    "connect",
    "fork",
    "listen",
    "mount",
    "ptrace",
    "setns",
    "socket",
    "socketpair",
    "unshare",
    "vfork",
)


def main() -> int:
    """Read exactly one bounded request and emit exactly one response."""
    raw = sys.stdin.buffer.read()
    try:
        request = PluginSandboxRequest.model_validate_json(raw, strict=True)
        if request.sandbox_policy_version != PLUGIN_SANDBOX_POLICY_VERSION:
            return 73
        _install_seccomp_policy()
        signal.signal(signal.SIGSYS, _policy_violation)
        signal.signal(signal.SIGXCPU, _resource_limit)
    except Exception:
        return 72
    try:
        plugin = _load_plugin(request.entry_point_value)
        payload = _dispatch(plugin, request)
        response = PluginSandboxResponse(
            schema_version=1,
            plugin_api_version=1,
            sandbox_policy_version=request.sandbox_policy_version,
            plugin_id=request.plugin_id,
            plugin_version=request.plugin_version,
            selection_sha256=request.selection_sha256,
            operation=request.operation,
            request_sha256=message_sha256(raw),
            payload=payload,
        )
    except OSError:
        return 74
    except MemoryError:
        return 75
    except Exception:
        return 70
    sys.stdout.buffer.write(canonical_message_bytes(response))
    return 0


def _load_plugin(entry_point_value: str) -> BasePlugin:
    module_name, attribute = entry_point_value.split(":", maxsplit=1)
    loaded = getattr(importlib.import_module(module_name), attribute)
    if not callable(loaded):
        raise TypeError("entry point is not callable")
    factory = cast(Callable[[], object], loaded)
    plugin = factory()
    if not isinstance(plugin, BasePlugin):
        raise TypeError("plugin does not implement the base interface")
    return plugin


def _dispatch(plugin: BasePlugin, request: PluginSandboxRequest) -> dict[str, Any]:
    metadata = plugin.metadata()
    if (
        metadata.plugin_id != request.plugin_id
        or metadata.plugin_version != request.plugin_version
    ):
        raise ValueError("runtime plugin identity mismatch")
    operation = request.operation
    if operation == "initialize":
        components = [
            name
            for name, interface in (
                ("kinetics", KineticsPlugin),
                ("metric", MetricPlugin),
                ("species", SpeciesPlugin),
            )
            if isinstance(plugin, interface)
        ]
        # Field/export interfaces are structural and imported lazily by method name.
        if callable(getattr(plugin, "advance_field", None)):
            components.append("field")
        if callable(getattr(plugin, "export", None)):
            components.append("exporter")
        return {
            "metadata": metadata.model_dump(mode="json"),
            "components": sorted(components),
        }
    if operation == "self_check":
        return plugin.self_check().model_dump(mode="json")
    if operation == "species_definition":
        if not isinstance(plugin, SpeciesPlugin):
            raise TypeError("plugin has no species component")
        return plugin.species_definition().model_dump(mode="json")
    if operation == "evaluate_kinetics":
        if not isinstance(plugin, KineticsPlugin):
            raise TypeError("plugin has no kinetics component")
        kinetics_request = KineticsRequest.model_validate(
            request.payload,
            strict=True,
        )
        return plugin.evaluate_kinetics(kinetics_request).model_dump(mode="json")
    if operation == "advance_field":
        if not isinstance(plugin, FieldPlugin):
            raise TypeError("plugin has no field component")
        field_request = FieldStepRequest(**request.payload)
        return asdict(plugin.advance_field(field_request))
    if operation == "evaluate_metric":
        if not isinstance(plugin, MetricPlugin):
            raise TypeError("plugin has no metric component")
        metric_request = MetricRequest(**request.payload)
        return asdict(plugin.evaluate_metric(metric_request))
    if operation == "export":
        if not isinstance(plugin, ExporterPlugin):
            raise TypeError("plugin has no exporter component")
        export_request = ExportRequest(
            interface_version=request.payload["interface_version"],
            artifacts=tuple(tuple(item) for item in request.payload["artifacts"]),
            output_directory=Path("/export/output"),
        )
        return asdict(plugin.export(export_request))
    raise ValueError("unsupported plugin operation")


def _install_seccomp_policy() -> None:
    library_name = ctypes.util.find_library("seccomp")
    if library_name is None:
        raise RuntimeError("libseccomp is unavailable")
    library = ctypes.CDLL(library_name, use_errno=True)
    library.seccomp_init.argtypes = [ctypes.c_uint32]
    library.seccomp_init.restype = ctypes.c_void_p
    library.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    library.seccomp_syscall_resolve_name.restype = ctypes.c_int
    library.seccomp_rule_add.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_int,
        ctypes.c_uint,
    ]
    library.seccomp_rule_add.restype = ctypes.c_int
    library.seccomp_load.argtypes = [ctypes.c_void_p]
    library.seccomp_load.restype = ctypes.c_int
    library.seccomp_release.argtypes = [ctypes.c_void_p]
    context = library.seccomp_init(_SCMP_ACT_ALLOW)
    if not context:
        raise RuntimeError("seccomp initialization failed")
    try:
        for name in _DENIED_SYSCALLS:
            number = library.seccomp_syscall_resolve_name(name.encode("ascii"))
            if number < 0:
                continue
            if (
                library.seccomp_rule_add(
                    context,
                    _SCMP_ACT_TRAP,
                    number,
                    0,
                )
                != 0
            ):
                raise RuntimeError("seccomp rule installation failed")
        if library.seccomp_load(context) != 0:
            raise RuntimeError("seccomp policy activation failed")
    finally:
        library.seccomp_release(context)


def _resource_limit(_signum: int, _frame: object) -> None:
    os._exit(75)


def _policy_violation(_signum: int, _frame: object) -> None:
    os._exit(76)


if __name__ == "__main__":
    raise SystemExit(main())
