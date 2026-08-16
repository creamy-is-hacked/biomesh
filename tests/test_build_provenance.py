"""Focused P5-WP02 tests for BP-01-BP-07 and MT-BP-01-MT-BP-08."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

import biomesh.distribution_build as distribution_build
from biomesh import __version__
from biomesh.build_identity import (
    BUILD_PROVENANCE_RESOURCE,
    BuildProvenanceError,
    PublicationManifest,
    canonical_json_bytes,
)
from biomesh.distribution_build import (
    build_publication,
    current_source_build_identity,
    verify_publication,
)


@pytest.fixture(scope="module")
def clean_repository(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("p5-wp02-source") / "repository"
    ignored = shutil.ignore_patterns(
        ".git",
        ".venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "build",
        "dist",
        "outputs",
        "*.egg-info",
        "*.pyc",
    )
    shutil.copytree(Path.cwd(), root, ignore=ignored)
    _run(["git", "init", "-q"], cwd=root)
    _run(["git", "config", "user.name", "BioMesh Test"], cwd=root)
    _run(["git", "config", "user.email", "biomesh@example.invalid"], cwd=root)
    _run(["git", "add", "."], cwd=root)
    _run(["git", "commit", "-q", "-m", "P5-WP02 test source"], cwd=root)
    return root


@pytest.fixture(scope="module")
def repeated_publications(
    clean_repository: Path, tmp_path_factory: pytest.TempPathFactory
) -> tuple[Path, Path, Path, Path]:
    root = tmp_path_factory.mktemp("p5-wp02-repeat")
    first_source = root / "first-source"
    second_source = root / "second-source"
    _run(["git", "clone", "-q", str(clean_repository), str(first_source)])
    _run(["git", "clone", "-q", str(clean_repository), str(second_source)])
    first_output = root / "first-publication"
    second_output = root / "second-publication"
    build_publication(first_source, first_output)
    build_publication(second_source, second_output)
    return first_source, second_source, first_output, second_output


def test_mt_bp_01_dirty_tracked_and_untracked_source_fails(
    clean_repository: Path, tmp_path: Path
) -> None:
    for mode in ("tracked", "untracked"):
        source = tmp_path / mode
        _run(["git", "clone", "-q", str(clean_repository), str(source)])
        if mode == "tracked":
            with (source / "README.md").open("ab") as file:
                file.write(b"dirty\n")
        else:
            (source / "untracked-source.txt").write_text("dirty\n")
        output = tmp_path / f"{mode}-publication"
        with pytest.raises(BuildProvenanceError, match="source state is dirty"):
            build_publication(source, output)
        assert not output.exists()


def test_mt_bp_02_missing_or_unresolvable_git_identity_fails(tmp_path: Path) -> None:
    source = tmp_path / "not-a-repository"
    source.mkdir()
    output = tmp_path / "publication"
    with pytest.raises(BuildProvenanceError, match="Git source command failed"):
        build_publication(source, output)
    assert not output.exists()


def test_mt_bp_03_changed_during_build_fails_without_publication(
    clean_repository: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    _run(["git", "clone", "-q", str(clean_repository), str(source)])
    original = distribution_build._build_wheel_and_sdist

    def build_then_mutate(source_stage: Path, output: Path) -> tuple[Path, Path]:
        artifacts = original(source_stage, output)
        with (source / "README.md").open("ab") as file:
            file.write(b"changed during build\n")
        return artifacts

    monkeypatch.setattr(distribution_build, "_build_wheel_and_sdist", build_then_mutate)
    output = tmp_path / "publication"
    with pytest.raises(BuildProvenanceError, match="source state is dirty"):
        build_publication(source, output)
    assert not output.exists()


@pytest.mark.parametrize("kind", ["wheel", "sdist", "linux_installer"])
def test_mt_bp_04_tampered_artifact_fails_before_use(
    repeated_publications: tuple[Path, Path, Path, Path],
    tmp_path: Path,
    kind: str,
) -> None:
    publication = _copy_publication(repeated_publications[2], tmp_path / kind)
    manifest_path = _manifest_path(publication)
    manifest = PublicationManifest.from_bytes(manifest_path.read_bytes())
    artifact = next(item for item in manifest.artifacts if item.kind == kind)
    with (publication / artifact.filename).open("ab") as file:
        file.write(b"tamper")
    with pytest.raises(BuildProvenanceError, match="size|SHA-256"):
        verify_publication(manifest_path)


def test_mt_bp_05_missing_or_inconsistent_provenance_fields_fail(
    repeated_publications: tuple[Path, Path, Path, Path], tmp_path: Path
) -> None:
    original = _manifest_path(repeated_publications[2]).read_bytes()
    mutations = (
        lambda data: data["build"].pop("source_commit"),
        lambda data: data["build"].__setitem__("package_version", "0.0.0"),
        lambda data: data["build"]["build_tools"][0].__setitem__(
            "version", "substituted"
        ),
        lambda data: data["artifacts"][0].__setitem__("sha256", "0" * 64),
    )
    for index, mutate in enumerate(mutations):
        publication = _copy_publication(
            repeated_publications[2], tmp_path / f"mutation-{index}"
        )
        manifest_path = _manifest_path(publication)
        value = json.loads(original)
        mutate(value)
        manifest_path.write_bytes(canonical_json_bytes(value))
        with pytest.raises(BuildProvenanceError):
            verify_publication(manifest_path)


def test_mt_bp_06_duplicate_and_mismatched_artifact_records_fail(
    repeated_publications: tuple[Path, Path, Path, Path], tmp_path: Path
) -> None:
    original = json.loads(_manifest_path(repeated_publications[2]).read_bytes())
    for label, mutate in (
        ("duplicate", lambda value: value["artifacts"].append(value["artifacts"][0])),
        (
            "mismatch",
            lambda value: value["artifacts"][0].__setitem__("kind", "wheel"),
        ),
    ):
        publication = _copy_publication(repeated_publications[2], tmp_path / label)
        manifest_path = _manifest_path(publication)
        value = json.loads(json.dumps(original))
        mutate(value)
        manifest_path.write_bytes(canonical_json_bytes(value))
        with pytest.raises(BuildProvenanceError, match="canonical|exactly one"):
            verify_publication(manifest_path)


def test_duplicate_json_fields_fail_closed(
    repeated_publications: tuple[Path, Path, Path, Path], tmp_path: Path
) -> None:
    publication = _copy_publication(repeated_publications[2], tmp_path / "json")
    manifest_path = _manifest_path(publication)
    contents = manifest_path.read_bytes()
    manifest_path.write_bytes(
        contents.replace(b'{"artifacts":', b'{"x":1,"x":2,"artifacts":', 1)
    )
    with pytest.raises(BuildProvenanceError, match="duplicate JSON field"):
        verify_publication(manifest_path)


def test_mt_bp_07_repeated_clean_builds_are_byte_identical(
    repeated_publications: tuple[Path, Path, Path, Path],
) -> None:
    first_source, second_source, first, second = repeated_publications
    assert current_source_build_identity(first_source) == current_source_build_identity(
        second_source
    )
    assert _directory_bytes(first) == _directory_bytes(second)
    assert verify_publication(_manifest_path(first)) == verify_publication(
        _manifest_path(second)
    )


def test_mt_bp_08_clone_and_installed_fixture_bytes_and_identities_match(
    repeated_publications: tuple[Path, Path, Path, Path], tmp_path: Path
) -> None:
    source, _, publication, _ = repeated_publications
    verify_publication(_manifest_path(publication))
    manifest = PublicationManifest.from_bytes(_manifest_path(publication).read_bytes())
    wheel = publication / next(
        item.filename for item in manifest.artifacts if item.kind == "wheel"
    )
    sdist = publication / next(
        item.filename for item in manifest.artifacts if item.kind == "sdist"
    )
    installer = publication / next(
        item.filename for item in manifest.artifacts if item.kind == "linux_installer"
    )
    installed = tmp_path / "installed"
    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-compile",
            "--no-deps",
            "--target",
            str(installed),
            str(wheel),
        ]
    )

    source_environment = _pythonpath(source / "src")
    installed_environment = _pythonpath(installed)
    source_identity = _run_json(
        [sys.executable, "-m", "biomesh", "provenance", "show"],
        cwd=source,
        env=source_environment,
    )
    installed_identity = _run_json(
        [sys.executable, "-m", "biomesh", "provenance", "show"],
        cwd=tmp_path,
        env=installed_environment,
    )
    assert source_identity == installed_identity == manifest.build.as_dict()

    installed_sdist = tmp_path / "installed-sdist"
    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-build-isolation",
            "--no-compile",
            "--no-deps",
            "--target",
            str(installed_sdist),
            str(sdist),
        ]
    )
    assert (
        _run_json(
            [sys.executable, "-m", "biomesh", "provenance", "show"],
            cwd=tmp_path,
            env=_pythonpath(installed_sdist),
        )
        == manifest.build.as_dict()
    )

    extracted = tmp_path / "installer"
    extracted.mkdir()
    with tarfile.open(installer, mode="r:gz") as archive:
        archive.extractall(extracted, filter="data")
    install_script = next(extracted.rglob("install.sh"))
    prefix = tmp_path / "prefix"
    _run(
        [
            str(install_script),
            "--prefix",
            str(prefix),
            "--python",
            sys.executable,
            "--no-deps",
        ]
    )
    assert (
        _run_json(
            [str(prefix / "bin" / "biomesh"), "provenance", "show"],
            cwd=tmp_path,
            env=os.environ.copy(),
        )
        == manifest.build.as_dict()
    )

    source_run = tmp_path / "source-run"
    installed_run = tmp_path / "installed-run"
    _run(
        [
            sys.executable,
            "-m",
            "biomesh",
            "run",
            "parameters/phase1_reference.toml",
            "--output",
            str(source_run),
        ],
        cwd=source,
        env=source_environment,
    )
    _run(
        [
            sys.executable,
            "-m",
            "biomesh",
            "run",
            "parameters/phase1_reference.toml",
            "--output",
            str(installed_run),
        ],
        cwd=tmp_path,
        env=installed_environment,
    )
    assert _directory_bytes(source_run) == _directory_bytes(installed_run)
    metadata = json.loads((installed_run / "run_metadata.json").read_bytes())
    assert metadata["commit_hash"] == manifest.build.source_commit
    assert metadata["package_version"] == __version__


def test_embedded_resource_is_present_in_wheel_and_sdist(
    repeated_publications: tuple[Path, Path, Path, Path],
) -> None:
    manifest = verify_publication(_manifest_path(repeated_publications[2]))
    assert manifest.build.source_commit != "UNKNOWN"
    assert manifest.build.source_commit != "UNAVAILABLE"
    assert BUILD_PROVENANCE_RESOURCE == "_build_provenance.json"


def _copy_publication(source: Path, destination: Path) -> Path:
    shutil.copytree(source, destination)
    return destination


def _manifest_path(publication: Path) -> Path:
    matches = list(publication.glob("*-provenance.json"))
    assert len(matches) == 1
    return matches[0]


def _directory_bytes(directory: Path) -> dict[str, bytes]:
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def _pythonpath(path: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(path)
    return environment


def _run_json(command: list[str], *, cwd: Path, env: dict[str, str]) -> object:
    result = _run(command, cwd=cwd, env=env)
    return json.loads(result.stdout)


def _run(
    command: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command, cwd=cwd, env=env, check=False, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return result
