# P5-WP04 Isolated Plugin Execution

## Scope and security boundary

P5-WP04 moves every reviewed non-empty plugin selection behind a fresh,
out-of-process Linux sandbox. The accepted engine, application, campaign,
queue, project, report, archive, and desktop paths retain the canonical empty
plugin set and do not import this runtime. Empty selection returns without
starting Bubblewrap, Python, or plugin code.

This work package does not approve plugins, validate plugin science, change the
simulation, embed plugin code in projects, add UI, or accept Phase 5. Review
policy remains host-owned and precedes all sandbox startup.

## Policy 1.0.0

The supported boundary requires Linux, Bubblewrap 0.8.0 or newer, util-linux
`prlimit`, libseccomp, and the repository's Python 3.14 runtime. Before startup,
the host validates the complete ordered manifest, plugin API, metadata hash,
review-policy binding, distribution/version, entry-point name/value, and a
narrow distribution root.
Any whole-set failure produces `preflight_denied` provenance and starts no
plugin code.

The distribution root is not itself a mount boundary. Preflight resolves the
entry-point module/package, rejects symlinked or non-regular payload files, and
records a path/size/SHA-256 inventory for that selected payload. The inventory
is rechecked before every operation. The sandbox mounts that selected payload
only, together with individual package roots derived from the declared direct
runtime dependency inventory; it does not mount the containing site-package
directory or unreviewed sibling files.

Each accepted operation uses a new Bubblewrap process with:

- separate mount, network, PID, IPC, UTS, cgroup, and user namespaces;
- no capabilities and parent-death handling;
- only `/usr`, `/lib*`, BioMesh, declared Python dependency roots, and the exact
  reviewed distribution root mounted read-only;
- a read-only sandbox root, private `/tmp`, private `/proc` and `/dev`, and only
  a private or host-created atomic exporter staging directory writable;
- a cleared environment containing only fixed `HOME`, `PATH`, `PYTHONPATH`, and
  Python bytecode/user-site controls;
- no host network plus seccomp denial of socket, process/thread creation,
  namespace, mount, ptrace, and BPF syscalls; and
- wall-clock, CPU, address-space, response/file-size, open-file, and one-process
  policy limits.

Bubblewrap's setup information channel distinguishes enforcement failure before
worker execution from a plugin crash. There is no in-process or less-restricted
fallback.

## Messages and result validation

Message schema 1 transports one canonical JSON request and one canonical JSON
response per fresh operation. Both directions are byte-bounded and bind plugin
API version, sandbox-policy version, plugin ID/version, exact selection hash,
operation, and request identity. Bytes cross process pipes; plugins receive no
mutable host object or engine reference.

The worker reconstructs the existing immutable species, kinetics, field,
metric, and exporter contracts. The host independently validates response
schema, version, identity, finite values, SI units, provenance and calibration
boundaries, field identity/unit/shape, safe paths, and exporter file hashes and
sizes. Export publication occurs only after complete validation and one atomic
rename. Invalid, partial, or interrupted results are discarded.

Every attempted operation carries a secret-free `PluginExecutionReceipt` with
the exact selection and set identities, policy version, request/result hashes,
limits, isolation modes, `CALIBRATION_REQUIRED`, and one explicit outcome:
`success`, `preflight_denied`, `setup_failure`, `policy_violation`, `timeout`,
`crash`, `resource_limit`, `malformed_output`, or `communication_failure`.
Successful containment is not scientific validation.

## Verification evidence

Focused tests cover MT-PL-01 through MT-PL-13: unreviewed/incompatible
preflight, policy mismatch, file read/write denial, network and process denial,
environment-secret clearing, immutable completed bytes, SI/provenance kinetics,
crash, wall timeout, CPU and memory exhaustion, malformed/wrong-identity/
oversized output, atomic nonpublication, and zero-plugin no-process identity.
The full P1-P5 regression suite provides the zero-plugin accepted-path replay;
the canonical empty-set SHA-256 remains
`1919457d222318dd73626ea9b92a26b0697d1b96230dff5ed254842ca9b310a0`.

## Residual risks

- The supported kernel, Bubblewrap, `prlimit`, libseccomp, Python runtime, and
  mounted runtime dependencies remain trusted. Root, kernel, or same-account
  host compromise is outside this boundary.
- A reviewed sandboxed plugin can return deceptive but schema-valid values or
  cause bounded failure. Review, sandboxing, calibration, and scientific
  validity remain separate.
- Engineering limits reduce per-operation impact but cannot guarantee host
  availability during system-wide exhaustion.
- Runtime libraries deliberately mounted read-only are visible to the plugin;
  projects, credentials, the caller environment, and mutable engine/completed
  state are not mounted or messaged.
- The content-bound distribution check does not authenticate a distributor or
  establish scientific validity. A host that controls the reviewed files,
  runtime, kernel, or dependency inventory remains within the trusted
  computing base.

P5A must independently assess the implementation and these residual risks.
At the P5-WP04 boundary, P5-WP05 installer lifecycle was the next work package;
it is now completed separately under `docs/P5_WP05_INSTALLER_LIFECYCLE.md`.
