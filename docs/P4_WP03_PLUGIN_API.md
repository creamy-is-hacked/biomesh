# P4-WP03 Plugin API

P4-WP03 adds a versioned extension boundary without importing plugins into the
accepted P1--P3 engine. The existing application and campaign paths therefore
remain the zero-plugin core path and preserve their audited artifacts, update
order, deterministic behavior, and raw-run/report traceability.

## Versioned component interfaces

`biomesh.plugin_api` defines plugin API version 1 and narrow immutable
interfaces for species, kinetics, fields, metrics, and exporters. Component
requests and results carry explicit interface versions and units. Kinetics
requests require one complete `BiologicalParameter` provenance record for each
numeric parameter and reject unresolved `CALIBRATION_REQUIRED` values before a
plugin callable can run.

Species metadata and the packaged example remain
`CALIBRATION_REQUIRED`. The field, metric, and exporter interfaces expose only
immutable caller values or hash-bound artifact identities; they do not expose
private mutable engine state.

## Controlled loading and compatibility

A `PluginSetManifest` records, for every selected plugin:

- plugin ID, plugin version, API version, component kinds, source,
  calibration status, and limitations;
- canonical metadata SHA-256;
- exact distribution name/version and entry-point name/value; and
- the out-of-band review reference.

Loading is two-stage and fails closed. BioMesh first validates the complete
manifest, API version, metadata hashes, exact entry-point identities, and an
explicit code-owned `PluginTrustPolicy`. If any selected plugin is
incompatible or absent from that policy, no entry point in the set is loaded.
Only after the whole set passes preflight may BioMesh import a factory. The
runtime metadata and every declared component interface must then equal the
reviewed declaration.

The trust policy binds the canonical SHA-256 of the complete selection,
including its metadata, distribution/version, entry point, and review
reference. The verification manifest exports both selection and metadata
hashes.

The complete ordered `PluginSetManifest` also has one canonical SHA-256. That
identity is defined for the empty manifest as well as reviewed non-empty sets,
so zero-plugin core execution is an explicit deterministic selection rather
than omitted provenance. An empty set loads no code and grants no trust.

A manifest is not a sandbox. Importing an approved entry point executes Python
code with the host process's permissions. P4-WP03 trusts only the packaged
example by default; adding another trust-policy entry requires separate human
review. Automatic discovery or execution of unreviewed third-party plugins is
not provided.

## Packaged species/kinetics example

`biomesh.example_species_kinetics` is registered in the
`biomesh.plugins` entry-point group. It provides:

- an explicitly uncalibrated, non-taxonomic example species descriptor; and
- the existing multiplicative dual-substrate Monod rate equation using only
  caller-supplied carbon and oxygen concentrations plus three SI-labelled,
  provenance-complete parameters.

It embeds no biological constant, does not modify the engine, and makes no
calibration or biological claim. The example is a software extension fixture.

## Verification application path

```text
python -m biomesh plugins verify
python -m biomesh plugins verify --output NEW_DIRECTORY
```

The first command emits a deterministic JSON verification report. The second
atomically publishes the same data as `plugin_manifest.json` and rejects an
existing output target. The report records zero-plugin compatibility, exact
loaded distribution/entry-point provenance, metadata SHA-256, limitations, and
the deterministic self-check result.

## Migration and scope boundary

No project, campaign, raw-run, report, parameter, or application schema is
changed. Existing projects and runs remain zero-plugin and are not rewritten.
P4-WP03 adds no model/parameter registry, background queue, portable archive,
Linux application packaging, acceleration, cloud execution, new biological
mechanism, or automatic trust decision. Those remain later work packages or
explicitly out of scope.
