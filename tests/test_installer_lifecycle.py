"""Focused P5-WP05 installer lifecycle misuse and recovery tests."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from biomesh.installer_lifecycle import (
    InstallerLifecycle,
    InstallerLifecycleError,
    LifecycleInterruption,
    OwnedFileManifest,
    build_owned_file_manifest,
)

_WHEEL_SHA256 = "a" * 64
_PROVENANCE_SHA256 = "b" * 64


def _candidate(tmp_path: Path, version: str) -> Path:
    root = tmp_path / f"candidate-{version}"
    (root / "app" / "biomesh").mkdir(parents=True)
    (root / "app" / "dependency").mkdir()
    (root / "bin").mkdir()
    (root / "app" / "biomesh" / "__init__.py").write_text(
        f"VERSION = {version!r}\n", encoding="utf-8"
    )
    (root / "app" / "dependency" / "runtime.py").write_text(
        f"RUNTIME = {version!r}\n", encoding="utf-8"
    )
    (root / "python-path").write_text("/usr/bin/python3.14\n", encoding="utf-8")
    for name in ("biomesh", "biomesh-gui"):
        launcher = root / "bin" / name
        launcher.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        launcher.chmod(0o755)
    return root


def _manifest(candidate: Path, version: str) -> bytes:
    return build_owned_file_manifest(
        candidate,
        version=version,
        wheel_sha256=_WHEEL_SHA256,
        provenance_sha256=_PROVENANCE_SHA256,
    ).to_bytes()


def _install(
    lifecycle: InstallerLifecycle,
    tmp_path: Path,
    version: str,
    *,
    upgrade: bool = False,
) -> Path:
    candidate = _candidate(tmp_path, version)
    lifecycle.install(candidate, _manifest(candidate, version), upgrade=upgrade)
    return candidate


def _interrupt_at(boundary: str) -> Callable[[str], None]:
    def interrupt(observed: str) -> None:
        if observed == boundary:
            raise LifecycleInterruption(boundary)

    return interrupt


def _inventory(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }


def test_mt_in_01_altered_candidate_or_manifest_fails_before_prefix_mutation(
    tmp_path: Path,
) -> None:
    prefix = tmp_path / "prefix"
    candidate = _candidate(tmp_path, "1.0.0")
    manifest = _manifest(candidate, "1.0.0")
    (candidate / "app" / "biomesh" / "__init__.py").write_text(
        "altered\n", encoding="utf-8"
    )
    lifecycle = InstallerLifecycle(prefix, smoke_runner=lambda _path: None)
    with pytest.raises(InstallerLifecycleError, match="modified"):
        lifecycle.install(candidate, manifest)
    assert not prefix.exists()

    clean = _candidate(tmp_path, "1.0.1")
    altered_value = json.loads(_manifest(clean, "1.0.1"))
    altered_value["files"][0]["sha256"] = "c" * 64
    altered = (
        json.dumps(altered_value, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode()
    with pytest.raises(InstallerLifecycleError, match="modified"):
        lifecycle.install(clean, altered)
    assert not prefix.exists()


def test_mt_in_02_unsafe_duplicate_symlinked_and_target_escape_inputs_fail(
    tmp_path: Path,
) -> None:
    candidate = _candidate(tmp_path, "1.0.0")
    manifest = json.loads(_manifest(candidate, "1.0.0"))
    manifest["files"][0]["path"] = "../escape"
    unsafe = (
        json.dumps(manifest, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode()
    with pytest.raises(InstallerLifecycleError, match="unsafe"):
        OwnedFileManifest.from_bytes(unsafe)

    manifest = json.loads(_manifest(candidate, "1.0.0"))
    manifest["files"].append(manifest["files"][0])
    duplicate = (
        json.dumps(manifest, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode()
    with pytest.raises(InstallerLifecycleError, match="duplicate"):
        OwnedFileManifest.from_bytes(duplicate)

    (candidate / "linked").symlink_to(candidate / "app", target_is_directory=True)
    with pytest.raises(InstallerLifecycleError, match="symlinked directory"):
        build_owned_file_manifest(
            candidate,
            version="1.0.0",
            wheel_sha256=_WHEEL_SHA256,
            provenance_sha256=_PROVENANCE_SHA256,
        )

    real = tmp_path / "real-prefix"
    linked = tmp_path / "linked-prefix"
    real.mkdir()
    linked.symlink_to(real, target_is_directory=True)
    lifecycle = InstallerLifecycle(linked, smoke_runner=lambda _path: None)
    clean = _candidate(tmp_path, "1.0.1")
    with pytest.raises(InstallerLifecycleError, match="uses symlink"):
        lifecycle.install(clean, _manifest(clean, "1.0.1"))
    assert not (real / "lib").exists()


@pytest.mark.parametrize("boundary", ["staged", "published", "verified", "activated"])
def test_mt_in_03_interrupted_fresh_install_recovers_without_partial_current(
    tmp_path: Path, boundary: str
) -> None:
    prefix = tmp_path / "prefix"
    candidate = _candidate(tmp_path, "1.0.0")
    lifecycle = InstallerLifecycle(
        prefix,
        smoke_runner=lambda _path: None,
        fault_hook=_interrupt_at(boundary),
    )
    with pytest.raises(LifecycleInterruption, match=boundary):
        lifecycle.install(candidate, _manifest(candidate, "1.0.0"))

    recovered = InstallerLifecycle(prefix, smoke_runner=lambda _path: None)
    outcome = recovered.recover()
    if boundary == "staged":
        assert recovered.current_version() is None
        assert outcome == "staging_removed_prior_current_retained"
    else:
        assert recovered.current_version() == "1.0.0"
        assert outcome == "verified_candidate_activated"


@pytest.mark.parametrize("boundary", ["staged", "published", "verified", "activated"])
def test_mt_in_04_interrupted_upgrade_keeps_one_complete_current_pair(
    tmp_path: Path, boundary: str
) -> None:
    prefix = tmp_path / "prefix"
    initial = InstallerLifecycle(prefix, smoke_runner=lambda _path: None)
    _install(initial, tmp_path, "1.0.0")
    candidate = _candidate(tmp_path, "1.1.0")
    interrupted = InstallerLifecycle(
        prefix,
        smoke_runner=lambda _path: None,
        fault_hook=_interrupt_at(boundary),
    )
    with pytest.raises(LifecycleInterruption, match=boundary):
        interrupted.install(candidate, _manifest(candidate, "1.1.0"), upgrade=True)

    recovered = InstallerLifecycle(prefix, smoke_runner=lambda _path: None)
    recovered.recover()
    assert recovered.current_version() in {"1.0.0", "1.1.0"}
    result = recovered.verify_current(require=True)
    assert result is not None and result.verified


def test_mt_in_05_failed_upgrade_smoke_retains_exact_prior_version(
    tmp_path: Path,
) -> None:
    prefix = tmp_path / "prefix"
    lifecycle = InstallerLifecycle(prefix, smoke_runner=lambda _path: None)
    _install(lifecycle, tmp_path, "1.0.0")
    before = lifecycle.verify_current(require=True)
    candidate = _candidate(tmp_path, "1.1.0")

    def fail_smoke(_path: Path) -> None:
        raise InstallerLifecycleError("simulated CLI smoke failure")

    failing = InstallerLifecycle(prefix, smoke_runner=fail_smoke)
    with pytest.raises(InstallerLifecycleError, match="smoke failure"):
        failing.install(candidate, _manifest(candidate, "1.1.0"), upgrade=True)
    after = lifecycle.verify_current(require=True)
    assert after == before
    assert lifecycle.current_version() == "1.0.0"
    assert lifecycle._find_version("1.1.0") is None


@pytest.mark.parametrize("change", ["modified", "missing", "extra"])
def test_mt_in_06_owned_path_change_blocks_upgrade_without_exact_choice(
    tmp_path: Path, change: str
) -> None:
    prefix = tmp_path / "prefix"
    lifecycle = InstallerLifecycle(prefix, smoke_runner=lambda _path: None)
    _install(lifecycle, tmp_path, "1.0.0")
    target = lifecycle._find_version("1.0.0")
    assert target is not None
    owned = target / "app" / "biomesh" / "__init__.py"
    if change == "modified":
        owned.write_text("local change\n", encoding="utf-8")
    elif change == "missing":
        owned.unlink()
    else:
        (target / "local-extra.txt").write_text("keep me\n", encoding="utf-8")
    candidate = _candidate(tmp_path, "1.1.0")
    with pytest.raises(InstallerLifecycleError, match="blocked by owned-path changes"):
        lifecycle.install(candidate, _manifest(candidate, "1.1.0"), upgrade=True)
    assert lifecycle.current_version() == "1.0.0"


def test_mt_in_07_missing_or_altered_rollback_target_is_rejected(
    tmp_path: Path,
) -> None:
    prefix = tmp_path / "prefix"
    lifecycle = InstallerLifecycle(prefix, smoke_runner=lambda _path: None)
    _install(lifecycle, tmp_path, "1.0.0")
    _install(lifecycle, tmp_path, "1.1.0", upgrade=True)
    with pytest.raises(InstallerLifecycleError, match="absent"):
        lifecycle.rollback("0.9.0")
    old = lifecycle._find_version("1.0.0")
    assert old is not None
    (old / "app" / "biomesh" / "__init__.py").write_text("altered\n", encoding="utf-8")
    with pytest.raises(InstallerLifecycleError, match="modified"):
        lifecycle.rollback("1.0.0")
    assert lifecycle.current_version() == "1.1.0"


@pytest.mark.parametrize("boundary", ["rollback-prepared", "rollback-activated"])
def test_mt_in_08_interrupted_rollback_recovers_one_verified_target(
    tmp_path: Path, boundary: str
) -> None:
    prefix = tmp_path / "prefix"
    lifecycle = InstallerLifecycle(prefix, smoke_runner=lambda _path: None)
    _install(lifecycle, tmp_path, "1.0.0")
    _install(lifecycle, tmp_path, "1.1.0", upgrade=True)
    interrupted = InstallerLifecycle(
        prefix,
        smoke_runner=lambda _path: None,
        fault_hook=_interrupt_at(boundary),
    )
    with pytest.raises(LifecycleInterruption, match=boundary):
        interrupted.rollback("1.0.0")
    recovered = InstallerLifecycle(prefix, smoke_runner=lambda _path: None)
    recovered.recover()
    assert recovered.current_version() in {"1.0.0", "1.1.0"}
    result = recovered.verify_current(require=True)
    assert result is not None and result.verified


def test_mt_in_09_uninstall_preserves_every_supported_user_data_root(
    tmp_path: Path,
) -> None:
    prefix = tmp_path / "prefix"
    lifecycle = InstallerLifecycle(prefix, smoke_runner=lambda _path: None)
    _install(lifecycle, tmp_path, "1.0.0")
    user_root = prefix / "user-data"
    for name in (
        "projects",
        "archives",
        "parameters",
        "queues",
        "reports",
        "configuration",
        "research-data",
    ):
        path = user_root / name / "retained.bin"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"{name}\x00payload".encode())
    before = _inventory(user_root)
    lifecycle.uninstall("1.0.0")
    assert _inventory(user_root) == before
    assert lifecycle.current_version() is None


def test_mt_in_10_unowned_file_blocks_removal_and_explicit_quarantine_keeps_it(
    tmp_path: Path,
) -> None:
    prefix = tmp_path / "prefix"
    lifecycle = InstallerLifecycle(prefix, smoke_runner=lambda _path: None)
    _install(lifecycle, tmp_path, "1.0.0")
    target = lifecycle._find_version("1.0.0")
    assert target is not None
    local = target / "local-not-owned.txt"
    local.write_bytes(b"must survive")
    with pytest.raises(InstallerLifecycleError, match="blocked by owned-path changes"):
        lifecycle.uninstall("1.0.0")
    assert local.read_bytes() == b"must survive"
    lifecycle.uninstall(
        "1.0.0",
        acknowledge_paths=("extra:local-not-owned.txt",),
        quarantine_modified=True,
    )
    quarantined = next((prefix / "lib" / "biomesh" / "recovery").iterdir())
    assert (quarantined / "local-not-owned.txt").read_bytes() == b"must survive"
    log = json.loads(
        sorted((prefix / "lib" / "biomesh" / "lifecycle-logs").glob("*.json"))[
            -1
        ].read_bytes()
    )
    assert log["wheel_sha256"] == _WHEEL_SHA256
    assert log["provenance_sha256"] == _PROVENANCE_SHA256
    assert log["affected_owned_paths"] == ["extra:local-not-owned.txt"]
    assert b"must survive" not in json.dumps(log, sort_keys=True).encode()


@pytest.mark.parametrize(
    "boundary",
    ["uninstall-deactivated", "uninstall-launchers-removed", "uninstall-retired"],
)
def test_mt_in_11_interrupted_uninstall_recovers_explicit_safe_state(
    tmp_path: Path, boundary: str
) -> None:
    prefix = tmp_path / "prefix"
    lifecycle = InstallerLifecycle(prefix, smoke_runner=lambda _path: None)
    _install(lifecycle, tmp_path, "1.0.0")
    user = prefix / "project" / "result.bin"
    user.parent.mkdir()
    user.write_bytes(b"immutable research bytes")
    interrupted = InstallerLifecycle(
        prefix,
        smoke_runner=lambda _path: None,
        fault_hook=_interrupt_at(boundary),
    )
    with pytest.raises(LifecycleInterruption, match=boundary):
        interrupted.uninstall("1.0.0")
    recovered = InstallerLifecycle(prefix, smoke_runner=lambda _path: None)
    outcome = recovered.recover()
    assert user.read_bytes() == b"immutable research bytes"
    if boundary == "uninstall-retired":
        assert recovered.current_version() is None
        assert outcome == "retired_tree_removed"
    else:
        assert recovered.current_version() == "1.0.0"
        assert outcome == "verified_installation_restored"


def test_mt_in_12_mismatched_launcher_target_blocks_lifecycle_mutation(
    tmp_path: Path,
) -> None:
    prefix = tmp_path / "prefix"
    lifecycle = InstallerLifecycle(prefix, smoke_runner=lambda _path: None)
    _install(lifecycle, tmp_path, "1.0.0")
    launcher = prefix / "bin" / "biomesh"
    launcher.unlink()
    launcher.symlink_to("../lib/biomesh/versions/wrong/bin/biomesh")
    candidate = _candidate(tmp_path, "1.1.0")
    with pytest.raises(InstallerLifecycleError, match="launcher-target"):
        lifecycle.install(candidate, _manifest(candidate, "1.1.0"), upgrade=True)
    assert lifecycle._find_version("1.1.0") is None


def test_mt_in_13_fresh_upgrade_and_rollback_smoke_before_activation(
    tmp_path: Path,
) -> None:
    observed: list[str] = []

    def smoke(path: Path) -> None:
        manifest = OwnedFileManifest.from_bytes(
            (path / ".biomesh-owned.json").read_bytes()
        )
        observed.append(manifest.version)

    lifecycle = InstallerLifecycle(tmp_path / "prefix", smoke_runner=smoke)
    _install(lifecycle, tmp_path, "1.0.0")
    _install(lifecycle, tmp_path, "1.1.0", upgrade=True)
    lifecycle.rollback("1.0.0")
    assert observed == ["1.0.0", "1.1.0", "1.0.0"]


def test_mt_in_14_lifecycle_paths_preserve_completed_artifact_bytes(
    tmp_path: Path,
) -> None:
    prefix = tmp_path / "prefix"
    retained = prefix / "retained"
    (retained / "projects").mkdir(parents=True)
    (retained / "completed").mkdir()
    (retained / "projects" / "project.json").write_bytes(b'{"schema_version":2}\n')
    (retained / "completed" / "receipt.bin").write_bytes(b"exact receipt\x00")
    before = _inventory(retained)
    lifecycle = InstallerLifecycle(prefix, smoke_runner=lambda _path: None)
    _install(lifecycle, tmp_path, "1.0.0")
    _install(lifecycle, tmp_path, "1.1.0", upgrade=True)
    lifecycle.rollback("1.0.0")
    lifecycle.rollback("1.1.0")
    lifecycle.uninstall("1.0.0")
    assert _inventory(retained) == before
