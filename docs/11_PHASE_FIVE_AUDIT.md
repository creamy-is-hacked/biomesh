# BioMesh P5A - Phase 5 Security and Distribution Audit

## Decision

```text
P5A ACCEPTED
```

The fresh acceptance rerun on 2026-08-15 found no remaining acceptance-blocking
defect. It evaluated the remediated tree based on rejected audit revision
`0d266186c73a209053c0d3f42a975ac5c46f35e3` on
`codex/p5a-installer-recovery-provenance`. The remediation commit containing
this record is the accepted revision. This task does not merge, tag, modify
`main`, or begin P6.

## Scope and method

The audit rerun was a distinct verification pass after implementation and
focused regression testing. It re-read the P5 threat/control ownership and the
BP, AR, PL, and IN requirements; inspected build identity capture, archive
verification ordering, sandbox mount construction, built-in and external
plugin inventory checks, installer journal identity binding, recovery
side-effect ordering, and rollback state restrictions; ran the complete P5
collection and repository gates; and used new temporary probes rather than
calling the newly added regression tests.

Every adversarial fixture was synthetic and temporary. No production or user
data, unrelated host content, credential, key, browser data, external service,
or third-party infrastructure was used.

## Requirement ownership and acceptance

| Boundary | Owner | Requirements and misuse tests | Audit result |
| --- | --- | --- | --- |
| Installed-build provenance | P5-WP02 | BP-01-BP-07; MT-BP-01-MT-BP-08 | Accepted. Source identity is captured before build, artifacts and embedded/external identities are cross-bound, installed provenance does not require Git, and changed source/artifacts fail closed. |
| Archive authenticity and optional confidentiality | P5-WP03 | AR-01-AR-13; MT-AR-01-MT-AR-14 | Accepted. Authentication and optional confidentiality precede P4 parsing/publication, trust remains host-owned, legacy status is explicit, and no downgrade or partial-publication path was found. |
| Isolated plugin execution | P5-WP04 | PL-01-PL-11; MT-PL-01-MT-PL-13 | Accepted. Only exact BioMesh-owned and authorized plugin/dependency roots are mounted; built-in and external inventories are rechecked before every operation; uncertainty and mutation fail closed. |
| Installer lifecycle and recovery | P5-WP05 with P5-WP02 identity dependency | IN-01-IN-12; MT-IN-01-MT-IN-14 | Accepted. Journal schema 2 binds source and target artifact identities, all identity checks precede smoke or state mutation, and rollback recognizes only exact recorded states. |

The limitation-to-control map in `P5_WP01_THREAT_MODEL.md` is closed as
implemented and accepted for these P5 boundaries. Queue portability,
calibration/validation, and 3D/accelerated computing remain assigned to P6,
P7, and P8 and were not promoted by this decision.

## Rejected-audit reproduction and remediation

### Plugin sandbox

On the rejected revision, installed-style discovery treated the containing
`site-packages` directory as BioMesh's root and mounted it at `/opt/biomesh`.
The synthetic sibling probe therefore returned `sentinel_visible=True`.
Built-in selection also bypassed the recorded distribution-inventory
comparison when its distribution root equalled that broad package root, so a
mutated built-in payload returned `inventory_matches=False` while preflight
still accepted it.

The remediated implementation discovers only the exact `biomesh` package
directory and its single BioMesh `.dist-info` directory, validates both, and
mounts them individually. It separately mounts only the selected plugin
payload and declared dependency package roots. It has no fallback to a parent
installation directory. Both built-in and external selections must match
their recorded file inventories before each operation.

An independent installed-layout probe used a temporary
`fake-site-packages/biomesh` beside
`fake-site-packages/undeclared_sibling/sentinel.txt` and a separately
authorized plugin. Results:

```text
worker_available=True
site_packages_bound=False
biomesh_package_bound=True
authorized_plugin_bound=True
sentinel_visible=False
sentinel_outcome=policy_violation
builtin_inventory_matches=False
builtin_preflight_accepted=False
builtin_mutation_outcome=preflight_denied
external_preflight_accepted=False
external_mutation_outcome=preflight_denied
```

This closes the original broad-mount and built-in-inventory findings while
retaining the worker, BioMesh package, authorized plugin, and declared
dependency paths.

### Installer recovery

On the rejected revision, recovery verified that a tree was internally valid
but did not compare the candidate's complete identity with the transaction
journal before smoke and activation. Independently changing `wheel_sha256` or
`provenance_sha256` still produced `verified_candidate_activated`, invoked
smoke, changed `current`, and deleted the journal. Rollback similarly retained
a valid current version unrelated to its recorded source or target.

The remediated journal schema 2 records exact source and target version,
manifest, wheel, and provenance identities. A centralized comparison verifies
every applicable identity before internal acceptance, smoke, launcher or
`current` mutation, activation, retirement/finalization, logging success, or
journal deletion. Rollback accepts only exact source or target state. A
mismatch raises an explicit recovery error and retains the journal. Legacy
schema-1 interrupted journals are not guessed or upgraded and fail closed for
operator diagnosis.

Independent temporary recovery probes produced:

```text
wheel_sha256_mismatch_rejected=True smoke_calls=0 current_unchanged=True launchers_unchanged=True journal_retained=True
provenance_sha256_mismatch_rejected=True smoke_calls=0 current_unchanged=True launchers_unchanged=True journal_retained=True
manifest_sha256_mismatch_rejected=True smoke_calls=0 current_unchanged=True launchers_unchanged=True journal_retained=True
version_mismatch_rejected=True smoke_calls=0 current_unchanged=True launchers_unchanged=True journal_retained=True
exact_identity_recovery_succeeded=True smoke_calls=1 journal_present=False
unrelated_rollback_state_rejected=True current_unchanged=True launchers_unchanged=True journal_retained=True
```

This closes the original recovery identity and rollback-state findings, with
the required fail-closed ordering directly observed.

## Regression and gate evidence

The focused eight-file P5 collection passed with no failures or skips:

```text
118 passed, 0 failed, 0 skipped
```

The exact files were `test_build_provenance.py`, `test_provenance.py`,
`test_archive_security.py`, `test_plugin_api.py`, `test_plugin_sandbox.py`,
`test_installer_lifecycle.py`, `test_linux_packaging.py`, and
`test_gui_backend.py`. The sandbox regressions also reject symlinked BioMesh
metadata and declared-dependency roots before either could become a broad
mount.

The final repository gates on Python 3.14.4 passed:

```text
python -m biomesh --help: exit 0
ruff check .: exit 0
mypy src: exit 0 (65 source files)
pytest -q: exit 0 (352 passed, 0 failed, 0 skipped)
git diff --check: exit 0
```

The complete suite covers the earlier P1-P4 behavior as well as P5. No skip or
expected failure affecting P5 acceptance was hidden.

## Findings and residual risks

No Critical, High, or Medium finding remains. No new acceptance-blocking
defect was identified.

- The supported Linux kernel, Bubblewrap, libseccomp, `prlimit`, Python
  runtime, filesystem atomicity, and explicitly mounted runtime dependencies
  remain trusted. Root, kernel, runtime, or same-account host compromise is
  outside the BioMesh boundary.
- Inventory validation occurs immediately before each operation, but the
  trusted host filesystem is not an immutable snapshot; a host actor able to
  race or replace reviewed files is within the trusted computing base.
- Sandboxing contains host effects but cannot make schema-valid plugin output
  scientifically correct or eliminate bounded denial of service.
- Journal schema 1 predates complete source/target identity binding. An
  interrupted legacy journal fails closed and requires explicit operator
  diagnosis rather than an unsafe inferred recovery.
- SHA-256 build and installer provenance is integrity evidence, not distributor
  authenticity. Archive signing trust and private-key custody remain external
  host policy.
- Biological values remain `CALIBRATION_REQUIRED`; portable queue operations,
  biological validation, and 3D/acceleration remain P6-P8 work.

## Phase boundary

```text
P5A COMPLETE
P6 remains untouched and may proceed only in a separate subsequent task.
```
