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
from biomesh.linux_packaging import LinuxPackagingError, build_linux_installer


def _wheel(tmp_path: Path, *, generated_data: bool = False) -> Path:
    path = tmp_path / f"biomesh-{__version__}-py3-none-any.whl"
    with zipfile.ZipFile(path, mode="w", compression=zipfile.ZIP_DEFLATED) as wheel:
        wheel.writestr("biomesh/__init__.py", b"VERSION = 'test'\n")
        wheel.writestr(
            f"biomesh-{__version__}.dist-info/METADATA",
            f"Name: biomesh\nVersion: {__version__}\n".encode(),
        )
        if generated_data:
            wheel.writestr("biomesh/outputs/run_metadata.json", b"{}")
    return path


def test_linux_bundle_is_deterministic_and_contains_no_research_data(
    tmp_path: Path,
) -> None:
    wheel = _wheel(tmp_path)
    first = build_linux_installer(wheel, tmp_path / "first")
    second = build_linux_installer(wheel, tmp_path / "second")
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
    assert any(name.endswith(".whl") for name in names)
    assert b"project import" in installer_bytes or b"pip install" in installer_bytes
    assert not any("run_metadata.json" in name for name in names)
    assert not any("campaign_state.json" in name for name in names)


def test_linux_bundle_rejects_generated_research_data(tmp_path: Path) -> None:
    wheel = _wheel(tmp_path, generated_data=True)
    with pytest.raises(LinuxPackagingError, match="generated research data"):
        build_linux_installer(wheel, tmp_path / "package")


def test_linux_package_cli_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    wheel = _wheel(tmp_path)
    output = tmp_path / "linux"
    assert main(
        [
            "package",
            "linux",
            "--wheel",
            str(wheel),
            "--output",
            str(output),
        ]
    ) == 0
    result = json.loads(capsys.readouterr().out)
    assert Path(result["bundle"]).is_file()
    assert result["wheel_sha256"]
