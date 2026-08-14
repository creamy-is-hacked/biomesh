"""Focused P4-WP06 Linux installer-bundle tests."""

from __future__ import annotations

import json
import subprocess
import tarfile
import zipfile
from pathlib import Path

import pytest

from biomesh import __version__
from biomesh.__main__ import main
from biomesh.build_identity import (
    SOURCE_IDENTITY_POLICY,
    ArtifactIdentity,
    BuildIdentity,
    BuildTool,
    canonical_json_bytes,
    sha256_bytes,
)
from biomesh.linux_packaging import (
    LinuxPackagingError,
    build_linux_installer,
    verify_installer_supply,
)


def _wheel(
    tmp_path: Path,
    *,
    generated_data: bool = False,
    private_key_path: bool = False,
) -> Path:
    provenance, _ = _provenance_inputs()
    path = tmp_path / f"biomesh-{__version__}-py3-none-any.whl"
    with zipfile.ZipFile(path, mode="w", compression=zipfile.ZIP_DEFLATED) as wheel:
        wheel.writestr("biomesh/__init__.py", b"VERSION = 'test'\n")
        wheel.writestr("biomesh/_build_provenance.json", provenance)
        wheel.writestr(
            f"biomesh-{__version__}.dist-info/METADATA",
            f"Name: biomesh\nVersion: {__version__}\n".encode(),
        )
        if generated_data:
            wheel.writestr("biomesh/outputs/run_metadata.json", b"{}")
        if private_key_path:
            wheel.writestr("biomesh/private.key", b"prohibited test placeholder")
    return path


def _provenance_inputs(wheel: Path | None = None) -> tuple[bytes, bytes]:
    build = BuildIdentity(
        package_name="biomesh",
        package_version=__version__,
        source_commit="a" * 40,
        source_tree_sha256="b" * 64,
        source_identity_policy=SOURCE_IDENTITY_POLICY,
        build_tools=tuple(
            sorted(
                (
                    BuildTool("biomesh-provenance-builder", __version__),
                    BuildTool("git", "test"),
                    BuildTool("hatchling", "test"),
                    BuildTool("python", "3.14.0"),
                )
            )
        ),
    )
    wheel_bytes = b"placeholder" if wheel is None else wheel.read_bytes()
    artifacts = [
        ArtifactIdentity("sdist", f"biomesh-{__version__}.tar.gz", "c" * 64, 1),
        ArtifactIdentity(
            "wheel",
            f"biomesh-{__version__}-py3-none-any.whl",
            sha256_bytes(wheel_bytes),
            len(wheel_bytes),
        ),
    ]
    binding = canonical_json_bytes(
        {
            "artifacts": [item.as_dict() for item in artifacts],
            "build": build.as_dict(),
            "schema_version": 1,
        }
    )
    return build.to_bytes(), binding


def test_linux_bundle_is_deterministic_and_contains_no_research_data(
    tmp_path: Path,
) -> None:
    wheel = _wheel(tmp_path)
    provenance, binding = _provenance_inputs(wheel)
    first = build_linux_installer(
        wheel,
        tmp_path / "first",
        build_provenance=provenance,
        artifact_binding=binding,
    )
    second = build_linux_installer(
        wheel,
        tmp_path / "second",
        build_provenance=provenance,
        artifact_binding=binding,
    )
    first_bytes = Path(first.bundle).read_bytes()
    assert first_bytes == Path(second.bundle).read_bytes()
    assert first.bundle_sha256 == second.bundle_sha256

    with tarfile.open(first.bundle, mode="r:gz") as archive:
        names = archive.getnames()
        installer_name = next(name for name in names if name.endswith("/install.sh"))
        installer = archive.extractfile(installer_name)
        assert installer is not None
        installer_bytes = installer.read()
    installer_path = tmp_path / "install.sh"
    installer_path.write_bytes(installer_bytes)
    syntax = subprocess.run(
        ["bash", "-n", str(installer_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert syntax.returncode == 0, syntax.stderr
    assert any(name.endswith("/SHA256SUMS") for name in names)
    assert any(name.endswith("/PROVENANCE.json") for name in names)
    assert any(name.endswith(".whl") for name in names)
    assert b"project import" in installer_bytes or b"pip install" in installer_bytes
    assert not any("run_metadata.json" in name for name in names)
    assert not any("campaign_state.json" in name for name in names)


def test_linux_bundle_rejects_generated_research_data(tmp_path: Path) -> None:
    wheel = _wheel(tmp_path, generated_data=True)
    provenance, binding = _provenance_inputs(wheel)
    with pytest.raises(LinuxPackagingError, match="generated research data"):
        build_linux_installer(
            wheel,
            tmp_path / "package",
            build_provenance=provenance,
            artifact_binding=binding,
        )


def test_linux_bundle_rejects_secret_bearing_paths(tmp_path: Path) -> None:
    wheel = _wheel(tmp_path, private_key_path=True)
    provenance, binding = _provenance_inputs(wheel)
    with pytest.raises(LinuxPackagingError, match="secret-bearing path"):
        build_linux_installer(
            wheel,
            tmp_path / "package",
            build_provenance=provenance,
            artifact_binding=binding,
        )


def test_linux_package_cli_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    wheel = _wheel(tmp_path)
    provenance, binding = _provenance_inputs(wheel)
    provenance_path = tmp_path / "build.json"
    binding_path = tmp_path / "binding.json"
    provenance_path.write_bytes(provenance)
    binding_path.write_bytes(binding)
    output = tmp_path / "linux"
    assert (
        main(
            [
                "package",
                "linux",
                "--wheel",
                str(wheel),
                "--output",
                str(output),
                "--build-provenance",
                str(provenance_path),
                "--artifact-binding",
                str(binding_path),
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert Path(result["bundle"]).is_file()
    assert result["wheel_sha256"]


def test_installer_supply_verification_rejects_altered_inputs(tmp_path: Path) -> None:
    """MT-IN-01 rejects wheel or provenance changes before lifecycle mutation."""
    wheel = _wheel(tmp_path)
    provenance, binding = _provenance_inputs(wheel)
    verified = verify_installer_supply(
        wheel, build_provenance=provenance, artifact_binding=binding
    )
    assert verified.wheel_sha256 == sha256_bytes(wheel.read_bytes())

    wheel.write_bytes(wheel.read_bytes() + b"altered")
    with pytest.raises(LinuxPackagingError, match="binding is inconsistent"):
        verify_installer_supply(
            wheel, build_provenance=provenance, artifact_binding=binding
        )
    with pytest.raises(LinuxPackagingError, match="provenance"):
        verify_installer_supply(
            _wheel(tmp_path),
            build_provenance=provenance.replace(
                b'"schema_version":1', b'"schema_version":2'
            ),
            artifact_binding=binding,
        )
