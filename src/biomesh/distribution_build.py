"""Atomic clean-source distribution building and verification for P5-WP02."""

from __future__ import annotations

import hashlib
import io
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from email.parser import BytesParser
from email.policy import default as default_email_policy
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path, PurePosixPath
from typing import Any, cast

from biomesh import __version__
from biomesh.build_identity import (
    BUILD_PROVENANCE_RESOURCE,
    SOURCE_IDENTITY_POLICY,
    ArtifactIdentity,
    BuildIdentity,
    BuildProvenanceError,
    BuildTool,
    PublicationManifest,
    canonical_json_bytes,
    load_embedded_build_identity,
    sha256_bytes,
    strict_json_loads,
)
from biomesh.linux_packaging import build_linux_installer

_SOURCE_TREE_DOMAIN = b"biomesh-source-tree-v1\0"
_SOURCE_DATE_EPOCH = "315532800"  # 1980-01-01, valid for ZIP timestamps.
_INSTALLER_PROVENANCE_NAME = "PROVENANCE.json"
_COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class PublicationResult:
    """Identity and location of one atomically published distribution set."""

    output_directory: str
    manifest: str
    manifest_sha256: str
    artifacts: tuple[ArtifactIdentity, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "artifacts": [artifact.as_dict() for artifact in self.artifacts],
            "manifest": self.manifest,
            "manifest_sha256": self.manifest_sha256,
            "output_directory": self.output_directory,
        }


def current_source_build_identity(source_root: Path) -> BuildIdentity:
    """Resolve one exact clean source and declared build-tool identity."""
    commit, tree_sha256 = _capture_clean_source(source_root)
    return BuildIdentity(
        package_name="biomesh",
        package_version=__version__,
        source_commit=commit,
        source_tree_sha256=tree_sha256,
        source_identity_policy=SOURCE_IDENTITY_POLICY,
        build_tools=_build_tools(),
    )


def runtime_build_identity() -> BuildIdentity:
    """Expose current clean-clone or immutable installed provenance."""
    source_root = _imported_source_root()
    if source_root is not None:
        return current_source_build_identity(source_root)
    return load_embedded_build_identity()


def _imported_source_root() -> Path | None:
    module = Path(__file__).resolve()
    for parent in module.parents:
        candidate = parent / "src" / "biomesh" / "distribution_build.py"
        if (parent / ".git").exists() and candidate.is_file():
            try:
                if candidate.samefile(module):
                    return parent
            except OSError:
                return None
    return None


def build_publication(source_root: Path, output_directory: Path) -> PublicationResult:
    """Build wheel, sdist, installer, and their binding manifest atomically."""
    root = source_root.resolve()
    output = output_directory.resolve()
    if platform.system().lower() != "linux":
        raise BuildProvenanceError(
            "P5 publishable distribution building requires Linux"
        )
    if output.exists() or output.is_symlink():
        raise BuildProvenanceError(
            f"publication output directory already exists: {output}"
        )
    if not output.parent.is_dir() or output.parent.is_symlink():
        raise BuildProvenanceError("publication output parent must be a real directory")
    _require_safe_output_location(root, output)

    identity = current_source_build_identity(root)
    stage_parent = _stage_parent(root, output)
    temporary = Path(tempfile.mkdtemp(prefix="biomesh-publication-", dir=stage_parent))
    try:
        source_stage = temporary / "source"
        artifact_stage = temporary / "artifacts"
        artifact_stage.mkdir()
        _export_source(root, identity.source_commit, source_stage)
        embedded_path = source_stage / "src" / "biomesh" / BUILD_PROVENANCE_RESOURCE
        embedded_path.write_bytes(identity.to_bytes())

        wheel, sdist = _build_wheel_and_sdist(source_stage, artifact_stage)
        wheel_identity = _artifact_identity("wheel", wheel)
        sdist_identity = _artifact_identity("sdist", sdist)
        _verify_wheel(wheel, identity)
        _verify_sdist(sdist, identity)

        installer_binding = _installer_binding_bytes(
            identity, (wheel_identity, sdist_identity)
        )
        installer_directory = temporary / "linux-installer"
        installer_result = build_linux_installer(
            wheel,
            installer_directory,
            build_provenance=identity.to_bytes(),
            artifact_binding=installer_binding,
        )
        nested_installer = Path(installer_result.bundle)
        installer = artifact_stage / nested_installer.name
        os.replace(nested_installer, installer)
        shutil.rmtree(installer_directory)
        installer_identity = _artifact_identity("linux_installer", installer)

        artifacts = tuple(
            sorted(
                (wheel_identity, sdist_identity, installer_identity),
                key=lambda item: item.kind,
            )
        )
        manifest = PublicationManifest(build=identity, artifacts=artifacts)
        manifest_name = f"biomesh-{__version__}-provenance.json"
        manifest_path = artifact_stage / manifest_name
        manifest_path.write_bytes(manifest.to_bytes())

        _require_unchanged_source(root, identity)
        verified = verify_publication(manifest_path)
        if verified != manifest:
            raise BuildProvenanceError("publication verification changed identity")
        _require_unchanged_source(root, identity)

        os.replace(artifact_stage, output)
        published_manifest = output / manifest_name
        return PublicationResult(
            output_directory=str(output),
            manifest=str(published_manifest),
            manifest_sha256=sha256_bytes(published_manifest.read_bytes()),
            artifacts=artifacts,
        )
    except Exception:
        if output.exists() and output.is_dir():
            shutil.rmtree(output)
        raise
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def verify_publication(manifest_path: Path) -> PublicationManifest:
    """Fail closed unless all artifact and embedded bindings are exact."""
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise BuildProvenanceError("publication manifest must be one regular file")
    try:
        contents = manifest_path.read_bytes()
    except OSError as error:
        raise BuildProvenanceError("publication manifest cannot be read") from error
    manifest = PublicationManifest.from_bytes(contents)
    if manifest.build.package_version != __version__:
        raise BuildProvenanceError("publication package version is inconsistent")
    if manifest_path.name != f"biomesh-{__version__}-provenance.json":
        raise BuildProvenanceError("publication manifest filename is inconsistent")
    expected_inventory = {manifest_path.name} | {
        artifact.filename for artifact in manifest.artifacts
    }
    actual_inventory = {path.name for path in manifest_path.parent.iterdir()}
    if actual_inventory != expected_inventory:
        raise BuildProvenanceError("publication artifact inventory is inconsistent")

    paths: dict[str, Path] = {}
    for artifact in manifest.artifacts:
        path = manifest_path.parent / artifact.filename
        if not path.is_file() or path.is_symlink():
            raise BuildProvenanceError(
                f"published {artifact.kind} artifact is missing or unsafe"
            )
        artifact_bytes = path.read_bytes()
        if len(artifact_bytes) != artifact.size_bytes:
            raise BuildProvenanceError(
                f"published {artifact.kind} size is inconsistent"
            )
        if sha256_bytes(artifact_bytes) != artifact.sha256:
            raise BuildProvenanceError(
                f"published {artifact.kind} SHA-256 is inconsistent"
            )
        paths[artifact.kind] = path

    _verify_wheel(paths["wheel"], manifest.build)
    _verify_sdist(paths["sdist"], manifest.build)
    _verify_installer(
        paths["linux_installer"],
        manifest.build,
        tuple(
            artifact
            for artifact in manifest.artifacts
            if artifact.kind in {"wheel", "sdist"}
        ),
    )
    return manifest


def _capture_clean_source(source_root: Path) -> tuple[str, str]:
    return _capture_source(source_root, require_clean=True)


def _capture_source(source_root: Path, *, require_clean: bool) -> tuple[str, str]:
    root = source_root.resolve()
    top_level = _git(root, "rev-parse", "--show-toplevel").decode().strip()
    if not top_level or Path(top_level).resolve() != root:
        raise BuildProvenanceError("source root is ambiguous or not the Git top level")
    commit = _git(root, "rev-parse", "--verify", "HEAD").decode().strip()
    if not _COMMIT_PATTERN.fullmatch(commit):
        raise BuildProvenanceError("exact source commit cannot be resolved")
    status = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    if require_clean and status:
        raise BuildProvenanceError(
            "source state is dirty; tracked or non-ignored untracked changes "
            "forbid publication"
        )
    listing = _git(root, "ls-tree", "-r", "-z", "--full-tree", commit)
    if not listing:
        raise BuildProvenanceError("source tree identity cannot be resolved")
    if b"160000 commit " in listing:
        raise BuildProvenanceError(
            "source tree contains an unresolved submodule identity"
        )
    tree_sha256 = hashlib.sha256(_SOURCE_TREE_DOMAIN + listing).hexdigest()
    return commit, tree_sha256


def _build_tools() -> tuple[BuildTool, ...]:
    try:
        hatchling_version = version("hatchling")
    except PackageNotFoundError as error:
        raise BuildProvenanceError(
            "required build tool is not installed: hatchling"
        ) from error
    git_output = (
        _run(["git", "--version"], cwd=None, label="Git build-tool identity")
        .decode()
        .strip()
    )
    if not git_output.startswith("git version "):
        raise BuildProvenanceError("Git build-tool version is malformed")
    tools = (
        BuildTool("biomesh-provenance-builder", __version__),
        BuildTool("git", git_output.removeprefix("git version ")),
        BuildTool("hatchling", hatchling_version),
        BuildTool("python", platform.python_version()),
    )
    return tuple(sorted(tools))


def _git(root: Path, *arguments: str) -> bytes:
    return _run(["git", "-C", str(root), *arguments], cwd=None, label="Git source")


def _run(command: list[str], *, cwd: Path | None, label: str) -> bytes:
    try:
        result = subprocess.run(command, cwd=cwd, check=False, capture_output=True)
    except OSError as error:
        raise BuildProvenanceError(f"{label} command is unavailable") from error
    if result.returncode != 0:
        detail = result.stderr.decode(errors="replace").strip()
        raise BuildProvenanceError(
            f"{label} command failed{f': {detail}' if detail else ''}"
        )
    return result.stdout


def _require_unchanged_source(source_root: Path, expected: BuildIdentity) -> None:
    current = current_source_build_identity(source_root)
    if current != expected:
        raise BuildProvenanceError(
            "source or declared build toolchain changed during the build"
        )


def _require_safe_output_location(source_root: Path, output: Path) -> None:
    try:
        relative = output.relative_to(source_root)
    except ValueError:
        return
    result = subprocess.run(
        ["git", "-C", str(source_root), "check-ignore", "-q", relative.as_posix()],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        raise BuildProvenanceError(
            "publication output inside the source tree must be ignored by Git"
        )


def _stage_parent(source_root: Path, output: Path) -> Path:
    try:
        output.relative_to(source_root)
    except ValueError:
        return output.parent
    build_root = source_root / "build"
    if build_root.is_symlink():
        raise BuildProvenanceError("build staging root must not be a symlink")
    build_root.mkdir(exist_ok=True)
    return build_root


def _export_source(source_root: Path, commit: str, destination: Path) -> None:
    archive_bytes = _git(source_root, "archive", "--format=tar", commit)
    destination.mkdir()
    try:
        with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:") as archive:
            members = archive.getmembers()
            names = [member.name for member in members]
            if len(names) != len(set(names)):
                raise BuildProvenanceError(
                    "Git source archive contains duplicate paths"
                )
            for member in members:
                path = PurePosixPath(member.name)
                if (
                    path.is_absolute()
                    or not path.parts
                    or any(part in {"", ".", ".."} for part in path.parts)
                    or not (member.isfile() or member.isdir())
                ):
                    raise BuildProvenanceError(
                        "Git source archive contains unsafe paths"
                    )
            archive.extractall(destination, filter="data")
    except tarfile.TarError as error:
        raise BuildProvenanceError("Git source archive is malformed") from error


def _build_wheel_and_sdist(source_stage: Path, output: Path) -> tuple[Path, Path]:
    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONHASHSEED": "0",
            "SOURCE_DATE_EPOCH": _SOURCE_DATE_EPOCH,
        }
    )
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "hatchling",
                "build",
                "-t",
                "wheel",
                "-t",
                "sdist",
                "-d",
                str(output),
            ],
            cwd=source_stage,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise BuildProvenanceError("hatchling build command is unavailable") from error
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise BuildProvenanceError(f"hatchling build failed: {detail}")
    wheels = sorted(output.glob("*.whl"))
    sdists = sorted(output.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise BuildProvenanceError("build must emit exactly one wheel and one sdist")
    return wheels[0], sdists[0]


def _artifact_identity(kind: str, path: Path) -> ArtifactIdentity:
    contents = path.read_bytes()
    return ArtifactIdentity(
        kind=cast(Any, kind),
        filename=path.name,
        sha256=sha256_bytes(contents),
        size_bytes=len(contents),
    )


def _installer_binding_bytes(
    build: BuildIdentity, artifacts: tuple[ArtifactIdentity, ArtifactIdentity]
) -> bytes:
    ordered = tuple(sorted(artifacts, key=lambda item: item.kind))
    if {artifact.kind for artifact in ordered} != {"wheel", "sdist"}:
        raise BuildProvenanceError("installer binding requires wheel and sdist")
    return canonical_json_bytes(
        {
            "artifacts": [artifact.as_dict() for artifact in ordered],
            "build": build.as_dict(),
            "schema_version": 1,
        }
    )


def _verify_wheel(path: Path, expected: BuildIdentity) -> None:
    try:
        with zipfile.ZipFile(path, mode="r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                raise BuildProvenanceError("wheel contains duplicate paths")
            for info in infos:
                _require_safe_member_path(info.filename, "wheel")
                mode = (info.external_attr >> 16) & 0o170000
                if info.flag_bits & 0x1 or mode not in {0, 0o040000, 0o100000}:
                    raise BuildProvenanceError("wheel contains an unsafe member")
            matches = [
                info
                for info in infos
                if info.filename == f"biomesh/{BUILD_PROVENANCE_RESOURCE}"
            ]
            if len(matches) != 1:
                raise BuildProvenanceError(
                    "wheel must contain exactly one embedded build provenance record"
                )
            embedded = archive.read(matches[0])
            metadata_members = [
                info
                for info in infos
                if info.filename.endswith(".dist-info/METADATA")
            ]
            if len(metadata_members) != 1:
                raise BuildProvenanceError(
                    "wheel package metadata is missing or duplicated"
                )
            _verify_package_metadata(archive.read(metadata_members[0]), expected)
    except (RuntimeError, zipfile.BadZipFile) as error:
        raise BuildProvenanceError("wheel is malformed") from error
    actual = BuildIdentity.from_bytes(embedded)
    if actual != expected:
        raise BuildProvenanceError("wheel embedded build provenance is inconsistent")


def _verify_sdist(path: Path, expected: BuildIdentity) -> None:
    try:
        with tarfile.open(path, mode="r:gz") as archive:
            members = archive.getmembers()
            names = [member.name for member in members]
            if len(names) != len(set(names)):
                raise BuildProvenanceError("sdist contains duplicate paths")
            for member in members:
                _require_safe_member_path(member.name, "sdist")
                if not (member.isfile() or member.isdir()):
                    raise BuildProvenanceError("sdist contains an unsafe member")
            matches = [
                member
                for member in members
                if PurePosixPath(member.name).parts[-3:]
                == ("src", "biomesh", BUILD_PROVENANCE_RESOURCE)
            ]
            if len(matches) != 1 or not matches[0].isfile():
                raise BuildProvenanceError(
                    "sdist must contain exactly one embedded build provenance record"
                )
            extracted = archive.extractfile(matches[0])
            if extracted is None:
                raise BuildProvenanceError("sdist build provenance cannot be read")
            embedded = extracted.read()
            metadata_members = [
                member
                for member in members
                if PurePosixPath(member.name).name == "PKG-INFO"
            ]
            if len(metadata_members) != 1 or not metadata_members[0].isfile():
                raise BuildProvenanceError(
                    "sdist package metadata is missing or duplicated"
                )
            metadata_file = archive.extractfile(metadata_members[0])
            if metadata_file is None:
                raise BuildProvenanceError("sdist package metadata cannot be read")
            _verify_package_metadata(metadata_file.read(), expected)
    except tarfile.TarError as error:
        raise BuildProvenanceError("sdist is malformed") from error
    actual = BuildIdentity.from_bytes(embedded)
    if actual != expected:
        raise BuildProvenanceError("sdist embedded build provenance is inconsistent")


def _verify_installer(
    path: Path,
    expected_build: BuildIdentity,
    expected_artifacts: tuple[ArtifactIdentity, ...],
) -> None:
    try:
        with tarfile.open(path, mode="r:gz") as archive:
            members = archive.getmembers()
            names = [member.name for member in members]
            if len(names) != len(set(names)):
                raise BuildProvenanceError("installer contains duplicate paths")
            roots: set[str] = set()
            for member in members:
                member_path = _require_safe_member_path(member.name, "installer")
                if not member.isfile():
                    raise BuildProvenanceError("installer contains an unsafe member")
                roots.add(member_path.parts[0])
            if (
                len(roots) != 1
                or not next(iter(roots)).startswith(
                    f"biomesh-{expected_build.package_version}-linux-"
                )
            ):
                raise BuildProvenanceError("installer package version is inconsistent")
            provenance_members = [
                member
                for member in members
                if PurePosixPath(member.name).name == _INSTALLER_PROVENANCE_NAME
            ]
            wheel_members = [
                member
                for member in members
                if PurePosixPath(member.name).suffix == ".whl"
            ]
            if len(provenance_members) != 1 or len(wheel_members) != 1:
                raise BuildProvenanceError(
                    "installer provenance or wheel binding is missing or duplicated"
                )
            provenance_file = archive.extractfile(provenance_members[0])
            wheel_file = archive.extractfile(wheel_members[0])
            if provenance_file is None or wheel_file is None:
                raise BuildProvenanceError("installer provenance cannot be read")
            binding = provenance_file.read()
            bundled_wheel = wheel_file.read()
    except tarfile.TarError as error:
        raise BuildProvenanceError("installer is malformed") from error

    value = strict_json_loads(binding)
    if not isinstance(value, dict) or set(value) != {
        "artifacts",
        "build",
        "schema_version",
    }:
        raise BuildProvenanceError("installer provenance fields are inconsistent")
    if value["schema_version"] != 1:
        raise BuildProvenanceError("installer provenance schema is unsupported")
    build = BuildIdentity.from_dict(value["build"])
    artifacts_value = value["artifacts"]
    if not isinstance(artifacts_value, list):
        raise BuildProvenanceError("installer artifact bindings are malformed")
    artifacts = tuple(ArtifactIdentity.from_dict(item) for item in artifacts_value)
    expected = tuple(sorted(expected_artifacts, key=lambda item: item.kind))
    if build != expected_build or artifacts != expected:
        raise BuildProvenanceError(
            "installer cross-artifact provenance is inconsistent"
        )
    if canonical_json_bytes(value) != binding:
        raise BuildProvenanceError("installer provenance JSON is not canonical")
    wheel = next(artifact for artifact in artifacts if artifact.kind == "wheel")
    if (
        PurePosixPath(wheel_members[0].name).name != wheel.filename
        or len(bundled_wheel) != wheel.size_bytes
        or sha256_bytes(bundled_wheel) != wheel.sha256
    ):
        raise BuildProvenanceError("installer bundled wheel identity is inconsistent")


def _verify_package_metadata(contents: bytes, expected: BuildIdentity) -> None:
    metadata = BytesParser(policy=default_email_policy).parsebytes(contents)
    if (
        metadata.get("Name") != expected.package_name
        or metadata.get("Version") != expected.package_version
    ):
        raise BuildProvenanceError("artifact package metadata is inconsistent")


def _require_safe_member_path(name: str, label: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise BuildProvenanceError(f"{label} contains an unsafe path")
    return path
