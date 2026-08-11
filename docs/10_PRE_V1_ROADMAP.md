# BioMesh Pre-v1 Roadmap

## Purpose and authority

This document authorizes only the bounded work required to move from the
accepted P4A release `v0.4.1-audit` toward BioMesh v1. It does not authorize
post-v1 work, new desktop UI behavior, cloud execution, clinical claims, or
unreviewed scientific changes.

Work proceeds in the exact order P5, P5A, P6, P6A, P7, P7A, P8, P8A, P9,
and P9A. Only the first `INCOMPLETE` work package in
`docs/PHASE_STATUS.md` may be executed. Every audit must begin in a fresh
reviewer session from the exact pushed implementation-branch tip. A failed
audit blocks the next phase.

## Global pre-v1 gates

Every work package must preserve all accepted P1-P4 contracts and pass the
canonical repository checks in `docs/STANDARDS.md`. Additional rules apply:

- Python remains 3.14 unless the dependency policy requires a reported change.
- Scientific quantities use SI units and retain source, uncertainty, notes,
  and calibration status.
- Unknown biological values remain `CALIBRATION_REQUIRED`; no task may invent
  a value, citation, dataset, fit, benchmark, or validation result.
- Security controls fail closed. Compatibility behavior must be explicit and
  must not silently upgrade trust, provenance, or calibration status.
- Completed run artifacts remain immutable and reproducible.
- Experimental acceleration remains isolated until P8A accepts it.
- Generated research data, private keys, credentials, and confidential source
  datasets must not be committed or bundled.
- Each work package updates the changelog and phase tracker with actual command
  output. Audit artifacts belong under `validation/<audit-id>/` only when they
  are safe, deterministic, and appropriate to retain.

## Canonical branches and release tags

| ID | Exact phase name | Implementation or audit branch | Accepted tag |
| --- | --- | --- | --- |
| P5 | Phase 5 – Security and Distribution Hardening | `phase-5-security-distribution` | `v0.5.0` |
| P5A | Phase 5 Audit | `audit-phase-5` | `v0.5.1-audit` |
| P6 | Phase 6 – Portable Operations | `phase-6-portable-operations` | `v0.6.0` |
| P6A | Phase 6 Audit | `audit-phase-6` | `v0.6.1-audit` |
| P7 | Phase 7 – Calibration and Validation | `phase-7-calibration-validation` | `v0.7.0` |
| P7A | Phase 7 Audit | `audit-phase-7` | `v0.7.1-audit` |
| P8 | Phase 8 – 3D and Accelerated Computing | `phase-8-3d-acceleration` | `v0.8.0` |
| P8A | Phase 8 Audit | `audit-phase-8` | `v0.8.1-audit` |
| P9 | Phase 9 – Version 1 Release | `phase-9-version-1-release` | `v1.0.0-rc.1` |
| P9A | Version 1 Release Audit | `audit-version-1` | `v1.0.0` |

Implementation tags freeze completed phase branches for independent audit under
`docs/STANDARDS.md` Section 11.1a; they are not acceptance or release claims.
Audit tags follow Section 11.2, and P9A alone may create the final `v1.0.0`
tag.

For P5-P8, package and manifest versions match the implementation tag version;
audit tags preserve that runtime version. P9 uses package version `1.0.0rc1`.
P9A may promote only release metadata to package version `1.0.0`, after which
it must rerun every final distribution, provenance, signature, installation,
and version check before the accepted audit commit and tag.

## P5 – Phase 5 – Security and Distribution Hardening

Goal: close the security and distribution limitations recorded by P4A without
changing scientific behavior, queue semantics, or accepted artifact bytes.

### P5-WP01 Threat model and security requirements

Define assets, trust boundaries, actors, entry points, threat assumptions,
abuse cases, mitigations, residual risk, and verification requirements for
plugins, archives, installers, build provenance, and local execution.

Acceptance criteria:

- A versioned threat model maps each P4A security limitation to an owner,
  mitigation status, testable control, and residual risk.
- Trust decisions distinguish integrity, authenticity, confidentiality,
  authorization, and sandboxing; checksums are not described as signatures.
- No implementation, key material, invented incident, or unsupported security
  guarantee is introduced.
- P5-WP02 through P5-WP05 have explicit threat-derived requirements and misuse
  tests before implementation begins.

### P5-WP02 Installed-build provenance

Embed deterministic build provenance so an installed wheel or installer can
identify its exact source without requiring a Git checkout.

Acceptance criteria:

- Wheel, sdist, and installer manifests bind package version, source commit,
  source-tree identity, build-tool versions, and artifact SHA-256 values.
- Dirty or unresolvable source state fails explicitly; it cannot be published
  as an exact clean build.
- Repeated clean builds are byte-identical and report the same identities.
- In-clone and installed scientific outputs remain equal except for explicitly
  documented environment metadata.

### P5-WP03 Signed and optionally confidential archives

Add an algorithm-agile authenticity layer and a separately requested
confidentiality envelope around the accepted portable-project format.

Acceptance criteria:

- Signature verification occurs before project import and binds every archive
  byte plus signer/key identity and algorithm metadata.
- Unknown, revoked, expired, mismatched, or tampered signatures fail closed
  with actionable errors; trust is never inferred from archive contents.
- Encryption is opt-in, authenticated, and separate from signing; secrets and
  private keys never enter archives, logs, fixtures, or the repository.
- Legacy unsigned archives remain readable only under an explicit documented
  policy and retain an `UNAUTHENTICATED` status.
- Deterministic unsigned payload bytes and accepted completed-run artifacts do
  not change.

### P5-WP04 Isolated plugin execution

Move reviewed plugin execution behind a least-privilege, out-of-process Linux
boundary while preserving the zero-plugin core.

Acceptance criteria:

- Plugin code cannot access arbitrary project files, network resources,
  environment secrets, or mutable engine state under the declared sandbox.
- The host exchanges only versioned, size-bounded, immutable messages and
  validates units, provenance, schema, timeouts, and resource limits.
- Sandbox setup or policy mismatch fails before plugin code runs; no silent
  in-process fallback exists.
- Crash, timeout, malformed output, and attempted policy violation leave core
  state and completed artifacts unchanged and produce explicit provenance.
- Zero-plugin execution remains byte-identical to the P4A-accepted path.

### P5-WP05 Installer lifecycle and supply-chain verification

Add side-by-side installation, verified upgrade, rollback, and uninstall
without deleting user projects or research data.

Acceptance criteria:

- Install, upgrade, rollback, and uninstall are atomic or recover to the last
  verified version after interruption.
- Every installed file is manifest-bound; modified files block unsafe upgrade
  or removal unless the caller makes an explicit recovery choice.
- Rollback restores the prior verified application and launcher versions.
- Uninstall removes only owned application files and never user projects,
  archives, parameters, queues, reports, configuration, or research data.
- Fresh and upgrade installation paths pass CLI and offscreen GUI smoke tests.

### P5A – Phase 5 Audit

An independent security-focused reviewer must verify the threat model,
reproducible provenance, signature/confidentiality behavior, sandbox escape
controls within the declared boundary, installer recovery, and all P1-P4
regressions. Critical failures include trust granted by archive contents,
plugin execution outside the declared sandbox, secret leakage, provenance
backfilling, mutation of completed results, or destructive uninstall behavior.

Required evidence: threat-control matrix, negative signature/encryption cases,
plugin misuse and containment report, repeated-build manifest, interrupted
installer lifecycle log, regression report, findings, and residual risks.

## P6 – Phase 6 – Portable Operations

Goal: make queued research intent portable without transporting live process
identity, silently changing local resource policy, or adding remote execution.

### P6-WP01 Portable queue-intent schema

Acceptance criteria:

- A versioned manifest carries ordered campaign intent, priorities, dependency
  identities, and source project/archive hashes, but never PID, process-start,
  lock, cancellation, running, or host-specific resource receipts.
- Export requires a stable queue snapshot and hash-verifies all referenced
  projects without mutating queue or project state.
- Ambiguous, active, stale, missing, or drifted references fail explicitly.
- Equal queue intent serializes byte-identically.

### P6-WP02 Explicit import and local rebinding

Acceptance criteria:

- Import validates the complete manifest before publication and creates no
  runnable item until the caller explicitly binds project paths and new local
  CPU/memory limits.
- Imported items retain order, priority, campaign identity, and provenance but
  start in a non-running `UNBOUND` or equivalent explicit state.
- Rebinding cannot grant plugin trust, registry trust, archive trust, or
  calibration status.
- Path traversal, symlinks, duplicate identities, partial publication, and
  incompatible schema versions fail closed.

### P6-WP03 Resume, retry, and recovery across hosts

Acceptance criteria:

- A transferred pending campaign completes from a clean installation after
  explicit rebinding, while already completed artifacts remain immutable.
- Retry never duplicates a completed run; missing and failed work remains
  visible and receives deterministic audit transitions.
- Source and destination reports trace to the same run/parameter/model/plugin
  identities and distinguish environment metadata.
- Concurrent workers cannot claim one imported item or mix project artifacts.

### P6-WP04 Operational documentation and migration

Acceptance criteria:

- The supported migration matrix covers P4 local queues, P6 portable intent,
  archive schema versions, failure recovery, and unsupported downgrade paths.
- Operator commands include verify, export, import, bind, status, and dry-run
  behavior with explicit failure examples.
- No cloud service, remote scheduler, automatic path guessing, UI workflow, or
  credential transfer is introduced.

### P6A – Phase 6 Audit

An independent portability reviewer must transfer a multi-project queue intent
between clean Linux installations, rebind it under different declared resource
limits, interrupt/restart it, and verify exact completed-artifact separation.
Critical failures include transported live process state, automatic trust,
duplicate completion, artifact mixing, or silent resource-policy changes.

Required evidence: source/destination manifests, rebinding log, ordering and
resource receipts, restart/cancellation report, artifact comparison, migration
matrix, regression report, findings, and limitations.

## P7 – Phase 7 – Calibration and Validation

Goal: establish an evidence-governed path from `CALIBRATION_REQUIRED` to
explicitly scoped calibrated parameter sets and independent validation. This
phase is blocked until suitable licensed source data and domain review are
available; software completion alone cannot satisfy it.

### P7-WP01 Calibration protocol and evidence governance

Acceptance criteria:

- The protocol predeclares biological system, strains, environmental domain,
  observables, SI units, inclusion/exclusion rules, identifiability criteria,
  training/validation split, uncertainty method, and acceptance thresholds.
- Dataset licensing, consent/ethics applicability, source citations, and raw
  file hashes are explicit.
- Unknown choices remain `CALIBRATION_REQUIRED`; no placeholder is promoted.
- A qualified domain reviewer approves the protocol before fitting begins.

### P7-WP02 Versioned dataset ingestion and quality control

Acceptance criteria:

- Immutable dataset manifests bind source, license, acquisition context, units,
  transformations, exclusions, uncertainty, and raw/processed hashes.
- Unit conversion and preprocessing are deterministic, tested, reversible or
  fully traced, and never silently impute or discard observations.
- Training and validation data remain separated by enforced identifiers.
- Restricted or confidential raw data remains outside Git and distributable
  packages while retaining verifiable manifests.

### P7-WP03 Deterministic parameter estimation and uncertainty

Acceptance criteria:

- The fitting objective, parameter bounds, priors if any, optimizer, seed
  policy, convergence criteria, and uncertainty method are versioned.
- Fixed inputs reproduce parameter estimates, diagnostics, and uncertainty
  artifacts within declared numerical tolerances.
- Non-identifiability, non-convergence, boundary solutions, and insufficient
  data fail or remain explicitly unresolved; no clamping or invented result is
  allowed.
- Fitted records retain complete lineage to observations and do not overwrite
  audited `CALIBRATION_REQUIRED` presets.

### P7-WP04 Independent validation and applicability domain

Acceptance criteria:

- Frozen fitted parameters are evaluated only against the held-out validation
  set using predeclared metrics and thresholds.
- Results report uncertainty, residuals, failure cases, sensitivity to relevant
  numerical resolution, and the exact domain where claims apply.
- Software fixtures are not counted as biological validation evidence.
- Failed thresholds remain visible and block calibrated status.

### P7-WP05 Registry promotion and scientific reporting

Acceptance criteria:

- Promotion requires the exact accepted protocol, data, fit, validation,
  citations, reviewer decision, model version, and applicability-domain hashes.
- Parameter status is granular: values outside the validated scope remain
  `CALIBRATION_REQUIRED` and mixed-status models are represented explicitly.
- Revocation and supersession preserve historical identities and completed
  results; no record is rewritten in place.
- Reports distinguish calibration, validation, extrapolation, and unsupported
  use without clinical or universal biological claims.

### P7A – Phase 7 Audit

P7A requires independent software, statistical, and biological-domain review.
The audit must reproduce data transformations and fitting from authorized
inputs, rerun held-out validation, check citations and licenses, and challenge
identifiability and applicability claims. Critical failures include invented or
unlicensed evidence, training/validation leakage, irreproducible estimates,
unsupported status promotion, or omitted failed validation.

Required evidence: approved protocol, dataset manifests, transformation log,
fit and uncertainty report, held-out validation report, reviewer identities and
scope, registry promotion/rejection record, regression report, findings, and
limitations.

## P8 – Phase 8 – 3D and Accelerated Computing

Goal: add an optional audited 3D execution path and accelerated backend without
changing the accepted 2D CPU reference or presenting engineering equivalence as
scientific validation.

### P8-WP01 3D model and numerical contract

Acceptance criteria:

- The 3D domain, boundaries, discretization, capsule geometry, conservation
  laws, update order, units, tolerances, and unsupported mechanisms are explicit
  before implementation.
- Manufactured 3D diffusion, growth, mechanics, boundary, and mass-balance
  cases have analytical or independently derived references.
- 2D configuration cannot silently select 3D behavior and existing 2D output
  bytes remain unchanged.
- No biological claim extends from 2D calibration to 3D without P7 evidence
  explicitly covering that domain.

### P8-WP02 Deterministic 3D CPU reference

Acceptance criteria:

- The CPU implementation satisfies the P8-WP01 manufactured cases, convergence
  studies, mass balance, nonnegativity, boundary behavior, and deterministic
  replay.
- Memory and failure behavior are bounded and explicit for unsupported sizes.
- 3D artifacts are unit-labelled, provenance-complete, schema-versioned, and
  distinguishable from 2D artifacts.
- Existing P1-P7 paths remain unchanged.

### P8-WP03 Accelerated backend and isolation

Acceptance criteria:

- Backend selection is explicit and disabled by default until P8A; unavailable
  hardware or runtime fails without silently using a different backend.
- Device, driver, runtime, precision, kernel, compiler, and transfer settings
  are recorded.
- The accelerated backend cannot alter plugin trust, registry selection,
  campaign ordering, queue recovery, or archive identities.
- Resource exhaustion, device loss, invalid output, and unsupported precision
  fail atomically without publishing a completed run.

### P8-WP04 Equivalence, determinism, and performance methodology

Acceptance criteria:

- CPU/backend comparisons cover every stored state and accounting field over a
  predeclared case matrix with justified engineering tolerances.
- Divergence distributions, worst cases, mismatches, and nondeterminism remain
  visible; no pass is inferred from one aggregate metric.
- Performance methodology predeclares hardware, warm-up, repetitions, transfer
  cost, memory, scaling, and statistical summaries before measurement.
- No speedup, GPU, 3D, production, energy, or scientific-accuracy claim is made
  outside the measured matrix.

### P8-WP05 Application integration and provenance

Acceptance criteria:

- CLI/application/project/queue/checkpoint/report/archive paths carry exact
  dimensionality and backend identities and reject incompatible resume.
- Completed CPU and accelerated runs remain separately identifiable and
  immutable; reports never pool them silently.
- Package/install paths verify optional runtime compatibility without making
  the GPU stack mandatory for the accepted 2D CPU core.
- User-facing documentation labels 3D/backend scope, hardware requirements,
  equivalence evidence, performance evidence, and remaining limitations.

### P8A – Phase 8 Audit

An independent numerical and accelerated-computing reviewer must reproduce the
3D CPU manufactured cases and convergence evidence, run the full equivalence
matrix on declared hardware, audit failure isolation, and independently repeat
the performance protocol. Critical failures include silent fallback, hidden
divergence, broken conservation, cross-backend artifact ambiguity, unsupported
scientific claims, or regression of the accepted 2D CPU path.

Required evidence: 3D numerical validation report, complete equivalence matrix,
determinism report, hardware/software manifest, raw performance observations,
failure-injection log, 2D regression report, findings, and limitations.

## P9 – Phase 9 – Version 1 Release

Goal: freeze the accepted product contract, prove supported installation and
migration paths, and prepare a release candidate without adding new scientific
or platform behavior.

### P9-WP01 Version 1 scope, API, and schema freeze

Acceptance criteria:

- Supported models, dimensionalities, backends, plugin API, schemas, platforms,
  commands, file formats, and exclusions are enumerated.
- Public compatibility guarantees and deprecation policy are explicit.
- No unresolved Critical or Major finding from P1A-P8A remains.
- Anything not accepted by prior audits is excluded rather than implied.

### P9-WP02 Migration and backward compatibility

Acceptance criteria:

- A versioned matrix covers every retained project, archive, registry, queue,
  checkpoint, plugin, and report schema from accepted releases.
- Supported migrations are deterministic, non-destructive, provenance-complete,
  and exercised on immutable golden fixtures.
- Unsupported upgrade/downgrade paths fail with recovery guidance.
- Historical completed results are never rewritten or relabelled.

### P9-WP03 Release packaging and platform matrix

Acceptance criteria:

- Reproducible wheel, sdist, and signed Linux installer artifacts build from the
  exact release-candidate commit and contain no generated research data.
- Release-candidate package and manifest versions equal PEP 440 `1.0.0rc1` and
  the candidate is frozen by tag `v1.0.0-rc.1`.
- Every supported clean install, upgrade, rollback, uninstall, CLI, GUI smoke,
  archive, plugin, queue, and optional backend path passes on its declared
  environment.
- SBOM, dependency/license inventory, build provenance, checksums, signatures,
  and vulnerability-review results are retained.
- The repository license decision is resolved before release packaging.

### P9-WP04 Documentation, examples, and claim review

Acceptance criteria:

- User, operator, extension, security, scientific-method, calibration,
  migration, and troubleshooting documentation matches the frozen behavior.
- Every executable example is reproducible and labelled as software fixture,
  calibrated evidence, validation evidence, or unsupported demonstration.
- Accessibility and minimum-display claims are rerun for the unchanged GUI.
- Documentation contains no post-v1 promise, clinical claim, unsupported
  benchmark, or universal biological claim.

### P9-WP05 Release-candidate rehearsal

Acceptance criteria:

- `v1.0.0-rc.1` is built from the exact pushed P9 branch only after P9-WP01
  through P9-WP04 pass.
- A clean-room rehearsal executes the complete supported lifecycle from install
  through representative project completion, export/import, reporting,
  rollback, and uninstall.
- Artifact hashes, signatures, manifests, logs, findings, and rollback evidence
  are archived without secrets or generated biological claims.
- No release publication, `v1.0.0` tag, or post-v1 development begins before
  P9A accepts the candidate.

### P9A – Version 1 Release Audit

P9A is a fresh, independent release audit over the exact pushed P9 release
candidate. It reruns every repository gate, all accepted phase regression
authorities, supported migration/install matrices, security controls,
scientific-evidence boundaries, optional backend matrices, documentation
claims, artifact reproducibility, signatures, and clean-room lifecycle.

After every non-version audit gate passes, P9A may make the sole authorized
product mutation: promote release metadata from `1.0.0rc1` to `1.0.0`. The
auditor must then rebuild and rerun the complete final artifact, provenance,
signature, clean-install, lifecycle, regression, and version-consistency gates
before committing the accepted audit. Any other product change returns to P9.

Any unresolved Critical or Major finding, unsupported claim, provenance gap,
failed migration, destructive lifecycle action, scientific-evidence failure, or
non-reproducible release artifact blocks v1. Only an accepted P9A may merge to
`main` and create `v1.0.0`.

Required evidence: consolidated regression report, open/closed finding ledger,
release manifest and SBOM, signature/provenance verification, security-control
matrix, scientific claim matrix, migration matrix, clean-room lifecycle log,
documentation review, final limitations, merge SHA, and tag.

## Explicitly deferred beyond this roadmap

This roadmap does not authorize cloud services, remote schedulers, clinical
use, automatic parameter invention, new biological mechanisms not required by
an approved calibration protocol, new desktop UI features, mobile/web clients,
or any post-v1 feature. Those require a new roadmap after `v1.0.0` is accepted.

## First executable work package

`P5-WP01 – Threat model and security requirements` is the first executable
pre-v1 work package. It is documentation and test-requirement work only.
