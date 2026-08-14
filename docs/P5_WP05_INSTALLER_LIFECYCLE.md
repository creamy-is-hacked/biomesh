# P5-WP05 Installer Lifecycle and Supply-Chain Verification

**Policy version:** 1.0.0

**Owned-file manifest schema:** 1

**Platform:** Linux x86_64/aarch64 with Python 3.14

**Status:** Implemented; P5A acceptance remains required

## Security boundary

The P5 installer accepts the exact P5-WP02 wheel, embedded build provenance,
and installer artifact binding before it may mutate an installation prefix.
The bundle's `SHA256SUMS` covers the installer, wheel, build provenance,
artifact binding, and documentation. These hashes establish exact integrity
and provenance; they are not a distributor signature or trust decision.

Linux, the selected Python 3.14 interpreter, pip, the filesystem, and the host
account remain trusted. Root/host compromise, unavailable dependencies, system
package management, automatic updates, and remote distribution are outside the
control boundary.

## Version and ownership layout

Each candidate is installed beneath:

```text
PREFIX/
  bin/biomesh -> ../lib/biomesh/current/bin/biomesh
  bin/biomesh-gui -> ../lib/biomesh/current/bin/biomesh-gui
  lib/biomesh/
    current -> versions/VERSION-MANIFEST_SHA256
    versions/VERSION-MANIFEST_SHA256/
      .biomesh-owned.json
      app/...
      bin/biomesh
      bin/biomesh-gui
      python-path
    lifecycle-logs/NNNNNN.json
    recovery/...
```

The canonical owned-file manifest records every candidate application,
dependency, metadata, and version-specific launcher regular file with its safe
relative path, role, SHA-256, size, and owning BioMesh version. The full
manifest SHA-256 is part of the immutable version-directory name. Duplicate,
missing, extra, modified, traversal, symlinked, non-regular, ambiguous, or
out-of-root input fails explicitly.

The two prefix launchers have fixed, verified relative targets. The single
`current` symlink is the atomic activation point. A candidate version is copied
and reverified under a staging name, atomically published side by side, and
must pass installed `biomesh --help` plus offscreen `biomesh-gui --smoke-test`
before `current` changes.

## Lifecycle operations

After extracting the verified publication's Linux bundle, use:

```bash
./install.sh --install
./install.sh --upgrade
./install.sh --rollback PREVIOUS_VERSION
./install.sh --uninstall VERSION
./install.sh --recover
```

`--prefix ABSOLUTE_PATH` and `--python PYTHON3.14` select the local target and
interpreter. `--no-deps` is restricted to controlled validation where the
exact dependencies are already available.

Fresh install and upgrade publish no current version until candidate ownership
and both smoke paths verify. Rollback accepts only one exact installed target,
reruns both smoke paths, and switches only the atomic current pointer. Normal
uninstall removes only the verified selected version tree and, when it is the
sole current version, its exact fixed launchers. A current version cannot be
removed while another version exists; the operator must roll back first.

Modified, missing, or extra paths block lifecycle mutation. The Python API and
bundle command accept repeated `--acknowledge-path STATE:PATH` values only when
they exactly equal every reported mismatch. Uninstall additionally requires
`--quarantine-modified`; it moves the complete changed tree under the explicit
installer recovery directory instead of deleting any changed or unowned byte.
Acknowledgement never adds an owned path or permits silent removal.

## Recovery and logs

One canonical transaction journal records the operation, source and target
versions, version/manifest identity, phase, and explicitly affected owned
paths. A new operation refuses to proceed while a journal exists. `--recover`
then resolves only that recorded transaction:

- incomplete staging is removed while the prior current version remains;
- a fully published candidate is reverified, smoke-tested, and activated;
- interrupted rollback retains whichever complete verified target the atomic
  pointer names;
- uninstall before retirement restores the exact verified version/launchers;
- uninstall after atomic retirement finishes only the recorded removal or
  quarantine.

Sequence-numbered canonical logs record operation, versions, manifest
identity, result, recovery result, and explicitly affected owned paths. They do
not record credentials, environment values, confidential bytes, project data,
or research contents.

## User-data boundary

Projects, portable archives, biological parameters, queue state, reports,
configuration, completed artifacts, research data, and source datasets are
never installer-owned. The lifecycle code operates only on the two exact
prefix launcher paths, the installer root, a validated version tree, its
transaction journal/logs, and an explicit recovery quarantine. Focused tests
compare retained user and completed-artifact inventories byte for byte across
install, upgrade, rollback, recovery, and uninstall.

## Requirement and misuse-test traceability

| Requirements | Implementation evidence | Focused tests |
| --- | --- | --- |
| IN-01, IN-02, IN-09 | P5-WP02 supply verification; canonical `OwnedFileManifest`; manifest-hash version directory; regular contained paths only | MT-IN-01, MT-IN-02 |
| IN-03-IN-06 | Side-by-side version roots; transaction journal; smoke-before-switch; atomic `current`; exact rollback target | MT-IN-03-MT-IN-05, MT-IN-07, MT-IN-08, MT-IN-13 |
| IN-07, IN-08 | Exact mismatch acknowledgement; ownership-safe uninstall; changed-tree quarantine | MT-IN-06, MT-IN-09, MT-IN-10, MT-IN-11 |
| IN-10 | Canonical secret-free lifecycle and recovery logs | MT-IN-03, MT-IN-04, MT-IN-08, MT-IN-10, MT-IN-11 |
| IN-11 | Installed CLI help and offscreen GUI smoke before every activation | MT-IN-05, MT-IN-13 |
| IN-12 | User-data exclusion and byte-inventory comparisons; no updater, cloud, or package-manager behavior | MT-IN-09, MT-IN-14 |

## Validation evidence

On 2026-08-14, Python 3.14.4 with PySide6 6.11.1 and `cryptography` 50.0.0
passed the focused installer/packaging collection and the complete repository
suite. The full suite requires an unsandboxed host invocation because the
accepted P5-WP04 tests create their own Bubblewrap/libseccomp boundary.
A clean temporary Git clone built and verified a complete 0.5.0 publication,
then its extracted bundle passed real installed CLI help and offscreen GUI
smoke. A separately committed, non-published `0.5.0.post1` rehearsal fixture
exercised the same bundle's upgrade path and smoke gates; rollback restored
0.5.0 exactly, both versions uninstalled ownership-safely, five lifecycle logs
remained, and an adjacent user-data file retained SHA-256
`b86b4d51c5b66262daa1b2eac227710e0b7f821a6fb6ae9896123a4bc5c4c870`.
The synthetic fixture is validation evidence only and does not change the
repository/package version or create a release claim.

```text
focused installer and packaging: 30 passed
full suite: 311 passed
ruff check .: passed
mypy src: passed
git diff --check: passed
python -m biomesh --help: passed
```

P5-WP05 changes no project/archive schema, queue semantic, completed artifact,
scientific output, biological parameter, calibration status, plugin/archive
trust decision, cloud behavior, remote execution, automatic update, system
package integration, or desktop feature. P5A remains the independent authority
for accepting Phase 5 and its residual risks.
