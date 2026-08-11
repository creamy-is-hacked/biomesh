# P5-WP01 Threat Model and Security Requirements

**Document version:** 1.0.0

**Requirements status:** P5-WP01 baseline

**Security-control status:** Not implemented; P5-WP02 through P5-WP05 remain
blocked until this work package is complete

**Authority:** P4A accepted release `v0.4.1-audit`, audit prerequisite
`b5bb3cf8ce12e67f6d80048aab2545e89bfcabe4`, and
`docs/10_PRE_V1_ROADMAP.md`

## 1. Scope and normative language

This document defines the threat model and testable security requirements for
installed-build provenance, portable-project authenticity and optional
confidentiality, isolated plugin execution, installer lifecycle, supply-chain
verification, and their local-execution boundaries. It introduces no security
implementation, cryptographic algorithm, key material, plugin sandbox,
archive envelope, installer behavior, or scientific behavior.

`MUST`, `MUST NOT`, `REQUIRED`, and `SHALL` are normative. A future work
package may refine implementation detail only where it preserves every
requirement and misuse-test outcome here. Any requirement change requires a
new document version, an explicit rationale, updated traceability, and review
before dependent implementation continues.

The accepted P1-P4 engine, deterministic outputs, queue semantics, SI units,
parameter provenance, immutable completed artifacts, and all
`CALIBRATION_REQUIRED` boundaries are assets, not implementation surfaces for
P5-WP01. Security metadata MUST NOT silently alter scientific/request bytes,
grant plugin or registry trust, promote calibration status, or reinterpret a
completed result.

## 2. Security-property vocabulary

| Property | Required meaning in BioMesh | What it does not establish |
| --- | --- | --- |
| Integrity | Evidence that bytes or state equal a bound expected identity. Existing SHA-256 inventories provide this property for accidental or detected byte change. | Author identity, signer approval, permission to execute, confidentiality, scientific validity, or calibration. |
| Authenticity | Verified binding of exact bytes to an externally trusted signer or producer identity under an approved, algorithm-agile policy. | Authorization to run a plugin, confidentiality, scientific validity, or calibration. |
| Confidentiality | Protection of explicitly declared plaintext from unauthorized disclosure through a separately requested authenticated-encryption envelope. | Signer identity, authorization, scientific validity, or protection after an authorized recipient decrypts. |
| Authorization | A decision by host-owned policy that an identified actor or component may perform a specific operation. | Proof that content is benign, scientifically valid, sandboxed, or confidential. |
| Trust | A local, explicit policy decision grounded in an out-of-band trust source. Trust is not carried or granted by plugin or archive contents. | Byte integrity alone, provenance identity alone, or self-asserted metadata. |
| Provenance | Traceable identity and lineage for source, build, model, parameter, plugin, run, artifact, and environment inputs. | Authenticity, authorization, confidentiality, sandboxing, calibration, or scientific validation. |
| Sandboxing | Enforced least-privilege isolation of plugin execution from host files, network, secrets, mutable engine state, and undeclared resources. | Plugin approval, correctness, scientific validity, authenticity, or freedom from denial of service inside declared limits. |

Checksums MUST be described as integrity mechanisms, never as digital
signatures. A signature MAY authenticate an archive only after validation
against an out-of-band trust decision. Encryption and signing are independent
operations and MUST be requested, represented, and verified separately.

## 3. Assets

| ID | Asset | Required protection |
| --- | --- | --- |
| A-01 | Accepted P1-P4 scientific code, update order, SI contracts, and deterministic behavior | Integrity, provenance, regression stability |
| A-02 | Biological parameter documents, sources, uncertainty, notes, and calibration status | Integrity, provenance; no silent promotion from `CALIBRATION_REQUIRED` |
| A-03 | Project definitions, campaign state, run requests, receipts, reports, queue records, and completed artifacts | Integrity, immutability, provenance, authorization for publication or lifecycle mutation |
| A-04 | Source-tree identity, package version, build-tool identity, wheel, sdist, installer, and installed-file manifests | Integrity and exact provenance; authenticity only where separately required |
| A-05 | Portable archive payload, archive policy/status, signer identity, and confidential plaintext when confidentiality is requested | Integrity, authenticity status, optional confidentiality, immutable completed bytes |
| A-06 | Plugin package/code, selection manifest, review policy, API messages, and plugin execution receipts | Integrity, explicit authorization, provenance, sandboxing |
| A-07 | Mutable engine state and the zero-plugin core execution path | Isolation from plugin mutation; deterministic byte stability |
| A-08 | Local project files, archives, parameters, queues, reports, configuration, research data, environment values, credentials, and network access | Least privilege, confidentiality where applicable, non-destructive lifecycle handling |
| A-09 | Versioned installation roots, owned-file inventories, launchers, prior verified version, and recovery state | Integrity, authorization, atomicity, recoverability |
| A-10 | Security decisions, failures, and provenance records | Integrity, explicit status, actionable errors, no secret leakage |

## 4. Actors and trust posture

| ID | Actor | Posture and permitted authority |
| --- | --- | --- |
| AC-01 | Local researcher/operator | Trusted to request an operation and select explicit policy options; input supplied by the operator is not automatically trusted. |
| AC-02 | Build/release operator | Authorized to request a build from a reviewed clean source state; cannot label dirty or unresolved source as an exact clean build. |
| AC-03 | Archive producer or signer | Untrusted until the exact archive bytes and signer identity verify against host-owned trust policy. Archive contents cannot add their producer to that policy. |
| AC-04 | Archive recipient/importer | Authorized to choose an explicit legacy or confidentiality policy; cannot bypass mandatory validation or publish a partial import. |
| AC-05 | Plugin author/distributor | Supplies hostile-capable code and metadata. Review identity may authorize selection but never removes sandbox requirements. |
| AC-06 | Plugin reviewer/policy owner | May approve an exact selection through host-owned policy; approval is distinct from execution containment and scientific validation. |
| AC-07 | Installer/lifecycle operator | May request install, upgrade, rollback, uninstall, or an explicit recovery choice; cannot implicitly authorize deletion of user data or modified files. |
| AC-08 | Local unprivileged adversary or tampered-input source | May modify, replace, replay, truncate, expand, or maliciously construct archives, packages, manifests, plugin messages, filesystem entries, and lifecycle inputs. |
| AC-09 | Operating system, Python runtime, and declared build/runtime dependencies | Trusted computing base only within the declared supported Linux boundary; their compromise is residual risk, not a BioMesh guarantee. |

## 5. Entry points and trust boundaries

| ID | Boundary | Untrusted entry points | Required decision before crossing |
| --- | --- | --- | --- |
| TB-01 | Source tree to build environment | Source files, Git state, version metadata, build configuration, build tools | Resolve clean source identity and tool identity before an exact build can be published. |
| TB-02 | Built artifacts to installed runtime | Wheel, sdist, installer bundle, provenance/installed-file manifests | Verify bound artifact identities before installation or use; installed provenance must not depend on a Git checkout. |
| TB-03 | External archive to archive verifier | Archive/envelope bytes, signer/algorithm metadata, legacy status, decryption request | Apply size/structure limits, required authenticity policy, and optional confidentiality policy before project import/publication. |
| TB-04 | Verified archive to project publication | Decrypted/verified payload, portable project metadata, completed artifacts | Reapply the accepted P4 integrity/schema checks and publish atomically without granting plugin, registry, or calibration trust. |
| TB-05 | Host plugin policy to sandbox startup | Plugin selection, review identity, sandbox policy, executable/package identity | Complete authorization, compatibility, and sandbox-policy setup before any plugin code runs. |
| TB-06 | Host process to plugin process | Versioned requests/results, units, provenance, file identities, errors | Enforce immutable, schema-valid, size-bounded messages, timeouts, resource limits, and fail-closed result validation. |
| TB-07 | Installer to installation prefix and launchers | Operation request, target version, installed-file state, current launcher, recovery choice | Verify inputs and owned state before mutation; publish or restore atomically. |
| TB-08 | Installation lifecycle to user-owned data | Projects, archives, parameters, queues, reports, configuration, research data | Treat all user-owned data as outside installer ownership and never delete or rewrite it. |

## 6. Threat assumptions and exclusions

- **AS-01:** Archives, plugins, distributions, installer inputs, and their
  embedded metadata are hostile-capable even when a checksum matches.
- **AS-02:** An adversary may replace payload bytes and recompute untrusted
  checksums or self-asserted metadata. Therefore integrity alone cannot grant
  authenticity, authorization, or trust.
- **AS-03:** Inputs may use path traversal, symlinks, duplicate entries,
  malformed schemas, oversized content, resource exhaustion, interruption,
  replay, or partial-state recovery to cross a boundary.
- **AS-04:** Private keys, credentials, and confidential source datasets remain
  outside Git, archives, fixtures, logs, and distributable bundles. Trust
  anchors and revocation/expiry data are host-owned and out of band.
- **AS-05:** P5-WP03 must obtain approval for algorithm requirements before
  selecting signing or authenticated-encryption algorithms. This document
  requires algorithm agility and fail-closed policy but selects none.
- **AS-06:** The supported Linux kernel, local account, Python runtime, and
  declared dependencies form the trusted computing base. Root compromise,
  kernel compromise, physical access, and malicious replacement after an
  authorized recipient obtains plaintext are outside the declared guarantee.
- **AS-07:** A plugin may be malicious or defective. Isolation must contain its
  host access and state effects, but cannot establish biological correctness or
  prevent all computation denial within an already granted resource budget.
- **AS-08:** Existing P4 archive structure, checksum, size, path, schema,
  execution-identity, immutability, and atomic-publication validation remains
  mandatory beneath any P5 authenticity or confidentiality layer.
- **AS-09:** Queue portability is P6, biological calibration/validation is P7,
  and 3D/accelerated computing is P8. P5 security status cannot promote or
  imply those properties.
- **AS-10:** No cloud service, remote execution service, automatic plugin
  discovery, GUI workflow, or post-v1 interface is in scope.

## 7. P4A limitation-to-control matrix

All mitigation statuses are `OPEN / REQUIREMENTS DEFINED`. No row is mitigated
by P5-WP01 documentation. Closure requires the owning implementation work
package, its required negative tests, the complete regression gate, and P5A.

| ID and P4A evidence | Assets; actors | Entry point; boundary; assumptions | Abuse cases | Required controls and verification | Owner; status; residual risk after planned control |
| --- | --- | --- | --- | --- | --- |
| L-PROV-01: installed distributions record source commit as unavailable when no Git checkout exists (`docs/09_PHASE_FOUR_AUDIT.md`; `LIMITATIONS.md`) | A-01, A-04, A-10; AC-02, AC-08, AC-09 | Build/install inputs; TB-01/TB-02; AS-01-AS-03, AS-06 | Publish dirty or unresolved source as clean; substitute an artifact or manifest; backfill a commit after build; installed run loses exact source identity | BP-01-BP-07; MT-BP-01-MT-BP-08; repeated-build and clean external-install verification | P5-WP02 / build and release provenance owner; **OPEN**. Provenance identifies origin but is not signer authenticity, authorization, or scientific validation. |
| L-ARCH-AUTH-01: P4 archives detect corruption with SHA-256 but are not signed or proof of author identity | A-02, A-03, A-05, A-10; AC-03, AC-04, AC-08 | Archive bytes/metadata; TB-03/TB-04; AS-01-AS-05, AS-08 | Repack an archive and recompute checksums; self-assert signer/trust; use unknown, revoked, expired, mismatched, or replayed identity; mutate completed bytes | AR-01-AR-07, AR-10-AR-13; MT-AR-01-MT-AR-08, MT-AR-12-MT-AR-14; authenticate before import, then retain every P4 verification | P5-WP03 / archive authenticity owner; **OPEN**. A valid signature identifies a trusted signer for exact bytes; it does not authorize plugins, validate science, or establish confidentiality. |
| L-ARCH-CONF-01: P4 archives are not encrypted or confidential | A-02, A-03, A-05, A-08, A-10; AC-03, AC-04, AC-08 | Optional confidential archive input; TB-03/TB-04; AS-03-AS-06, AS-08 | Read confidential payload without authorization; tamper with ciphertext/metadata; confuse encryption with signing; leak secret material through archive/log/fixture | AR-08-AR-13; MT-AR-09-MT-AR-14; opt-in authenticated confidentiality, separate status, no partial import or secret persistence | P5-WP03 / archive confidentiality owner; **OPEN**. Protection ends at authorized decryption and is bounded by the declared envelope; authenticity and scientific trust remain separate. |
| L-PLUG-01: approved Python plugins are reviewed but not sandboxed and execute with host-process permissions | A-01-A-03, A-06-A-08, A-10; AC-05, AC-06, AC-08, AC-09 | Plugin selection/startup/messages; TB-05/TB-06; AS-01-AS-03, AS-06-AS-08 | Read arbitrary files/environment secrets; use network; mutate engine/artifacts; exploit malformed or oversized messages; crash, hang, exhaust resources; trigger silent in-process fallback | PL-01-PL-11; MT-PL-01-MT-PL-13; Linux containment, policy-failure, message-validation, resource, failure-atomicity, provenance, and zero-plugin replay tests | P5-WP04 / plugin runtime and sandbox owner; **OPEN**. The OS/runtime remain trusted; containment cannot make plugin results scientifically valid or prevent bounded job failure. |
| L-INST-01: the P4 Linux installer has no verified upgrade, rollback, or uninstaller lifecycle and only checksum-verifies its bundle | A-03, A-04, A-08-A-10; AC-02, AC-07-AC-09 | Bundle/operation/prefix/current state; TB-02/TB-07/TB-08; AS-01-AS-03, AS-06 | Install substituted input; interrupt lifecycle into partial state; overwrite or delete locally modified files; mismatch launcher/app versions; rollback to unverified state; uninstall user research data | IN-01-IN-12; MT-IN-01-MT-IN-14; manifest-bound side-by-side lifecycle, interruption recovery, modified-file gates, ownership-safe uninstall, CLI/GUI smoke tests | P5-WP05 / installer lifecycle owner with P5-WP02 provenance dependency; **OPEN**. Host/root compromise and external dependency availability remain outside the guarantee; system-package integration and automatic updating are not required. |

P4A also records local-only queue state, unresolved biological calibration, and
isolated 2D CPU acceleration limitations. They are not P5 mitigations: the
roadmap assigns them to P6, P7, and P8 respectively. P5 work MUST preserve
their current explicit statuses and MUST NOT claim them closed.

## 8. P5-WP02 installed-build provenance requirements

- **BP-01:** Every publishable wheel, sdist, and Linux installer provenance
  record MUST bind the package version, exact source commit, deterministic
  source-tree identity, build-tool names/versions, and SHA-256 identity of each
  applicable published artifact.
- **BP-02:** Source identity collection MUST finish before artifact publication
  and MUST NOT be derived from or backfilled by the artifact being identified.
- **BP-03:** Dirty, ambiguous, missing, or unresolvable source state MUST fail
  explicitly and MUST NOT be labelled or published as an exact clean build.
- **BP-04:** Installed BioMesh MUST expose the embedded exact build provenance
  without access to Git, the source tree, network services, or mutable external
  files. `UNKNOWN` or equivalent is not acceptable for a publishable P5 build.
- **BP-05:** The verifier MUST fail closed when an artifact, manifest, source
  identity, package version, build-tool identity, or cross-artifact binding is
  missing, malformed, inconsistent, duplicated, or changed.
- **BP-06:** Two builds from the same clean source and declared toolchain MUST
  produce byte-identical wheel, sdist, installer, and provenance records.
- **BP-07:** In-clone and installed executions with equal scientific inputs
  MUST preserve the accepted scientific/request/artifact bytes. Only explicitly
  documented environment metadata may differ, and each difference MUST remain
  traceable rather than silently normalized.

### Required P5-WP02 misuse and negative tests

| ID | Misuse or fault | Required fail-closed observation |
| --- | --- | --- |
| MT-BP-01 | Build from a dirty tracked or untracked source state covered by the source-identity policy | Exact clean publication is rejected; no publishable artifact is emitted. |
| MT-BP-02 | Build where Git/source identity cannot be resolved | Publication fails explicitly; no `UNKNOWN`, guessed, or backfilled commit is accepted. |
| MT-BP-03 | Modify source after identity capture but before publication | Source-tree verification fails and partial artifacts are not published. |
| MT-BP-04 | Alter a wheel, sdist, or installer byte while retaining the old manifest | Verification rejects the artifact before installation or execution. |
| MT-BP-05 | Alter or remove a provenance field, cross-artifact hash, package version, or build-tool version | Verification rejects the incomplete or inconsistent provenance. |
| MT-BP-06 | Supply duplicate or mismatched artifact records | Verification rejects ambiguity rather than choosing a record. |
| MT-BP-07 | Repeat clean builds in separate directories with the same declared toolchain | Every required artifact and manifest is byte-identical. |
| MT-BP-08 | Run the same accepted fixture in-clone and from the verified installed build | Canonical scientific/request bytes match; only documented environment fields differ and both executions expose the same source/build identities. |

## 9. P5-WP03 archive authenticity and confidentiality requirements

- **AR-01:** Signature verification MUST occur before project import or project
  publication and MUST bind every byte of the deterministic unsigned P4
  archive payload plus signer/key identity and algorithm metadata.
- **AR-02:** Signature and algorithm formats MUST be versioned and
  algorithm-agile. Unsupported versions or algorithms MUST fail closed; no
  algorithm is selected by P5-WP01.
- **AR-03:** Trust anchors, authorization, revocation, and expiry decisions MUST
  come from explicit host-owned policy outside the archive. Archive contents
  MUST NOT add or upgrade their own trust.
- **AR-04:** Unknown, revoked, expired, mismatched, malformed, or tampered
  signature states MUST fail with actionable errors before import publication.
- **AR-05:** After authenticity succeeds, every accepted P4 archive checksum,
  path, size, schema, execution-identity, completed-artifact, and atomic-import
  validation MUST still run. Signing MUST NOT replace payload integrity checks.
- **AR-06:** Legacy unsigned archives MAY remain readable only under an
  explicit caller-selected, documented compatibility policy. Their status MUST
  remain `UNAUTHENTICATED` in verification, import, provenance, and subsequent
  reporting and MUST NOT be silently upgraded.
- **AR-07:** Signing MUST NOT change deterministic unsigned payload bytes or any
  accepted completed-run artifact byte.
- **AR-08:** Confidentiality MUST be opt-in and separately requested from
  signing. Absence of encryption MUST remain explicit and MUST NOT be described
  as confidential.
- **AR-09:** The confidentiality envelope MUST provide authenticated
  decryption: wrong credentials, changed ciphertext, changed authenticated
  metadata, truncation, or unsupported format MUST fail before plaintext
  project publication and MUST leave no partial project.
- **AR-10:** Signature and confidentiality status MUST be independently
  represented so signed/plaintext, signed/confidential, unsigned/plaintext
  legacy, and policy-rejected combinations cannot be confused.
- **AR-11:** Private keys, credentials, decrypted temporary payloads, and
  confidential values MUST NOT enter the archive payload, repository, fixtures,
  logs, error messages, provenance fields, or distributable bundles.
- **AR-12:** Verification/decryption MUST retain explicit size, count, path,
  regular-file, duplicate, and resource ceilings before unbounded allocation or
  publication.
- **AR-13:** Archive authentication or decryption MUST NOT grant plugin trust,
  registry trust, execution authorization, calibration status, or scientific
  validity.

### Required P5-WP03 misuse and negative tests

| ID | Misuse or fault | Required fail-closed observation |
| --- | --- | --- |
| MT-AR-01 | Change any signed archive payload byte | Signature verification fails before project import; no target or completed byte changes. |
| MT-AR-02 | Repack content and recompute the P4 checksum inventory without a valid trusted signature | Authenticity verification fails; checksum consistency is not treated as signature validity. |
| MT-AR-03 | Put a signer, trust anchor, approval, or registry/plugin trust claim inside the archive | Host policy ignores the self-assertion and rejects an otherwise untrusted signer. |
| MT-AR-04 | Present an unknown, revoked, expired, mismatched, malformed, or unsupported signer/algorithm state | Verification fails with a distinct actionable status before import. |
| MT-AR-05 | Mismatch signature metadata and exact signed bytes | Verification fails; no compatible-algorithm guessing or fallback occurs. |
| MT-AR-06 | Import an unsigned legacy archive without selecting the legacy policy | Import fails explicitly. |
| MT-AR-07 | Import an unsigned legacy archive with the explicit policy | Import may proceed only with durable `UNAUTHENTICATED` status and unchanged legacy/completed bytes. |
| MT-AR-08 | Sign the same deterministic unsigned archive payload under the same declared deterministic test conditions | The underlying unsigned payload and completed artifacts remain byte-identical; authenticity metadata remains separately identifiable. |
| MT-AR-09 | Request confidentiality with wrong credentials | Authenticated decryption fails without publishing plaintext or a partial project. |
| MT-AR-10 | Modify, truncate, extend, or reorder ciphertext/authenticated metadata | Decryption fails before project parsing/publication. |
| MT-AR-11 | Supply an unsupported or malformed confidentiality envelope | Processing fails closed without falling back to plaintext or unsigned import. |
| MT-AR-12 | Confuse a signed-only archive with a confidential archive, or an encrypted-only policy with signer trust | Independent status checks reject the missing requested property. |
| MT-AR-13 | Place secret/private-key-like material in an archive, log, fixture, or bundle path covered by the policy | Build/test validation rejects publication and emits no secret value. |
| MT-AR-14 | Use excessive counts/sizes, duplicate paths, traversal, symlinks, non-regular entries, or malformed inner P4 data | Processing fails within declared bounds and preserves the target and completed artifacts. |

## 10. P5-WP04 isolated plugin execution requirements

- **PL-01:** Every non-empty plugin selection MUST execute out of process
  behind the declared supported Linux sandbox. No selected plugin callable may
  run during authorization, compatibility, or sandbox setup.
- **PL-02:** Complete host-owned selection authorization and compatibility
  preflight MUST precede sandbox startup. Sandbox isolation MUST NOT itself
  grant plugin trust or approval.
- **PL-03:** Sandbox policy MUST deny arbitrary project/host file access,
  network access, environment secrets, credentials, mutable engine state, and
  undeclared child/process capabilities.
- **PL-04:** Sandbox setup failure, unavailable enforcement, policy mismatch,
  or unsupported platform MUST fail before plugin code runs. There MUST be no
  silent in-process, less-restricted, or zero-plugin fallback for a requested
  non-empty selection.
- **PL-05:** Host/plugin exchange MUST use versioned, schema-valid,
  size-bounded, immutable messages containing only the minimum declared values
  or hash-bound artifact identities required by the existing API.
- **PL-06:** The host MUST validate message version, schema, units, complete
  provenance, calibration boundary, shape/length, paths, and plugin/result
  identity before accepting a result.
- **PL-07:** Wall-clock timeout, CPU, memory/address-space, message-size, and
  other declared resource limits MUST be explicit and enforced. Limit values
  are engineering policy, not biological parameters or benchmark evidence.
- **PL-08:** Plugin crash, timeout, malformed output, policy violation, resource
  exhaustion, or interrupted communication MUST fail the plugin operation
  atomically, leave core mutable state and completed artifacts unchanged, and
  publish no successful result.
- **PL-09:** Each attempted plugin operation MUST record exact selection,
  sandbox-policy version, request/result identities when available, resource
  outcome, and explicit failure category without leaking secrets.
- **PL-10:** The empty plugin selection MUST start no sandbox/plugin process and
  remain byte-identical to the P4A-accepted zero-plugin core path.
- **PL-11:** Plugin outputs retain their declared provenance and
  `CALIBRATION_REQUIRED` boundaries. Containment, successful execution, or a
  reviewed selection MUST NOT be presented as scientific validation.

### Required P5-WP04 misuse and negative tests

| ID | Misuse or fault | Required fail-closed observation |
| --- | --- | --- |
| MT-PL-01 | Request a plugin absent from the host review policy | Preflight rejects it and records zero plugin-code starts. |
| MT-PL-02 | Supply incompatible API/distribution/entry-point/metadata identity | Whole-set preflight rejects before any plugin-code start. |
| MT-PL-03 | Make sandbox setup unavailable or inject a policy/version mismatch | Requested plugin execution fails before code runs; no in-process fallback occurs. |
| MT-PL-04 | Plugin attempts to read or write an arbitrary project or host file | Access is denied; project/core/completed bytes remain unchanged and violation provenance is explicit. |
| MT-PL-05 | Plugin attempts network access | Access is denied and recorded without successful result publication. |
| MT-PL-06 | Plugin attempts to read environment secrets or credentials | Access is denied and no value appears in output, provenance, logs, or errors. |
| MT-PL-07 | Plugin attempts to mutate engine state or a completed artifact | No mutable reference/path is available; host identity checks reject effects and bytes remain unchanged. |
| MT-PL-08 | Plugin returns oversized, malformed, mutable, wrong-version, wrong-unit, unresolved-provenance, unsafe-path, or identity-mismatched output | Host rejects the complete result and publishes no partial data. |
| MT-PL-09 | Plugin crashes or exits nonzero | Operation fails explicitly; core state and completed artifacts equal their pre-call identities. |
| MT-PL-10 | Plugin hangs beyond timeout | Host terminates/contains the operation within policy and publishes no success. |
| MT-PL-11 | Plugin exhausts or attempts to exceed a declared CPU/memory/process/message limit | Limit is enforced, failure is explicit, and no completed result is published. |
| MT-PL-12 | Interrupt host/plugin communication at each publication boundary | Recovery exposes no partial successful result and preserves core/completed identities. |
| MT-PL-13 | Execute the accepted campaign with an empty plugin set | No sandbox process starts and the full P4A canonical artifact tree is byte-identical. |

## 11. P5-WP05 installer lifecycle and supply-chain requirements

- **IN-01:** Install, upgrade, rollback, and uninstall MUST accept only
  artifacts and provenance/ownership manifests whose exact identities verify
  before filesystem mutation.
- **IN-02:** Every installed application, dependency, metadata, and launcher
  file MUST be represented by a versioned owned-file manifest with its path,
  role, byte identity, and owning BioMesh version.
- **IN-03:** Versions MUST install side by side. A new version MUST NOT
  overwrite the prior verified version before the new version and launchers are
  fully verified.
- **IN-04:** Each lifecycle operation MUST be atomic or recover deterministically
  to the last verified application and launcher version after interruption.
- **IN-05:** Upgrade MUST verify the current and candidate installations,
  publish the candidate completely, run required verification, and only then
  switch launchers. Failure MUST retain or restore the prior verified version.
- **IN-06:** Rollback MUST restore the exact prior verified application and
  launcher identities and MUST reject absent, modified, ambiguous, or
  unverified rollback targets.
- **IN-07:** Modified, missing, extra-owned-path, or ownership-mismatched files
  MUST block unsafe upgrade, rollback, or removal. The operator MAY proceed
  only through an explicit documented recovery choice that identifies affected
  paths and never expands installer ownership.
- **IN-08:** Uninstall MUST remove only manifest-owned application files and
  launchers for the selected version. It MUST NOT delete or rewrite projects,
  archives, parameters, queues, reports, configuration, research data, source
  datasets, or paths not proven to be owned.
- **IN-09:** Path traversal, symlink redirection, duplicate paths, target-root
  escape, non-regular payloads, and manifest ambiguity MUST fail before
  mutation.
- **IN-10:** Lifecycle logs and errors MUST record operation, versions,
  manifest/artifact identities, verification/recovery result, and affected
  owned paths without credentials, confidential data, or research contents.
- **IN-11:** Fresh install and successful upgrade/rollback targets MUST pass
  module/CLI help and offscreen GUI smoke tests from the installed location
  before becoming current.
- **IN-12:** Lifecycle operations MUST preserve accepted project/archive
  schemas, queue semantics, completed artifacts, scientific outputs, and user
  data; they MUST NOT add automatic update, cloud, or system-package behavior.

### Required P5-WP05 misuse and negative tests

| ID | Misuse or fault | Required fail-closed observation |
| --- | --- | --- |
| MT-IN-01 | Alter candidate wheel, installer, provenance, or owned-file manifest | Verification rejects it before prefix or launcher mutation. |
| MT-IN-02 | Supply missing, duplicate, mismatched, traversal, symlinked, or out-of-root manifest entries | Operation fails before mutation and reports the offending ownership/path state. |
| MT-IN-03 | Interrupt fresh install at each staging/publication/launcher boundary | No partial version becomes current; recovery removes only owned staging data or finishes a verified state. |
| MT-IN-04 | Interrupt upgrade before and after candidate publication and launcher switch | Current launchers resolve to either the fully verified old or fully verified new version, never a mixture. |
| MT-IN-05 | Candidate install or CLI/GUI smoke verification fails during upgrade | Prior version and launchers remain or are restored exactly. |
| MT-IN-06 | Modify, remove, or add an installer-owned file before upgrade | Unsafe automatic upgrade is blocked pending an explicit recovery choice. |
| MT-IN-07 | Request rollback to a missing, altered, or unverified version | Rollback is rejected and the current verified version remains active. |
| MT-IN-08 | Interrupt rollback at each state transition | Recovery restores one complete verified application/launcher pair. |
| MT-IN-09 | Place projects, archives, parameters, queues, reports, configuration, and research data beside and beneath supported user-data roots, then uninstall | All user-owned bytes remain identical; only proven owned application files are removed. |
| MT-IN-10 | Place an unowned or locally modified file under an installation prefix, then uninstall | Removal blocks or requires explicit path-specific recovery; the unowned/modified file is not silently deleted. |
| MT-IN-11 | Interrupt uninstall at each removal/publication boundary | Recovery leaves explicit state and never deletes unowned/user data or a different version. |
| MT-IN-12 | Attempt lifecycle operation through a launcher whose target/version differs from its recorded manifest | Operation rejects ambiguity before changing either launcher or installation. |
| MT-IN-13 | Fresh install, upgrade, and rollback using verified artifacts | Each target passes installed CLI help and offscreen GUI smoke before activation. |
| MT-IN-14 | Compare retained projects and completed artifacts before and after every lifecycle path | All bytes and ownership boundaries remain unchanged. |

## 12. Cross-package verification and acceptance traceability

Every owning work package MUST implement its listed requirements with focused
automated tests and retain deterministic, secret-free evidence appropriate for
P5A. Tests MUST assert both the error and the absence of forbidden side
effects. A mere nonzero exit, exception, checksum match, or successful happy
path is insufficient.

| P5-WP01 acceptance criterion | Evidence in this document |
| --- | --- |
| Versioned threat model maps every applicable P4A security limitation to owner, mitigation status, control, test, and residual risk | Sections 1 and 7; L-PROV-01, L-ARCH-AUTH-01, L-ARCH-CONF-01, L-PLUG-01, L-INST-01 |
| Integrity, authenticity, confidentiality, authorization, trust, provenance, and sandboxing are distinct; checksums are not signatures | Section 2 and AR-01-AR-13 |
| No implementation, key material, incident, algorithm choice, or unsupported guarantee | Sections 1 and 6; all control statuses remain open |
| P5-WP02 through P5-WP05 have explicit threat-derived requirements and misuse tests | Sections 8-11, requirements BP/AR/PL/IN and tests MT-BP/MT-AR/MT-PL/MT-IN |

### Required future evidence by owner

- **P5-WP02:** exact clean-source/build manifest, dirty/unresolved failure log,
  repeated wheel/sdist/installer byte comparison, tamper failures, and
  in-clone/installed scientific-byte comparison.
- **P5-WP03:** property-state matrix, negative signature/trust/legacy cases,
  negative authenticated-confidentiality cases, inner P4 archive regression,
  secret-leak scan, and unchanged unsigned/completed payload comparison.
- **P5-WP04:** sandbox-policy and compatibility preflight report, denied
  file/network/environment/state attempts, malformed/oversized message cases,
  crash/timeout/resource/interruption isolation, and zero-plugin byte replay.
- **P5-WP05:** artifact/owned-file manifest verification, fresh/upgrade/
  rollback/uninstall paths, systematic interruption recovery, modified/unowned
  file cases, preserved user-data byte inventory, and installed CLI/GUI smoke.

P5A remains the independent authority for closing these inherited risks. A
work-package pass records implemented controls; it does not by itself erase
residual risk or accept Phase 5.

## 13. Residual-risk register

| ID | Residual risk | Treatment |
| --- | --- | --- |
| RR-01 | Build provenance can identify exact source and artifacts without proving that a distributor is trusted. | Keep provenance distinct from authenticity; require verification at installer/archive trust boundaries where applicable. |
| RR-02 | A trusted signature authenticates exact archive bytes but not scientific validity, calibration, plugin approval, or absence of malicious content. | Preserve P4 validation and explicit trust/calibration statuses; never promote them from a signature. |
| RR-03 | Confidentiality ends when an authorized recipient decrypts, and protection is limited to the declared envelope. | Record exact confidentiality status and scope; do not claim endpoint, OS, or post-decryption protection. |
| RR-04 | Explicit legacy unsigned import remains vulnerable to unauthenticated origin even when P4 checksums pass. | Require caller opt-in and durable `UNAUTHENTICATED` provenance; recommend authenticated archives without blocking historical read access. |
| RR-05 | A sandboxed plugin can return deceptive or scientifically invalid values through an allowed interface or cause a bounded operation failure. | Validate schemas/units/provenance, keep review and calibration separate, record plugin identity, and publish no result on policy/runtime failure. |
| RR-06 | Sandbox guarantees depend on the supported Linux kernel/runtime and declared enforcement boundary. | Fail closed when enforcement is unavailable or mismatched; document the tested platform and policy version in P5-WP04/P5A. |
| RR-07 | A privileged/root or already-compromised same-account actor may modify installed files, trust policy, or decrypted data outside BioMesh operation boundaries. | Detect state at BioMesh entry points where required; do not claim protection from host compromise. |
| RR-08 | Installer lifecycle cannot guarantee third-party dependency availability or system-package integration. | Bind accepted installed inputs/files and recover locally; automatic updates and system integration remain out of scope. |
| RR-09 | Resource limits reduce impact but cannot guarantee availability under host-wide exhaustion. | Fail operations explicitly, preserve completed artifacts, and record the resource outcome. |
| RR-10 | P4A limitations assigned to P6-P8 remain open. | Preserve explicit queue-portability, calibration, and acceleration boundaries until their owning phases and audits pass. |
