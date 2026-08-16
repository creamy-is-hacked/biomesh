# P5-WP02 Installed-build Provenance

## Scope

P5-WP02 adds deterministic integrity and lineage records for BioMesh 0.5.0
wheel, sdist, and Linux-installer publication sets. It does not authenticate a
distributor, grant trust or authorization, sign an artifact, select a
cryptographic-signature algorithm, change installer lifecycle behavior, or
alter scientific inputs and update order.

## Canonical build and verification

Use Python 3.14 with the declared development dependencies, including
Hatchling, from the exact clean Git top level:

```bash
python -m biomesh provenance show
python -m biomesh provenance build --source . --output dist
python -m biomesh provenance verify dist/biomesh-0.5.0-provenance.json
```

`dist/` must not already exist. An output inside the source tree must be
Git-ignored. The build resolves the source identity before creating artifacts,
builds from a temporary `git archive` of that commit, rechecks the live source
and toolchain before atomic publication, and removes its staged output on any
failure. Tracked changes and non-ignored untracked files are dirty source.
Missing Git state, an unresolved commit, a submodule gitlink, a changed source
tree, or an unavailable declared build tool fails explicitly.

The publication directory contains exactly four files:

- the BioMesh wheel;
- the BioMesh sdist;
- the reproducible Linux installer `.tar.gz`;
- `biomesh-0.5.0-provenance.json`.

Verification requires this exact inventory. It validates canonical JSON with
no duplicate keys, one artifact record per required kind, safe unique
filenames, byte sizes, raw artifact SHA-256 values, package name/version,
embedded provenance, installer wheel/sdist binding, and the installer-bundled
wheel. Missing, malformed, inconsistent, duplicated, substituted, or tampered
state fails closed.

## Identity model

Every build identity records:

- schema version and package name/version;
- the exact lowercase Git commit ID;
- `git-head-ls-tree-sha256-v1`, a SHA-256 over the domain-separated canonical
  recursive `git ls-tree` bytes for that commit;
- exact versions of Python, Git, Hatchling, and the BioMesh provenance builder.

The clean-source/build identity is embedded as
`biomesh/_build_provenance.json` in the wheel and sdist. The installer contains
`PROVENANCE.json`, bound by its `SHA256SUMS`, with the same build identity and
the final wheel/sdist hashes. The external publication manifest binds the
final raw SHA-256 and size of all three artifacts.

This two-layer form is required because an artifact cannot contain its own
final raw hash without changing the bytes being hashed. An artifact is
publishable only as part of its complete verified publication directory; the
embedded record supplies immutable Git-free installed source/tool identity,
while the external manifest supplies final cross-artifact byte identities.

An installed wheel, an installation rebuilt from the sdist, and the Linux
installer expose the same immutable identity without Git, a source tree,
network access, or a mutable external record:

```bash
biomesh provenance show
```

No P5 package may report `UNKNOWN` or `UNAVAILABLE` as an exact source commit.
Run metadata uses the embedded commit when Git is unavailable.

Source-run metadata also records a domain-separated source/working-tree
identity and a `clean` or `modified` state label. A modified source run may
retain the same Git commit, but its working-state identity is distinct and is
not presented as a clean source identity. Modified identities use the
`biomesh-working-tree-v2` domain: every commit, tracked-tree, status, diff, and
untracked-file field is type-labelled and length-delimited, and each untracked
regular file binds its path, permission mode, and bytes. This versioned encoding
prevents path/content ambiguity and distinguishes an executable-mode change;
the clean `biomesh-source-tree-v1` identity is unchanged. Run dependency
metadata is sourced from one centralized inventory containing every direct
runtime dependency declared in `pyproject.toml`, including cryptography,
PySide6, and pyqtgraph; transitive dependencies are outside that explicitly
labelled inventory.

## Determinism and accepted-output boundary

The builder fixes `SOURCE_DATE_EPOCH` to the ZIP-compatible Unix epoch for
1980-01-01 and `PYTHONHASHSEED` to zero, uses a commit archive rather than the
caller's absolute path, and retains the existing deterministic installer tar,
gzip, ownership, permission, and ordering rules. Equal clean source plus equal
declared tool versions must produce equal wheel, sdist, installer, and
publication-manifest bytes.

P5-WP02 changes no scientific value, request, update order, field/table schema,
queue transition, archive format, plugin selection, or acceleration path.
In-clone and installed accepted-fixture artifacts must remain byte-equal.
Environment metadata may differ only in the existing `platform`,
`python_version`, and `dependency_versions` fields when those environments
actually differ; the package version and exact source commit must remain equal
and traceable. The new embedded/publication provenance files are distribution
metadata, not scientific artifacts.

## Residual risks and boundaries

- SHA-256 provides integrity identity, not distributor authenticity. P5-WP03
  owns archive signing/confidentiality; it is not implemented here.
- A consistently repackaged artifact set can self-report different provenance.
  Host-owned authenticity and release policy remain required outside this
  provenance control.
- The supported OS, Git, Python runtime, Hatchling, and local account are in
  the declared trusted computing base. Root or host compromise is not covered.
- P5-WP05 still owns upgrade, rollback, uninstall, modified-file handling, and
  broader installer supply-chain lifecycle controls.
- Plugin sandboxing remains P5-WP04. Portable queue state, biological
  calibration/validation, and production 3D/acceleration remain P6-P8.
