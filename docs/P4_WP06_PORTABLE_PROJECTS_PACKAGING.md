# P4-WP06 Portable Projects and Packaging

P4-WP06 adds a deterministic exchange format for P4-WP01 projects and a
documented Linux application installer path. It changes no model, parameter,
plugin-trust, registry, queue-resource, cancellation, recovery, raw-artifact,
or report contract.

## Portable project archive

A `.biomesh` archive is a stored, deterministic ZIP with fixed metadata. Its
strict schema-version 1 `archive.json` identifies the BioMesh version, project,
source and portable project hashes, calibration boundary, inclusion policy,
and every carried regular file by role, byte size, and SHA-256. The payload is:

- a portable `project.json` whose accepted fixture references point to embedded
  hash-verified fixture bytes;
- `campaign_state.json` rebound only to that portable definition hash;
- the fixture configurations required to resolve existing campaign plans; and
- every artifact and completion receipt for each hash-verified completed run.

The archive retains all completed raw-run bytes and artifact records. Existing
Parquet/NumPy/JSON output is already the compact canonical result surface; no
lossy summary or new scientific interpretation replaces it. Pending and failed
runs remain explicit. Export rejects running work, symlinks, unexpected or
unpublished artifact paths, fixture drift, and any completed-artifact mismatch.
The source project is held under its campaign lock and is never rewritten.

Use new targets for all operations:

```bash
python -m biomesh project export PROJECT_DIRECTORY \
  --output NEW_PROJECT_ARCHIVE.biomesh
python -m biomesh project verify-archive PROJECT_ARCHIVE.biomesh
python -m biomesh project import PROJECT_ARCHIVE.biomesh \
  NEW_PROJECT_DIRECTORY
```

Verification rejects duplicate, encrypted, compressed, non-regular,
out-of-root, missing, or extra members; a 100,000-file and 64 GiB expanded-size
ceiling bounds archive processing. Every payload byte must match its recorded
size and SHA-256 before import. Import writes into a temporary sibling,
recreates the process lock, validates the complete project through
`CampaignService`, then publishes atomically.

SHA-256 detects accidental corruption; it is not a digital signature or proof
of author identity. No plugin, plugin approval, registry export, registry
identity, or queue state is carried or inferred. Re-enqueue an imported project
explicitly if local queue execution is wanted. Import never grants third-party
plugin trust.

## Clean-clone or installed reproduction

The tracked manufactured validation definition is
`validation/p4_wp06/project.json`. It contains one accepted producer-fixture run
at seed 101 and remains `CALIBRATION_REQUIRED` software-validation input. The
reproduction path is:

```bash
python -m biomesh project create validation/p4_wp06/project.json SOURCE_PROJECT
python -m biomesh campaign resume SOURCE_PROJECT portable-campaign
python -m biomesh project export SOURCE_PROJECT --output project.biomesh

# Run these commands outside the clone with an installed BioMesh package.
biomesh project verify-archive /path/to/project.biomesh
biomesh project import /path/to/project.biomesh IMPORTED_PROJECT
biomesh campaign status IMPORTED_PROJECT portable-campaign
```

The imported completed artifacts and receipts are byte-identical to the source
and pass the existing immutable completed-run verifier. This establishes
portable software reproduction, not biological calibration or experimental
validity.

## Linux application package

The Linux build consumes exactly one BioMesh wheel and publishes a new
architecture-labelled `.tar.gz` containing the wheel, `install.sh`,
`INSTALL.md`, and `SHA256SUMS`. Tar and gzip timestamps, ownership, permissions,
and member order are fixed for reproducible bundle bytes.

Build with Python 3.14 from a clean clone:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]" hatchling
python -m hatchling build --clean -d dist
python -m biomesh package linux --wheel dist/*.whl \
  --output dist/linux-installer
```

Extract and install for the current user:

```bash
tar -xzf dist/linux-installer/biomesh-*-linux-*.tar.gz
cd biomesh-*-linux-*
./install.sh
biomesh --version
QT_QPA_PLATFORM=offscreen biomesh-gui --smoke-test
```

The installer requires Linux and Python 3.14, verifies `SHA256SUMS`, installs
the wheel plus declared dependencies under a new `${HOME}/.local` versioned
directory, and creates CLI/GUI launchers. `--prefix ABSOLUTE_PATH` and
`--python PYTHON3.14` select an alternate new location/interpreter. The
`--no-deps` option is only for controlled verification where the exact runtime
dependencies already exist.

The bundle builder fails if the wheel contains generated project, queue,
report, raw-run, archive, CSV, Parquet, or NumPy-result data. Packaged
manufactured experiment definitions and unresolved parameter resources remain
configuration, not generated research data. User `.biomesh` archives are
always exchanged separately and explicitly.

## Migration and scope boundary

There is no earlier portable-project or Linux-installer schema to migrate.
P4-WP01 project/state records remain schema version 1; the imported definition
changes only external fixture locations to archive-contained relative paths and
updates the matching state definition hash. Run plans, audit sequences, run
IDs, status, artifact records, raw bytes, and completion receipts remain equal.

P4-WP06 adds no GUI archive action, automatic queue rebinding, remote service,
cloud behavior, installer auto-update, archive signing, automatic plugin trust,
registry reinterpretation, acceleration prototype, biological parameter,
scientific mechanism, calibration result, or P4-WP07/P4A behavior.
