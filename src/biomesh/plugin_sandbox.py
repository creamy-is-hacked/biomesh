"""Least-privilege out-of-process Linux execution for reviewed plugins."""

from __future__ import annotations

import hashlib
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path, PurePosixPath
from typing import Any, cast

from pydantic import BaseModel, ValidationError

from biomesh.plugin_components import (
    ExportRequest,
    ExportResult,
    FieldStepRequest,
    FieldStepResult,
    KineticsResult,
    MetricRequest,
    MetricResult,
    PluginError,
    PluginMetadata,
    PluginSelfCheck,
    SpeciesDefinition,
)
from biomesh.plugin_sandbox_types import (
    PLUGIN_SANDBOX_POLICY_VERSION,
    PluginExecutionOutcome,
    PluginExecutionReceipt,
    PluginOperation,
    PluginResourceLimits,
    PluginSandboxError,
    PluginSandboxPolicy,
    PluginSandboxRequest,
    PluginSandboxResponse,
    canonical_message_bytes,
    default_plugin_sandbox_policy,
    message_sha256,
)

_BWRAP_PATH = Path("/usr/bin/bwrap")
_PYTHON_PATH = Path("/usr/bin/python")
_PRLIMIT_PATH = Path("/usr/bin/prlimit")
_MINIMUM_BWRAP_VERSION = (0, 8, 0)
_DECLARED_RUNTIME_DISTRIBUTIONS = (
    "biomesh",
    "cryptography",
    "matplotlib",
    "numba",
    "numpy",
    "pyarrow",
    "pydantic",
    "pydantic-core",
    "pyqtgraph",
    "PySide6",
    "scipy",
    "annotated-types",
    "typing-extensions",
    "typing-inspection",
)


@dataclass(frozen=True, slots=True)
class PluginDistribution:
    """One entry-point payload narrowed to an immutable mounted inventory."""

    root: Path
    mount_source: Path
    mount_target: str
    inventory: tuple[tuple[str, int, str], ...]


def inspect_plugin_distribution(
    root: Path, entry_point_value: str
) -> PluginDistribution:
    """Resolve only the entry-point module/package and inventory its regular files."""
    resolved_root = root.resolve()
    if (
        not resolved_root.is_dir()
        or root.is_symlink()
        or resolved_root in {Path("/"), Path.home().resolve(), Path.cwd().resolve()}
    ):
        raise PluginError("reviewed plugin distribution root is unavailable")
    _reject_symlink_chain(resolved_root)
    try:
        module_name, _attribute = entry_point_value.split(":", maxsplit=1)
    except ValueError as error:
        raise PluginError("reviewed plugin entry point value is malformed") from error
    parts = module_name.split(".")
    if not module_name or any(not part.isidentifier() for part in parts):
        raise PluginError("reviewed plugin entry point module is malformed")
    module_file = resolved_root.joinpath(*parts).with_suffix(".py")
    module_package = resolved_root.joinpath(*parts)
    package_root = resolved_root / parts[0]
    file_exists = module_file.is_file() and not module_file.is_symlink()
    package_exists = (
        module_package.is_dir()
        and not module_package.is_symlink()
        and (module_package / "__init__.py").is_file()
    )
    if file_exists and package_exists:
        raise PluginError("reviewed plugin entry point module is ambiguous")
    if not file_exists and not package_exists:
        raise PluginError("reviewed plugin entry point module is unavailable")
    if package_root.is_dir() and not package_root.is_symlink():
        mount_source = package_root
        mount_target = f"/opt/plugin/{parts[0]}"
    else:
        mount_source = module_file
        mount_target = f"/opt/plugin/{module_file.name}"
    _reject_symlink_chain(mount_source)
    resolved_source = mount_source.resolve()
    if not resolved_source.is_relative_to(resolved_root):
        raise PluginError("reviewed plugin payload escapes its distribution root")
    inventory = _plugin_inventory(resolved_root, resolved_source)
    if not inventory:
        raise PluginError("reviewed plugin distribution payload is empty")
    return PluginDistribution(
        root=resolved_root,
        mount_source=resolved_source,
        mount_target=mount_target,
        inventory=inventory,
    )


def _plugin_inventory(root: Path, source: Path) -> tuple[tuple[str, int, str], ...]:
    paths: list[Path] = []
    if source.is_file():
        paths.append(source)
    elif source.is_dir():
        for directory, names, filenames in os.walk(source, followlinks=False):
            directory_path = Path(directory)
            for name in names:
                child = directory_path / name
                if child.is_symlink():
                    raise PluginError("reviewed plugin payload contains a symlink")
            for name in filenames:
                path = directory_path / name
                if path.is_symlink() or not path.is_file():
                    raise PluginError(
                        "reviewed plugin payload contains a non-regular file"
                    )
                paths.append(path)
    else:
        raise PluginError("reviewed plugin payload is unavailable")
    result = tuple(
        (
            path.relative_to(root).as_posix(),
            path.stat().st_size,
            _file_sha256(path),
        )
        for path in sorted(paths)
    )
    return result


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reject_symlink_chain(path: Path) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if current.is_symlink():
            raise PluginError(f"reviewed plugin path uses symlink: {current}")
        if not current.exists():
            break


def _distribution_inventory_matches(
    distribution_payload: PluginDistribution,
) -> bool:
    try:
        return _plugin_inventory(
            distribution_payload.root,
            distribution_payload.mount_source,
        ) == distribution_payload.inventory
    except (OSError, PluginError):
        return False


@dataclass(frozen=True, slots=True)
class PluginOperationResult:
    """One fully validated result and its immutable execution provenance."""

    value: object
    receipt: PluginExecutionReceipt


@dataclass(frozen=True, slots=True)
class SandboxPluginRuntime:
    """Exact reviewed identity and declared code root used by a proxy."""

    plugin_set_sha256: str
    plugin_id: str
    plugin_version: str
    selection_sha256: str
    entry_point_value: str
    distribution_root: Path
    policy: PluginSandboxPolicy
    distribution: PluginDistribution | None = None

    def execute(
        self,
        operation: PluginOperation,
        payload: Mapping[str, Any] | None = None,
        *,
        export_output: Path | None = None,
    ) -> PluginOperationResult:
        request = PluginSandboxRequest(
            schema_version=1,
            plugin_api_version=1,
            sandbox_policy_version=self.policy.policy_version,
            plugin_id=self.plugin_id,
            plugin_version=self.plugin_version,
            selection_sha256=self.selection_sha256,
            entry_point_value=self.entry_point_value,
            operation=operation,
            payload=dict(payload or {}),
        )
        request_bytes = canonical_message_bytes(request)
        request_hash = message_sha256(request_bytes)
        self._preflight(request, request_bytes)
        temporary_output: Path | None = None
        if export_output is not None:
            if export_output.exists() or export_output.is_symlink():
                self._fail(
                    operation,
                    request_hash,
                    "preflight_denied",
                    "export output directory must not already exist",
                )
            if not export_output.parent.is_dir():
                self._fail(
                    operation,
                    request_hash,
                    "preflight_denied",
                    "export output parent must exist",
                )
            try:
                temporary_output = Path(
                    tempfile.mkdtemp(
                        prefix=f".{export_output.name}.plugin-",
                        dir=export_output.parent,
                    )
                )
            except OSError:
                self._fail(
                    operation,
                    request_hash,
                    "communication_failure",
                    "private plugin output staging could not be created",
                )
        try:
            response_bytes, return_code, sandbox_ready = self._run(
                request_bytes,
                temporary_output,
            )
            response = self._validate_response(
                operation,
                request_hash,
                response_bytes,
                return_code,
                sandbox_ready,
            )
            try:
                value = _validate_payload(operation, response.payload)
            except PluginError:
                self._fail(
                    operation,
                    request_hash,
                    "malformed_output",
                    "plugin result failed host schema validation",
                )
            if operation == "advance_field":
                assert isinstance(value, FieldStepResult)
                if (
                    value.field_id != request.payload.get("field_id")
                    or value.unit != request.payload.get("unit")
                    or value.shape != tuple(request.payload.get("shape", ()))
                ):
                    self._fail(
                        operation,
                        request_hash,
                        "malformed_output",
                        "field result identity, unit, or shape differs from request",
                    )
            if operation == "export":
                assert temporary_output is not None
                assert export_output is not None
                assert isinstance(value, ExportResult)
                generated_output = temporary_output / "output"
                try:
                    _validate_exported_files(generated_output, value)
                except PluginError:
                    self._fail(
                        operation,
                        request_hash,
                        "malformed_output",
                        "exported bytes differ from declared result identity",
                    )
                try:
                    os.replace(generated_output, export_output)
                except OSError:
                    self._fail(
                        operation,
                        request_hash,
                        "communication_failure",
                        "validated plugin output could not be published atomically",
                    )
            receipt = self._receipt(
                operation,
                request_hash,
                "success",
                message_sha256(response_bytes),
                "isolated operation completed and host validation passed",
            )
            return PluginOperationResult(value=value, receipt=receipt)
        finally:
            if temporary_output is not None:
                shutil.rmtree(temporary_output)

    def _preflight(self, request: PluginSandboxRequest, request_bytes: bytes) -> None:
        if sys.platform != "linux":
            self._fail(
                request.operation,
                message_sha256(request_bytes),
                "setup_failure",
                "isolated plugins require the supported Linux sandbox",
            )
        if self.policy.policy_version != PLUGIN_SANDBOX_POLICY_VERSION:
            self._fail(
                request.operation,
                message_sha256(request_bytes),
                "setup_failure",
                "sandbox policy version mismatch",
            )
        if len(request_bytes) > self.policy.max_message_bytes:
            self._fail(
                request.operation,
                message_sha256(request_bytes),
                "preflight_denied",
                "plugin request exceeds the declared message limit",
            )
        package_root = Path(__file__).resolve().parent.parent
        if self.distribution_root == package_root:
            if self.distribution is None:
                self._fail(
                    request.operation,
                    message_sha256(request_bytes),
                    "preflight_denied",
                    "reviewed plugin distribution inventory is unavailable",
                )
        elif self.distribution is None or not _distribution_inventory_matches(
            self.distribution
        ):
            self._fail(
                request.operation,
                message_sha256(request_bytes),
                "preflight_denied",
                "reviewed plugin distribution inventory is unavailable or changed",
            )
        if (
            not _BWRAP_PATH.is_file()
            or not os.access(_BWRAP_PATH, os.X_OK)
            or not _PRLIMIT_PATH.is_file()
            or not os.access(_PRLIMIT_PATH, os.X_OK)
        ):
            self._fail(
                request.operation,
                message_sha256(request_bytes),
                "setup_failure",
                "sandbox enforcement tools are unavailable",
            )
        try:
            version = subprocess.run(
                [str(_BWRAP_PATH), "--version"],
                check=True,
                capture_output=True,
                text=True,
                timeout=2.0,
            ).stdout.strip()
            numbers = tuple(int(part) for part in version.rsplit(" ", 1)[-1].split("."))
        except (OSError, ValueError, subprocess.SubprocessError):
            self._fail(
                request.operation,
                message_sha256(request_bytes),
                "setup_failure",
                "bubblewrap sandbox version cannot be verified",
            )
        if numbers < _MINIMUM_BWRAP_VERSION:
            self._fail(
                request.operation,
                message_sha256(request_bytes),
                "setup_failure",
                "bubblewrap sandbox version is below policy minimum",
            )

    def _run(
        self, request_bytes: bytes, temporary_output: Path | None
    ) -> tuple[bytes, int, bool]:
        operation = PluginSandboxRequest.model_validate_json(request_bytes).operation
        try:
            info_read, info_write = os.pipe()
        except OSError:
            self._fail(
                operation,
                message_sha256(request_bytes),
                "setup_failure",
                "sandbox setup channel could not be created",
            )
        command = self._command(temporary_output, info_fd=info_write)
        with tempfile.TemporaryFile() as stdout_file:
            try:
                process = subprocess.Popen(
                    command,
                    stdin=subprocess.PIPE,
                    stdout=stdout_file,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                    pass_fds=(info_write,),
                )
            except (OSError, subprocess.SubprocessError):
                os.close(info_read)
                os.close(info_write)
                self._fail(
                    operation,
                    message_sha256(request_bytes),
                    "setup_failure",
                    "sandbox process could not be started",
                )
            os.close(info_write)
            try:
                process.communicate(
                    input=request_bytes,
                    timeout=self.policy.wall_timeout_seconds,
                )
            except subprocess.TimeoutExpired:
                _terminate_process(process)
                os.close(info_read)
                self._fail(
                    operation,
                    message_sha256(request_bytes),
                    "timeout",
                    "plugin exceeded the declared wall-clock limit",
                )
            stdout_file.seek(0)
            response = stdout_file.read(self.policy.max_output_bytes + 1)
        try:
            sandbox_ready = bool(os.read(info_read, 1))
        finally:
            os.close(info_read)
        return response, process.returncode, sandbox_ready

    def _command(
        self,
        temporary_output: Path | None,
        *,
        info_fd: int | None = None,
    ) -> list[str]:
        package_root = Path(__file__).resolve().parent.parent
        command = [
            str(_BWRAP_PATH),
            "--unshare-all",
            "--die-with-parent",
            "--new-session",
            "--cap-drop",
            "ALL",
            "--ro-bind",
            "/usr",
            "/usr",
        ]
        if info_fd is not None:
            command.extend(("--info-fd", str(info_fd)))
        for system_root in (Path("/lib"), Path("/lib64")):
            if system_root.exists():
                command.extend(("--ro-bind", str(system_root), str(system_root)))
        command.extend(
            (
                "--proc",
                "/proc",
                "--dev",
                "/dev",
                "--tmpfs",
                "/tmp",
                "--dir",
                "/work",
                "--dir",
                "/opt",
                "--dir",
                "/opt/biomesh",
                "--dir",
                "/opt/plugin",
                "--dir",
                "/opt/python-site",
            )
        )
        command.extend(("--ro-bind", str(package_root), "/opt/biomesh"))
        python_paths = ["/opt/plugin", "/opt/biomesh"]
        if self.distribution is not None and self.distribution_root != package_root:
            if self.distribution.mount_source.is_dir():
                command.extend(("--dir", self.distribution.mount_target))
            command.extend(
                (
                    "--ro-bind",
                    str(self.distribution.mount_source),
                    self.distribution.mount_target,
                )
            )
        elif self.distribution is not None:
            mount_target = self.distribution.mount_target
            if self.distribution.mount_source.is_dir():
                command.extend(("--dir", mount_target))
            command.extend(
                (
                    "--ro-bind",
                    str(self.distribution.mount_source),
                    mount_target,
                )
            )
        for index, (root, name) in enumerate(_external_site_roots()):
            target = f"/opt/python-site/{index}"
            mount_target = f"{target}/{name}"
            command.append("--dir")
            command.append(target)
            if root.is_dir():
                command.append("--dir")
                command.append(mount_target)
            command.extend(("--ro-bind", str(root), mount_target))
            python_paths.append(target)
        if temporary_output is None:
            command.extend(("--tmpfs", "/export"))
        else:
            command.extend(("--bind", str(temporary_output), "/export"))
        command.extend(
            (
                "--remount-ro",
                "/",
                "--clearenv",
                "--setenv",
                "HOME",
                "/nonexistent",
                "--setenv",
                "PATH",
                "/usr/bin:/bin",
                "--setenv",
                "PYTHONPATH",
                ":".join(python_paths),
                "--setenv",
                "PYTHONDONTWRITEBYTECODE",
                "1",
                "--setenv",
                "PYTHONNOUSERSITE",
                "1",
                "--chdir",
                "/work",
                str(_PRLIMIT_PATH),
                f"--cpu={self.policy.cpu_time_seconds}:"
                f"{self.policy.cpu_time_seconds + 1}",
                f"--as={self.policy.memory_limit_bytes}:"
                f"{self.policy.memory_limit_bytes}",
                f"--fsize={self.policy.max_output_bytes}:"
                f"{self.policy.max_output_bytes}",
                f"--nofile={self.policy.max_open_files}:"
                f"{self.policy.max_open_files}",
                "--",
                str(_PYTHON_PATH),
                "-P",
                "-m",
                "biomesh.plugin_worker",
            )
        )
        return command

    def _validate_response(
        self,
        operation: PluginOperation,
        request_hash: str,
        response_bytes: bytes,
        return_code: int,
        sandbox_ready: bool,
    ) -> PluginSandboxResponse:
        if return_code != 0:
            outcome: PluginExecutionOutcome
            if not sandbox_ready:
                outcome = "setup_failure"
                details = "sandbox enforcement setup failed before plugin execution"
            elif return_code in {
                -signal.SIGSYS,
                1,
                76,
                128 + signal.SIGSYS,
            }:
                outcome = "policy_violation"
                details = "plugin attempted a syscall prohibited by sandbox policy"
            elif return_code in {
                -signal.SIGXCPU,
                -signal.SIGXFSZ,
                -signal.SIGKILL,
                75,
            }:
                outcome = "resource_limit"
                details = "plugin exceeded a declared operating-system resource limit"
            elif return_code == 74:
                outcome = "policy_violation"
                details = "plugin attempted filesystem access denied by sandbox policy"
            elif return_code in {72, 73, 125, 126, 127}:
                outcome = "setup_failure"
                details = "sandbox enforcement setup failed before plugin execution"
            else:
                outcome = "crash"
                details = "plugin exited without a valid successful result"
            self._fail(operation, request_hash, outcome, details)
        if len(response_bytes) > self.policy.max_output_bytes:
            self._fail(
                operation,
                request_hash,
                "resource_limit",
                "plugin response exceeds the declared message limit",
            )
        try:
            response = PluginSandboxResponse.model_validate_json(
                response_bytes,
                strict=True,
            )
        except ValidationError:
            self._fail(
                operation,
                request_hash,
                "malformed_output",
                "plugin response is not a valid versioned message",
            )
        if (
            response.sandbox_policy_version != self.policy.policy_version
            or response.plugin_id != self.plugin_id
            or response.plugin_version != self.plugin_version
            or response.selection_sha256 != self.selection_sha256
            or response.operation != operation
            or response.request_sha256 != request_hash
        ):
            self._fail(
                operation,
                request_hash,
                "malformed_output",
                "plugin response identity does not match the exact request",
            )
        return response

    def _receipt(
        self,
        operation: PluginOperation,
        request_hash: str,
        outcome: PluginExecutionOutcome,
        result_hash: str | None,
        details: str,
    ) -> PluginExecutionReceipt:
        policy = self.policy
        return PluginExecutionReceipt(
            schema_version=1,
            plugin_api_version=1,
            sandbox_policy_version=policy.policy_version,
            plugin_id=self.plugin_id,
            plugin_version=self.plugin_version,
            selection_sha256=self.selection_sha256,
            plugin_set_sha256=self.plugin_set_sha256,
            operation=operation,
            request_sha256=cast(Any, request_hash),
            result_sha256=cast(Any, result_hash),
            outcome=outcome,
            resource_limits=PluginResourceLimits(
                wall_timeout_seconds=policy.wall_timeout_seconds,
                cpu_time_seconds=policy.cpu_time_seconds,
                memory_limit_bytes=policy.memory_limit_bytes,
                max_message_bytes=policy.max_message_bytes,
                max_output_bytes=policy.max_output_bytes,
                max_open_files=policy.max_open_files,
                max_processes=policy.max_processes,
            ),
            environment_isolation="cleared",
            filesystem_isolation="declared-runtime-read-only",
            network_isolation="network-namespace-and-seccomp",
            process_isolation="pid-namespace-and-seccomp",
            calibration_status="CALIBRATION_REQUIRED",
            details=details,
        )

    def _fail(
        self,
        operation: PluginOperation,
        request_hash: str,
        outcome: PluginExecutionOutcome,
        details: str,
    ) -> None:
        receipt = self._receipt(operation, request_hash, outcome, None, details)
        raise PluginSandboxError(details, receipt)


def _validate_payload(operation: PluginOperation, payload: dict[str, Any]) -> object:
    try:
        if operation == "initialize":
            if set(payload) != {"components", "metadata"}:
                raise ValueError("initialize result fields differ from schema")
            metadata = PluginMetadata.model_validate(payload["metadata"], strict=True)
            components = payload["components"]
            if (
                not isinstance(components, list)
                or any(not isinstance(item, str) for item in components)
                or components != sorted(set(components))
            ):
                raise ValueError("runtime components are not canonical")
            return (metadata, tuple(components))
        models: dict[PluginOperation, type[BaseModel]] = {
            "self_check": PluginSelfCheck,
            "species_definition": SpeciesDefinition,
            "evaluate_kinetics": KineticsResult,
        }
        if operation in models:
            return models[operation].model_validate(payload, strict=True)
        if operation == "advance_field":
            return FieldStepResult(**_tuplify(payload, ("shape", "values")))
        if operation == "evaluate_metric":
            return MetricResult(**payload)
        if operation == "export":
            return ExportResult(**_tuplify(payload, ("artifacts",)))
    except (KeyError, TypeError, ValueError, ValidationError) as error:
        raise PluginError("plugin result failed host schema validation") from error
    raise PluginError("unsupported plugin operation")


def _tuplify(payload: dict[str, Any], fields: Sequence[str]) -> dict[str, Any]:
    converted = dict(payload)
    for field in fields:
        value = converted[field]
        converted[field] = tuple(
            tuple(item) if isinstance(item, list) else item for item in value
        )
    return converted


def _validate_exported_files(directory: Path, result: ExportResult) -> None:
    if not directory.is_dir() or directory.is_symlink():
        raise PluginError("exporter did not create one regular output directory")
    entries = sorted(directory.rglob("*"))
    if any(path.is_symlink() for path in entries):
        raise PluginError("exported inventory must not contain symbolic links")
    actual = sorted(path for path in entries if path.is_file())
    actual_directories = {path for path in entries if path.is_dir()}
    if len(actual) + len(actual_directories) != len(entries):
        raise PluginError("exported inventory must contain only regular entries")
    expected_paths = [directory / path for path, _sha256, _size in result.artifacts]
    if actual != expected_paths:
        raise PluginError("exported files differ from the declared result inventory")
    expected_directories: set[Path] = set()
    for path in expected_paths:
        parent = path.parent
        while parent != directory:
            expected_directories.add(parent)
            parent = parent.parent
    if actual_directories != expected_directories:
        raise PluginError("exported directories differ from the declared inventory")
    for relative, expected_hash, expected_size in result.artifacts:
        data = (directory / relative).read_bytes()
        if len(data) != expected_size or message_sha256(data) != expected_hash:
            raise PluginError("exported file identity differs from declared result")


def _external_site_roots() -> tuple[tuple[Path, str], ...]:
    """Return only package roots from BioMesh's declared dependencies."""
    mounts: dict[tuple[str, str], Path] = {}
    for distribution_name in _DECLARED_RUNTIME_DISTRIBUTIONS:
        try:
            installed = distribution(distribution_name)
        except PackageNotFoundError:
            continue
        names: set[str] = set()
        top_level = installed.read_text("top_level.txt")
        if top_level is not None:
            names.update(
                item.strip()
                for item in top_level.splitlines()
                if item.strip()
            )
        if installed.files is not None:
            for item in installed.files:
                parts = PurePosixPath(str(item)).parts
                if not parts or any(part in {"", ".", ".."} for part in parts):
                    continue
                first = parts[0]
                if first == "__pycache__" or first.endswith(".data"):
                    continue
                if first.endswith(".dist-info"):
                    if distribution_name == "biomesh":
                        names.add(first)
                    continue
                names.add(first.removesuffix(".py"))
        for name in sorted(names):
            if not name.isidentifier() and not (
                distribution_name == "biomesh" and name.endswith(".dist-info")
            ):
                continue
            source = Path(str(installed.locate_file(name))).resolve()
            if (
                not source.exists()
                or source.is_symlink()
                or source.is_relative_to("/usr")
            ):
                continue
            try:
                _reject_symlink_chain(source)
            except PluginError:
                continue
            mounts[(str(source), name)] = source
    return tuple(
        (root, name)
        for (_source, name), root in sorted(mounts.items())
    )


def _terminate_process(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def request_payload(value: object) -> dict[str, Any]:
    """Convert a validated immutable component request into JSON data."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, (FieldStepRequest, MetricRequest)):
        return asdict(value)
    if isinstance(value, ExportRequest):
        return {
            "interface_version": value.interface_version,
            "artifacts": value.artifacts,
        }
    raise PluginError("unsupported plugin request type")


def preflight_denied_error(
    *,
    plugin_set_sha256: str,
    plugin_id: str,
    plugin_version: str,
    selection_sha256: str,
    entry_point_value: str,
    policy: PluginSandboxPolicy,
    details: str,
) -> PluginSandboxError:
    """Create explicit provenance for a denial before plugin code starts."""
    request = PluginSandboxRequest(
        schema_version=1,
        plugin_api_version=1,
        sandbox_policy_version=policy.policy_version,
        plugin_id=plugin_id,
        plugin_version=plugin_version,
        selection_sha256=cast(Any, selection_sha256),
        entry_point_value=entry_point_value,
        operation="initialize",
        payload={},
    )
    runtime = SandboxPluginRuntime(
        plugin_set_sha256=plugin_set_sha256,
        plugin_id=plugin_id,
        plugin_version=plugin_version,
        selection_sha256=selection_sha256,
        entry_point_value=entry_point_value,
        distribution_root=Path("/"),
        policy=policy,
    )
    receipt = runtime._receipt(
        "initialize",
        message_sha256(canonical_message_bytes(request)),
        "preflight_denied",
        None,
        details,
    )
    return PluginSandboxError(details, receipt)


__all__ = [
    "PluginExecutionReceipt",
    "PluginOperationResult",
    "PluginSandboxError",
    "PluginSandboxPolicy",
    "SandboxPluginRuntime",
    "default_plugin_sandbox_policy",
    "preflight_denied_error",
    "request_payload",
]
