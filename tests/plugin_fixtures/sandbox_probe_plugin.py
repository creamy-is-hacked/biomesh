"""Adversarial software-only fixtures for the P5-WP04 sandbox tests."""

from __future__ import annotations

import hashlib
import os
import socket
from pathlib import Path

from biomesh.plugin_components import (
    ExportRequest,
    ExportResult,
    FieldStepRequest,
    FieldStepResult,
    PluginMetadata,
    PluginSelfCheck,
    SpeciesDefinition,
)


class SandboxProbePlugin:
    def __init__(self, plugin_id: str, action: str) -> None:
        self._plugin_id = plugin_id
        self._action = action

    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            schema_version=1,
            plugin_api_version=1,
            plugin_id=self._plugin_id,
            plugin_version="1.0.0",
            display_name="P5-WP04 adversarial sandbox probe",
            components=["species"],
            source="manufactured security-verification fixture",
            calibration_status="CALIBRATION_REQUIRED",
            limitations=["Software security probe only; not biological evidence"],
        )

    def species_definition(self) -> SpeciesDefinition:
        return SpeciesDefinition(
            interface_version=1,
            species_id="sandbox-probe",
            display_name="Sandbox probe",
            calibration_status="CALIBRATION_REQUIRED",
            notes="Software security probe only; not biological evidence.",
        )

    def self_check(self) -> PluginSelfCheck:
        details = "sandbox probe completed without a forbidden action"
        if self._action == "network":
            socket.socket()
        elif self._action == "environment":
            value = os.environ.get("BIOMESH_TEST_SECRET", "ABSENT")
            details = f"environment isolation returned {value}"
        elif self._action == "process":
            os.fork()
        elif self._action == "crash":
            raise RuntimeError("intentional sandbox probe crash")
        elif self._action == "hang":
            while True:
                pass
        elif self._action == "memory":
            bytearray(1_073_741_824)
        return PluginSelfCheck(
            schema_version=1,
            plugin_id=self._plugin_id,
            plugin_version="1.0.0",
            passed=True,
            details=details,
        )


class SandboxFileProbePlugin(SandboxProbePlugin):
    def metadata(self) -> PluginMetadata:
        return super().metadata().model_copy(
            update={"components": ["field", "species"]}
        )

    def advance_field(self, request: FieldStepRequest) -> FieldStepResult:
        target = Path(request.field_id)
        if self._action == "file-read":
            target.read_bytes()
        elif self._action == "file-write":
            target.write_bytes(b"changed")
        return FieldStepResult(
            interface_version=1,
            field_id=request.field_id,
            unit=request.unit,
            shape=request.shape,
            values=request.values,
        )


def create_ok() -> SandboxProbePlugin:
    return SandboxProbePlugin("org.biomesh.test.ok", "ok")


def create_file_read() -> SandboxProbePlugin:
    return SandboxFileProbePlugin("org.biomesh.test.file-read", "file-read")


def create_file_write() -> SandboxProbePlugin:
    return SandboxFileProbePlugin("org.biomesh.test.file-write", "file-write")


def create_network() -> SandboxProbePlugin:
    return SandboxProbePlugin("org.biomesh.test.network", "network")


def create_environment() -> SandboxProbePlugin:
    return SandboxProbePlugin("org.biomesh.test.environment", "environment")


def create_process() -> SandboxProbePlugin:
    return SandboxProbePlugin("org.biomesh.test.process", "process")


def create_crash() -> SandboxProbePlugin:
    return SandboxProbePlugin("org.biomesh.test.crash", "crash")


def create_hang() -> SandboxProbePlugin:
    return SandboxProbePlugin("org.biomesh.test.hang", "hang")


def create_memory() -> SandboxProbePlugin:
    return SandboxProbePlugin("org.biomesh.test.memory", "memory")


class SandboxExporterPlugin:
    def __init__(self, plugin_id: str, *, wrong_hash: bool) -> None:
        self._plugin_id = plugin_id
        self._wrong_hash = wrong_hash

    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            schema_version=1,
            plugin_api_version=1,
            plugin_id=self._plugin_id,
            plugin_version="1.0.0",
            display_name="P5-WP04 atomic exporter probe",
            components=["exporter"],
            source="manufactured security-verification fixture",
            calibration_status="CALIBRATION_REQUIRED",
            limitations=["Software security probe only; not biological evidence"],
        )

    def self_check(self) -> PluginSelfCheck:
        return PluginSelfCheck(
            schema_version=1,
            plugin_id=self._plugin_id,
            plugin_version="1.0.0",
            passed=True,
            details="atomic exporter sandbox probe",
        )

    def export(self, request: ExportRequest) -> ExportResult:
        request.output_directory.mkdir()
        payload = b"sandboxed-export\n"
        output = request.output_directory / "result.txt"
        if self._plugin_id.endswith("symlink"):
            output.symlink_to("/etc/passwd")
        else:
            output.write_bytes(payload)
        digest = hashlib.sha256(payload).hexdigest()
        if self._wrong_hash:
            digest = "0" * 64
        return ExportResult(
            interface_version=1,
            artifacts=(("result.txt", digest, len(payload)),),
        )


def create_exporter() -> SandboxExporterPlugin:
    return SandboxExporterPlugin("org.biomesh.test.exporter", wrong_hash=False)


def create_exporter_mismatch() -> SandboxExporterPlugin:
    return SandboxExporterPlugin(
        "org.biomesh.test.exporter-mismatch",
        wrong_hash=True,
    )


def create_exporter_symlink() -> SandboxExporterPlugin:
    return SandboxExporterPlugin(
        "org.biomesh.test.exporter-symlink",
        wrong_hash=False,
    )
