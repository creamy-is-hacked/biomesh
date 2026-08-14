"""P4-WP06 reproducible Linux installer-bundle construction."""

from __future__ import annotations

import gzip
import hashlib
import io
import os
import platform
import shutil
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from biomesh import __version__
from biomesh.build_identity import (
    BUILD_PROVENANCE_RESOURCE,
    ArtifactIdentity,
    BuildIdentity,
    BuildProvenanceError,
    canonical_json_bytes,
    strict_json_loads,
)

_FORBIDDEN_DATA_DIRECTORIES = frozenset(
    {"artifacts", "outputs", "projects", "queues", "reports", "raw"}
)
_FORBIDDEN_DATA_NAMES = frozenset(
    {
        ".biomesh-completion.json",
        "archive.json",
        "campaign_state.json",
        "project.json",
        "queue_state.json",
        "run_metadata.json",
    }
)
_FORBIDDEN_DATA_SUFFIXES = frozenset({".biomesh", ".csv", ".npy", ".npz", ".parquet"})
_FORBIDDEN_SECRET_SUFFIXES = frozenset({".key", ".p8", ".p12", ".pem", ".pk8"})


class LinuxPackagingError(ValueError):
    """Raised when a Linux installer cannot be built safely."""


@dataclass(frozen=True, slots=True)
class LinuxPackageResult:
    """Identity of one atomically published Linux installer bundle."""

    bundle: str
    bundle_sha256: str
    size_bytes: int
    wheel_sha256: str
    provenance_sha256: str

    def as_dict(self) -> dict[str, int | str]:
        return {
            "bundle": self.bundle,
            "bundle_sha256": self.bundle_sha256,
            "size_bytes": self.size_bytes,
            "wheel_sha256": self.wheel_sha256,
            "provenance_sha256": self.provenance_sha256,
        }


@dataclass(frozen=True, slots=True)
class InstallerSupplyIdentity:
    """Verified wheel and provenance identities accepted before prefix mutation."""

    package_version: str
    wheel_sha256: str
    provenance_sha256: str


def build_linux_installer(
    wheel: Path,
    output_directory: Path,
    *,
    build_provenance: bytes,
    artifact_binding: bytes,
) -> LinuxPackageResult:
    """Build a deterministic Linux installer tarball around one verified wheel."""
    if not platform.system().lower() == "linux":
        raise LinuxPackagingError("the documented application package targets Linux")
    if output_directory.exists() or output_directory.is_symlink():
        raise LinuxPackagingError(
            f"Linux package output directory already exists: {output_directory}"
        )
    if not output_directory.parent.is_dir():
        raise LinuxPackagingError("Linux package output parent must exist")
    supply = verify_installer_supply(
        wheel,
        build_provenance=build_provenance,
        artifact_binding=artifact_binding,
    )
    wheel_bytes = wheel.read_bytes()
    architecture = _linux_architecture(platform.machine())
    root = f"biomesh-{__version__}-linux-{architecture}"
    installer = _installer_script(__version__)
    install_document = _install_document(__version__)
    members = {
        f"{root}/INSTALL.md": install_document,
        f"{root}/BUILD_PROVENANCE.json": build_provenance,
        f"{root}/PROVENANCE.json": artifact_binding,
        f"{root}/install.sh": installer,
        f"{root}/packages/{wheel.name}": wheel_bytes,
    }
    checksums = "".join(
        f"{_sha256(contents)}  {path.removeprefix(f'{root}/')}\n"
        for path, contents in sorted(members.items())
    ).encode()
    members[f"{root}/SHA256SUMS"] = checksums
    bundle_name = f"biomesh-{__version__}-linux-{architecture}.tar.gz"
    temporary = Path(
        tempfile.mkdtemp(
            prefix=f".{output_directory.name}.", dir=output_directory.parent
        )
    )
    try:
        bundle = temporary / bundle_name
        _write_reproducible_tar_gz(bundle, members)
        _verify_bundle(bundle, root, set(members))
        os.replace(temporary, output_directory)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    published = output_directory / bundle_name
    contents = published.read_bytes()
    return LinuxPackageResult(
        bundle=str(published),
        bundle_sha256=_sha256(contents),
        size_bytes=len(contents),
        wheel_sha256=supply.wheel_sha256,
        provenance_sha256=supply.provenance_sha256,
    )


def verify_installer_supply(
    wheel: Path,
    *,
    build_provenance: bytes,
    artifact_binding: bytes,
) -> InstallerSupplyIdentity:
    """Verify the exact candidate wheel and its P5-WP02 provenance binding."""
    wheel_bytes = _validated_wheel(wheel)
    try:
        build = BuildIdentity.from_bytes(build_provenance)
        if build.package_version != __version__:
            raise LinuxPackagingError("installer package version is inconsistent")
        value = strict_json_loads(artifact_binding)
        if not isinstance(value, dict) or set(value) != {
            "artifacts",
            "build",
            "schema_version",
        }:
            raise LinuxPackagingError("installer provenance fields are inconsistent")
        if value["schema_version"] != 1:
            raise LinuxPackagingError("installer provenance schema is unsupported")
        if BuildIdentity.from_dict(value["build"]) != build:
            raise LinuxPackagingError("installer build provenance is inconsistent")
        artifacts_value = value["artifacts"]
        if not isinstance(artifacts_value, list) or len(artifacts_value) != 2:
            raise LinuxPackagingError("installer artifact bindings are incomplete")
        artifacts = tuple(ArtifactIdentity.from_dict(item) for item in artifacts_value)
        if (
            tuple(sorted(artifacts, key=lambda item: item.kind)) != artifacts
            or {item.kind for item in artifacts} != {"wheel", "sdist"}
            or canonical_json_bytes(value) != artifact_binding
        ):
            raise LinuxPackagingError("installer artifact bindings are inconsistent")
        wheel_records = [item for item in artifacts if item.kind == "wheel"]
        if len(wheel_records) != 1:
            raise LinuxPackagingError(
                "installer wheel binding is missing or duplicated"
            )
        wheel_record = wheel_records[0]
        if (
            wheel_record.filename != wheel.name
            or wheel_record.sha256 != _sha256(wheel_bytes)
            or wheel_record.size_bytes != len(wheel_bytes)
        ):
            raise LinuxPackagingError("installer wheel binding is inconsistent")
        with zipfile.ZipFile(io.BytesIO(wheel_bytes), mode="r") as archive:
            embedded = [
                info
                for info in archive.infolist()
                if info.filename == f"biomesh/{BUILD_PROVENANCE_RESOURCE}"
            ]
            if len(embedded) != 1:
                raise LinuxPackagingError(
                    "installer wheel build provenance is missing or duplicated"
                )
            if BuildIdentity.from_bytes(archive.read(embedded[0])) != build:
                raise LinuxPackagingError(
                    "installer wheel build provenance is inconsistent"
                )
    except BuildProvenanceError as error:
        raise LinuxPackagingError(f"invalid installer provenance: {error}") from error
    return InstallerSupplyIdentity(
        package_version=build.package_version,
        wheel_sha256=_sha256(wheel_bytes),
        provenance_sha256=_sha256(artifact_binding),
    )


def _validated_wheel(path: Path) -> bytes:
    if (
        not path.is_file()
        or path.is_symlink()
        or path.suffix != ".whl"
        or not path.name.startswith(f"biomesh-{__version__}-")
    ):
        raise LinuxPackagingError(f"expected a BioMesh {__version__} wheel: {path}")
    contents = path.read_bytes()
    try:
        with zipfile.ZipFile(io.BytesIO(contents), mode="r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                raise LinuxPackagingError("wheel contains duplicate paths")
            if not any(name.startswith("biomesh/") for name in names):
                raise LinuxPackagingError("wheel omits the biomesh package")
            for info in infos:
                _validate_wheel_member(info)
    except zipfile.BadZipFile as error:
        raise LinuxPackagingError(f"invalid wheel: {error}") from error
    return contents


def _validate_wheel_member(info: zipfile.ZipInfo) -> None:
    path = PurePosixPath(info.filename)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise LinuxPackagingError("wheel contains an unsafe path")
    mode = (info.external_attr >> 16) & 0o170000
    if mode not in {0, 0o100000, 0o040000}:
        raise LinuxPackagingError("wheel contains a non-regular payload")
    lowered_parts = {part.lower() for part in path.parts[:-1]}
    lowered_name = path.name.lower()
    if (
        lowered_parts & _FORBIDDEN_DATA_DIRECTORIES
        or lowered_name in _FORBIDDEN_DATA_NAMES
        or path.suffix.lower() in _FORBIDDEN_DATA_SUFFIXES
    ):
        raise LinuxPackagingError(
            f"installer wheel contains generated research data: {info.filename}"
        )
    if path.suffix.lower() in _FORBIDDEN_SECRET_SUFFIXES:
        raise LinuxPackagingError(
            "installer wheel contains a prohibited secret-bearing path"
        )


def _write_reproducible_tar_gz(path: Path, members: dict[str, bytes]) -> None:
    with path.open("xb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(
                fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT
            ) as archive:
                for name, contents in sorted(members.items()):
                    info = tarfile.TarInfo(name=name)
                    info.size = len(contents)
                    info.mode = 0o755 if name.endswith("/install.sh") else 0o644
                    info.mtime = 0
                    info.uid = 0
                    info.gid = 0
                    info.uname = "root"
                    info.gname = "root"
                    archive.addfile(info, io.BytesIO(contents))


def _verify_bundle(path: Path, root: str, expected: set[str]) -> None:
    try:
        with tarfile.open(path, mode="r:gz") as archive:
            members = archive.getmembers()
            names = {member.name for member in members}
            if names != expected or len(members) != len(expected):
                raise LinuxPackagingError("Linux bundle inventory mismatch")
            for member in members:
                if not member.isfile() or not member.name.startswith(f"{root}/"):
                    raise LinuxPackagingError("Linux bundle contains an unsafe member")
    except (OSError, tarfile.TarError) as error:
        raise LinuxPackagingError(f"invalid Linux bundle: {error}") from error


def _linux_architecture(value: str) -> str:
    normalized = value.lower()
    aliases = {"amd64": "x86_64", "arm64": "aarch64"}
    result = aliases.get(normalized, normalized)
    if result not in {"x86_64", "aarch64"}:
        raise LinuxPackagingError(f"unsupported Linux architecture: {value}")
    return result


def _installer_script(version: str) -> bytes:
    return rf"""#!/usr/bin/env bash
set -euo pipefail

prefix="${{HOME}}/.local"
python_command="python3.14"
no_dependencies=0
operation="install"
target_version=""
quarantine_modified=0
acknowledge_paths=()

usage() {{
  printf '%s\n' \
    "usage: install.sh LIFECYCLE [OPTIONS]" \
    "  LIFECYCLE: --install | --upgrade | --rollback VERSION" \
    "             --uninstall VERSION | --recover" \
    "                  [--prefix PATH] [--python PYTHON3.14] [--no-deps]" \
    "                  [--acknowledge-path STATE] [--quarantine-modified]"
}}

while (($#)); do
  case "$1" in
    --install) operation="install"; shift ;;
    --upgrade) operation="upgrade"; shift ;;
    --rollback) operation="rollback"; target_version="$2"; shift 2 ;;
    --uninstall) operation="uninstall"; target_version="$2"; shift 2 ;;
    --recover) operation="recover"; shift ;;
    --prefix) prefix="$2"; shift 2 ;;
    --python) python_command="$2"; shift 2 ;;
    --no-deps) no_dependencies=1; shift ;;
    --acknowledge-path) acknowledge_paths+=("$2"); shift 2 ;;
    --quarantine-modified) quarantine_modified=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done

case "$prefix" in
  /*) ;;
  *) printf '%s\n' "install prefix must be absolute" >&2; exit 2 ;;
esac
if test "$(uname -s)" != "Linux"; then
  printf '%s\n' "BioMesh installer requires Linux" >&2
  exit 2
fi
python_version="$($python_command -c \
  'import sys; print(f"{{sys.version_info.major}}.{{sys.version_info.minor}}")')"
if test "$python_version" != "3.14"; then
  printf '%s\n' "BioMesh requires Python 3.14" >&2
  exit 2
fi

bundle_root="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
(cd "$bundle_root" && sha256sum --check SHA256SUMS)
wheel="$(find "$bundle_root/packages" -maxdepth 1 -type f -name 'biomesh-*.whl' -print)"
test -n "$wheel" && test "$(printf '%s\n' "$wheel" | wc -l)" -eq 1 || {{
  printf '%s\n' "installer requires exactly one BioMesh wheel" >&2
  exit 2
}}

common_supply=(
  --wheel "$wheel"
  --build-provenance "$bundle_root/BUILD_PROVENANCE.json"
  --artifact-binding "$bundle_root/PROVENANCE.json"
)
lifecycle=(
  env "PYTHONPATH=$wheel"
  "$python_command" -m biomesh.installer_lifecycle
)

if test "$operation" = "recover"; then
  "${{lifecycle[@]}}" recover --prefix "$prefix"
  exit
fi
if test "$operation" = "rollback"; then
  test -n "$target_version" || {{ usage >&2; exit 2; }}
  "${{lifecycle[@]}}" rollback --prefix "$prefix" --version "$target_version" \
    "${{common_supply[@]}}"
  exit
fi
if test "$operation" = "uninstall"; then
  test -n "$target_version" || {{ usage >&2; exit 2; }}
  recovery_arguments=()
  for path in "${{acknowledge_paths[@]}}"; do
    recovery_arguments+=(--acknowledge-path "$path")
  done
  if ((quarantine_modified)); then
    recovery_arguments+=(--quarantine-modified)
  fi
  "${{lifecycle[@]}}" uninstall --prefix "$prefix" --version "$target_version" \
    "${{common_supply[@]}}" "${{recovery_arguments[@]}}"
  exit
fi

stage="$(mktemp -d "${{TMPDIR:-/tmp}}/biomesh-{version}.XXXXXX")"
trap 'rm -rf -- "$stage"' EXIT
mkdir -p "$stage/app" "$stage/bin"
pip_arguments=(--disable-pip-version-check --target "$stage/app")
if ((no_dependencies)); then pip_arguments+=(--no-deps); fi
"$python_command" -m pip install "${{pip_arguments[@]}}" "$wheel"
"$python_command" -c 'import sys; print(sys.executable)' > "$stage/python-path"

for command in biomesh biomesh-gui; do
  module="biomesh"
  if test "$command" = "biomesh-gui"; then module="biomesh.gui"; fi
  printf '%s\n' '#!/usr/bin/env bash' \
    'set -euo pipefail' \
    'script="$(readlink -f -- "$0")"' \
    'root="$(CDPATH= cd -- "$(dirname -- "$script")/.." && pwd)"' \
    'python_path="$(head -n 1 "$root/python-path")"' \
    "PYTHONPATH=\"\$root/app\${{PYTHONPATH:+:\$PYTHONPATH}}\" \\" \
    "  exec \"\$python_path\" -m $module \"\$@\"" \
    > "$stage/bin/$command"
  chmod 755 "$stage/bin/$command"
done

recovery_arguments=()
for path in "${{acknowledge_paths[@]}}"; do
  recovery_arguments+=(--acknowledge-path "$path")
done
"${{lifecycle[@]}}" apply "$operation" \
  --prefix "$prefix" \
  --candidate "$stage" \
  --version "{version}" \
  "${{common_supply[@]}}" \
  "${{recovery_arguments[@]}}"
trap - EXIT
rm -rf -- "$stage"
printf '%s\n' "$operation completed for BioMesh {version} under $prefix"
""".encode()


def _install_document(version: str) -> bytes:
    return f"""# BioMesh {version} Linux installer

This bundle contains the BioMesh wheel, an installer, and SHA-256 checksums.
It deliberately contains no generated project, queue, report, raw-run, or
research-result data. Manufactured experiment and unresolved parameter
resources remain clearly labelled software-validation configuration.

Install for the current user with Python 3.14:

```bash
./install.sh --install
```

Use `--prefix /absolute/path` for a different new installation prefix and
`--python /path/to/python3.14` to select the interpreter. The default install
resolves the wheel's declared runtime dependencies through pip. `--no-deps` is
reserved for controlled validation where those exact dependencies are already
available to the selected interpreter.

Lifecycle operations verify the exact wheel/build provenance before prefix
mutation, install versions side by side, and run installed CLI help plus an
offscreen GUI smoke test before activation:

```bash
./install.sh --upgrade
./install.sh --rollback PREVIOUS_VERSION
./install.sh --uninstall VERSION
./install.sh --recover
```

Modified, missing, extra, ambiguous, or ownership-mismatched application paths
block automatic changes. Exact `--acknowledge-path STATE:PATH` options identify
every affected path; changed uninstall trees also require
`--quarantine-modified` and are retained instead of deleted. There is no
automatic update or system-package integration.

Portable project archives are user research data and remain separate from this
installer. Import them explicitly with `biomesh project import` after install.
""".encode()


def _sha256(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()
