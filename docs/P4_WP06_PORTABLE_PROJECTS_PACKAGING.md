# P4-WP06 Portable Projects and Packaging

P4-WP06 adds a deterministic exchange format for P4-WP01 projects and a
documented Linux application installer path. It changes no model, parameter,
plugin-trust, registry, queue-resource, cancellation, recovery, raw-artifact,
or report contract.

## Portable project archive

A `.biomesh` archive is a stored, deterministic ZIP with fixed metadata. New
archives use strict schema-version 2 `archive.json`, which identifies the
BioMesh version, project, source and portable project hashes, calibration
boundary, inclusion policy, and every carried regular file by role, byte size,
and SHA-256. The payload is:

- a portable `project.json` whose accepted fixture references point to embedded
  hash-verified fixture bytes;
- `campaign_state.json` rebound only to that portable definition hash;
- the fixture configurations plus all five exact registry-selected biological
  parameter documents required by the accepted campaign executor; and
- every artifact and completion receipt for each hash-verified completed run.

Parameter resources are stored at contained paths that preserve the fixture's
relative references. Their bytes are checksum-inventoried and cross-checked
against the prospective execution identity before import and again before
execution. Plugin code/trust, registry documents/trust, and queue state remain
non-transferable; carrying exact selection hashes as provenance grants none of
them.

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

Legacy archive/project schema version 1 remains verifiable and importable for
historical completed results. An unfinished legacy project cannot be exported
as executable or resumed because missing model/plugin provenance is never
backfilled. Completed bytes and legacy receipts remain unchanged.

SHA-256 detects accidental corruption; it is not a digital signature or proof
of author identity. No plugin, plugin approval, registry export, registry trust,
or queue state is carried or inferred. Re-enqueue an imported project
explicitly if local queue execution is wanted. Import never grants third-party
plugin trust.

## Clean-clone or installed reproduction

The tracked P4-WP06 manufactured validation definition remains
`validation/p4_wp06/project.json`. The P4A audit authority uses the broader
`experiments/platform_reference.yaml`: two accepted manufactured conditions at
fixed seeds 101, 202, and 303. Both remain `CALIBRATION_REQUIRED`
software-validation input. A pending-archive reproduction path is:

```bash
python -m biomesh project create experiments/platform_reference.yaml SOURCE_PROJECT
python -m biomesh project export SOURCE_PROJECT --output project.biomesh

# Run these commands outside the clone with an installed BioMesh package.
biomesh project verify-archive /path/to/project.biomesh
biomesh project import /path/to/project.biomesh IMPORTED_PROJECT
biomesh campaign resume IMPORTED_PROJECT platform-reference
biomesh campaign status IMPORTED_PROJECT platform-reference
```

The imported pending campaign completes all six runs without the source clone.
Separately, archives carrying completed artifacts and receipts preserve every
source byte and pass the immutable completed-run verifier. This establishes
portable software reproduction, not biological calibration or experimental
validity.

## Linux application package

The Linux build consumes exactly one BioMesh wheel and publishes a new
architecture-labelled `.tar.gz` containing the wheel, `install.sh`,
`INSTALL.md`, `PROVENANCE.json`, and `SHA256SUMS`. Tar and gzip timestamps,
ownership, permissions, and member order are fixed for reproducible bundle
bytes.

Build with Python 3.14 from a clean clone:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]" hatchling
python -m biomesh provenance build --source . --output dist
python -m biomesh provenance verify dist/biomesh-0.5.0-provenance.json
```

Extract and install for the current user:

```bash
tar -xzf dist/biomesh-*-linux-*.tar.gz
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

P5-WP02 supersedes the former direct Hatchling/`package linux` publication
path with the provenance-bound whole-set command above. The accepted P4-WP06
archive and installer behavior is unchanged; publishable P5 artifacts now
require the additional exact clean-source and cross-artifact verification in
`docs/P5_WP02_INSTALLED_BUILD_PROVENANCE.md`.

The bundle builder fails if the wheel contains generated project, queue,
report, raw-run, archive, CSV, Parquet, or NumPy-result data. Packaged
manufactured experiment definitions and unresolved parameter resources remain
configuration, not generated research data. User `.biomesh` archives are
always exchanged separately and explicitly.

## Migration and scope boundary

Archive/project schema version 1 has the explicit historical compatibility
behavior described above. For version 2, the imported definition changes only
external fixture locations to archive-contained relative paths and updates the
matching state definition hash. Run plans, audit sequences, run IDs, status,
artifact records, raw bytes, and completion receipts remain equal.

P4-WP06 adds no GUI archive action, automatic queue rebinding, remote service,
cloud behavior, installer auto-update, archive signing, automatic plugin trust,
registry reinterpretation, acceleration prototype, biological parameter,
scientific mechanism, calibration result, or P4A acceptance result.
