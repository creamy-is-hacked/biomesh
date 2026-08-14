"""P5-WP04 misuse, containment, resource, and atomicity evidence."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from dataclasses import replace as dataclass_replace
from pathlib import Path

import pytest

from biomesh.config import BiologicalParameter
from biomesh.plugin_api import (
    ExportRequest,
    FieldStepRequest,
    KineticsRequest,
    PluginSelection,
    PluginSetManifest,
    PluginTrustPolicy,
    example_plugin_manifest,
    load_plugins,
    plugin_metadata_sha256,
    plugin_selection_sha256,
    plugin_set_sha256,
)
from biomesh.plugin_components import PluginMetadata
from biomesh.plugin_sandbox import (
    PluginSandboxError,
    PluginSandboxPolicy,
    SandboxPluginRuntime,
)

_FIXTURE_ROOT = Path(__file__).parent / "plugin_fixtures"


@dataclass(frozen=True, slots=True)
class _FixtureEntryPoint:
    name: str
    value: str
    distribution_name: str
    distribution_version: str
    distribution_root: Path


def _selection(action: str) -> tuple[PluginSetManifest, PluginTrustPolicy, object]:
    plugin_id = f"org.biomesh.test.{action.replace('_', '-')}"
    if action.startswith("exporter"):
        components = ["exporter"]
    elif action in {"file_read", "file_write"}:
        components = ["field", "species"]
    else:
        components = ["species"]
    display_name = (
        "P5-WP04 atomic exporter probe"
        if action.startswith("exporter")
        else "P5-WP04 adversarial sandbox probe"
    )
    metadata = PluginMetadata(
        schema_version=1,
        plugin_api_version=1,
        plugin_id=plugin_id,
        plugin_version="1.0.0",
        display_name=display_name,
        components=components,
        source="manufactured security-verification fixture",
        calibration_status="CALIBRATION_REQUIRED",
        limitations=["Software security probe only; not biological evidence"],
    )
    selection = PluginSelection(
        schema_version=1,
        metadata=metadata,
        metadata_sha256=plugin_metadata_sha256(metadata),
        distribution_name="biomesh-sandbox-test-fixture",
        distribution_version="1.0.0",
        entry_point_name=f"sandbox-{action.replace('_', '-')}",
        entry_point_value=f"sandbox_probe_plugin:create_{action.replace('-', '_')}",
        review_reference="P5-WP04 manufactured adversarial fixture",
    )
    manifest = PluginSetManifest(schema_version=1, plugins=[selection])
    policy = PluginTrustPolicy(
        approved_selection_sha256=frozenset({plugin_selection_sha256(selection)})
    )
    entry_point = _FixtureEntryPoint(
        name=selection.entry_point_name,
        value=selection.entry_point_value,
        distribution_name=selection.distribution_name,
        distribution_version=selection.distribution_version,
        distribution_root=_FIXTURE_ROOT,
    )
    return manifest, policy, entry_point


def _loaded_probe(
    action: str,
    *,
    sandbox_policy: PluginSandboxPolicy | None = None,
) -> object:
    manifest, trust, entry_point = _selection(action)
    return load_plugins(
        manifest,
        trust,
        available_entry_points=[entry_point],
        sandbox_policy=sandbox_policy,
    )[0].instance


def test_reviewed_plugin_executes_out_of_process_with_bounded_provenance() -> None:
    plugin = _loaded_probe("ok")
    result = plugin.self_check()  # type: ignore[attr-defined]
    receipts = plugin.sandbox_executions  # type: ignore[attr-defined]

    assert result.passed is True
    assert [item.operation for item in receipts] == ["initialize", "self_check"]
    assert all(item.outcome == "success" for item in receipts)
    assert all(item.sandbox_policy_version == "1.0.0" for item in receipts)
    assert all(item.calibration_status == "CALIBRATION_REQUIRED" for item in receipts)
    assert all(item.result_sha256 is not None for item in receipts)


def test_si_and_provenance_validated_kinetics_round_trips_through_sandbox() -> None:
    manifest = example_plugin_manifest()
    trust = PluginTrustPolicy(
        approved_selection_sha256=frozenset(
            {plugin_selection_sha256(manifest.plugins[0])}
        )
    )
    plugin = load_plugins(manifest, trust)[0].instance
    request = KineticsRequest(
        interface_version=1,
        carbon_concentration_mol_m3=2.0,
        oxygen_concentration_mol_m3=3.0,
        biological_parameters=[
            BiologicalParameter(
                name=name,
                value=value,
                unit=unit,
                source="manufactured P5-WP04 software-verification fixture",
                uncertainty="not a biological uncertainty estimate",
                notes="Sandbox message validation only; not calibration evidence.",
                calibration_status="CALIBRATION_REQUIRED",
            )
            for name, value, unit in (
                ("maximum_specific_growth_rate", 0.5, "s^-1"),
                ("carbon_half_saturation_constant", 1.0, "mol m^-3"),
                ("oxygen_half_saturation_constant", 1.0, "mol m^-3"),
            )
        ],
    )

    result = plugin.evaluate_kinetics(request)  # type: ignore[attr-defined]

    assert result.specific_growth_rate_s == pytest.approx(0.25)
    assert result.unit == "s^-1"
    assert plugin.sandbox_executions[-1].operation == (  # type: ignore[attr-defined]
        "evaluate_kinetics"
    )


def test_unreviewed_selection_has_explicit_preflight_denial_and_no_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, _trust, entry_point = _selection("ok")
    starts = 0

    def unexpected_start(*_args: object, **_kwargs: object) -> object:
        nonlocal starts
        starts += 1
        raise AssertionError("unreviewed plugin must not start")

    monkeypatch.setattr("biomesh.plugin_sandbox.subprocess.Popen", unexpected_start)
    with pytest.raises(PluginSandboxError) as caught:
        load_plugins(
            manifest,
            PluginTrustPolicy(approved_selection_sha256=frozenset()),
            available_entry_points=[entry_point],
        )

    assert caught.value.receipt.outcome == "preflight_denied"
    assert caught.value.receipt.result_sha256 is None
    assert starts == 0


def test_exporter_publishes_only_fully_hash_validated_output(tmp_path: Path) -> None:
    output = tmp_path / "export"
    request = ExportRequest(
        interface_version=1,
        artifacts=(("input.bin", "0" * 64, 0),),
        output_directory=output,
    )
    plugin = _loaded_probe("exporter")

    result = plugin.export(request)  # type: ignore[attr-defined]

    assert result.artifacts[0][0] == "result.txt"
    assert (output / "result.txt").read_bytes() == b"sandboxed-export\n"
    assert plugin.sandbox_executions[-1].outcome == "success"  # type: ignore[attr-defined]


@pytest.mark.parametrize("action", ["exporter_mismatch", "exporter_symlink"])
def test_unsafe_exporter_output_publishes_no_partial_directory(
    action: str,
    tmp_path: Path,
) -> None:
    output = tmp_path / "export"
    request = ExportRequest(
        interface_version=1,
        artifacts=(("input.bin", "0" * 64, 0),),
        output_directory=output,
    )
    plugin = _loaded_probe(action)

    with pytest.raises(PluginSandboxError) as caught:
        plugin.export(request)  # type: ignore[attr-defined]

    assert caught.value.receipt.outcome == "malformed_output"
    assert not output.exists()


@pytest.mark.parametrize("action", ["file_read", "file_write"])
def test_arbitrary_host_file_access_is_denied_and_artifacts_are_unchanged(
    action: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completed = tmp_path / "completed.bin"
    completed.write_bytes(b"immutable-completed-artifact")
    before = hashlib.sha256(completed.read_bytes()).hexdigest()
    monkeypatch.setenv("BIOMESH_TEST_SECRET", "must-not-cross-sandbox")
    plugin = _loaded_probe(action)
    request = FieldStepRequest(
        interface_version=1,
        field_id=str(completed),
        unit="mol m^-3",
        shape=(1, 1),
        values=(1.0,),
        time_step_s=1.0,
    )

    with pytest.raises(PluginSandboxError) as caught:
        plugin.advance_field(request)  # type: ignore[attr-defined]

    assert caught.value.receipt.outcome == "policy_violation"
    assert hashlib.sha256(completed.read_bytes()).hexdigest() == before
    assert "must-not-cross-sandbox" not in caught.value.receipt.model_dump_json()


def test_unreviewed_distribution_siblings_are_not_mounted(
    tmp_path: Path,
) -> None:
    manifest, trust, entry_point = _selection("file_read")
    isolated_root = tmp_path / "distribution"
    shutil.copytree(_FIXTURE_ROOT, isolated_root)
    (isolated_root / "host-secret.txt").write_text("must-not-cross-sandbox")
    isolated_entry_point = dataclass_replace(
        entry_point,
        distribution_root=isolated_root,
    )
    plugin = load_plugins(
        manifest,
        trust,
        available_entry_points=[isolated_entry_point],
    )[0].instance
    request = FieldStepRequest(
        interface_version=1,
        field_id="/opt/plugin/host-secret.txt",
        unit="mol m^-3",
        shape=(1, 1),
        values=(1.0,),
        time_step_s=1.0,
    )
    with pytest.raises(PluginSandboxError) as caught:
        plugin.advance_field(request)  # type: ignore[attr-defined]
    assert caught.value.receipt.outcome == "policy_violation"
    assert "must-not-cross-sandbox" not in caught.value.receipt.model_dump_json()


@pytest.mark.parametrize("action", ["network", "process"])
def test_network_and_child_process_syscalls_are_trapped(action: str) -> None:
    plugin = _loaded_probe(action)
    with pytest.raises(PluginSandboxError) as caught:
        plugin.self_check()  # type: ignore[attr-defined]
    assert caught.value.receipt.outcome == "policy_violation"


def test_environment_is_cleared_without_leaking_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "P5-WP04-SECRET-MUST-NOT-LEAK"
    monkeypatch.setenv("BIOMESH_TEST_SECRET", secret)
    plugin = _loaded_probe("environment")

    result = plugin.self_check()  # type: ignore[attr-defined]
    receipt = plugin.sandbox_executions[-1]  # type: ignore[attr-defined]

    assert result.details.endswith("ABSENT")
    assert receipt.environment_isolation == "cleared"
    assert secret not in result.model_dump_json()
    assert secret not in receipt.model_dump_json()


def test_crash_timeout_and_memory_exhaustion_are_explicit_and_atomic(
    tmp_path: Path,
) -> None:
    completed = tmp_path / "completed.bin"
    completed.write_bytes(b"completed")
    before = completed.read_bytes()
    cases = (
        ("crash", PluginSandboxPolicy(), "crash"),
        (
            "hang",
            PluginSandboxPolicy(wall_timeout_seconds=1.0),
            "timeout",
        ),
        (
            "memory",
            PluginSandboxPolicy(memory_limit_bytes=134_217_728),
            "resource_limit",
        ),
        (
            "hang",
            PluginSandboxPolicy(
                wall_timeout_seconds=5.0,
                cpu_time_seconds=1,
            ),
            "resource_limit",
        ),
    )
    for action, policy, expected in cases:
        plugin = _loaded_probe(action, sandbox_policy=policy)
        with pytest.raises(PluginSandboxError) as caught:
            plugin.self_check()  # type: ignore[attr-defined]
        assert caught.value.receipt.outcome == expected
        assert completed.read_bytes() == before


def test_policy_mismatch_fails_before_sandbox_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy = PluginSandboxPolicy().model_copy(update={"policy_version": "9.9.9"})
    starts = 0

    def unexpected_start(*_args: object, **_kwargs: object) -> object:
        nonlocal starts
        starts += 1
        raise AssertionError("sandbox must not start")

    monkeypatch.setattr("biomesh.plugin_sandbox.subprocess.Popen", unexpected_start)
    manifest, trust, entry_point = _selection("ok")
    with pytest.raises(PluginSandboxError) as caught:
        load_plugins(
            manifest,
            trust,
            available_entry_points=[entry_point],
            sandbox_policy=policy,
        )
    assert caught.value.receipt.outcome == "setup_failure"
    assert starts == 0


def test_malformed_wrong_identity_and_oversized_outputs_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = example_plugin_manifest()
    selection = manifest.plugins[0]
    runtime = SandboxPluginRuntime(
        plugin_set_sha256=plugin_set_sha256(manifest),
        plugin_id=selection.metadata.plugin_id,
        plugin_version=selection.metadata.plugin_version,
        selection_sha256=plugin_selection_sha256(selection),
        entry_point_value=selection.entry_point_value,
        distribution_root=Path(__file__).parents[1] / "src",
        policy=PluginSandboxPolicy(),
    )
    monkeypatch.setattr(SandboxPluginRuntime, "_preflight", lambda *_args: None)

    monkeypatch.setattr(
        SandboxPluginRuntime,
        "_run",
        lambda *_args: (b"not-json\n", 0, True),
    )
    with pytest.raises(PluginSandboxError) as malformed:
        runtime.execute("initialize")
    assert malformed.value.receipt.outcome == "malformed_output"

    oversized = b"x" * (runtime.policy.max_output_bytes + 1)
    monkeypatch.setattr(
        SandboxPluginRuntime,
        "_run",
        lambda *_args: (oversized, 0, True),
    )
    with pytest.raises(PluginSandboxError) as too_large:
        runtime.execute("initialize")
    assert too_large.value.receipt.outcome == "resource_limit"

    request_hash = "0" * 64
    response = {
        "schema_version": 1,
        "plugin_api_version": 1,
        "sandbox_policy_version": "1.0.0",
        "plugin_id": selection.metadata.plugin_id,
        "plugin_version": selection.metadata.plugin_version,
        "selection_sha256": plugin_selection_sha256(selection),
        "operation": "initialize",
        "request_sha256": request_hash,
        "payload": {},
    }
    wrong_identity = (json.dumps(response, sort_keys=True) + "\n").encode()
    monkeypatch.setattr(
        SandboxPluginRuntime,
        "_run",
        lambda *_args: (wrong_identity, 0, True),
    )
    with pytest.raises(PluginSandboxError) as mismatched:
        runtime.execute("initialize")
    assert mismatched.value.receipt.outcome == "malformed_output"


def test_zero_plugin_selection_starts_no_process_and_keeps_canonical_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    starts = 0

    def unexpected_start(*_args: object, **_kwargs: object) -> object:
        nonlocal starts
        starts += 1
        raise AssertionError("empty plugin selection must not start a process")

    monkeypatch.setattr("biomesh.plugin_sandbox.subprocess.Popen", unexpected_start)
    manifest = PluginSetManifest(schema_version=1, plugins=[])
    loaded = load_plugins(
        manifest,
        PluginTrustPolicy(approved_selection_sha256=frozenset()),
    )
    assert loaded == ()
    assert plugin_set_sha256(manifest) == (
        "1919457d222318dd73626ea9b92a26b0697d1b96230dff5ed254842ca9b310a0"
    )
    assert starts == 0
