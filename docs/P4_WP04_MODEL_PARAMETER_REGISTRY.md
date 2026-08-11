# P4-WP04 Model and Parameter Registry

P4-WP04 adds a deterministic declarative registry beside the accepted engine,
project/campaign, plugin, raw-run, and report paths. It does not rewrite those
contracts or make registry data executable by itself.

## Named and versioned records

`registry.json` is a strict schema-version 1 document. Every model and
parameter-set record has a stable ID, explicit version, and canonical SHA-256.
The complete registry also has a canonical SHA-256. Equal semantic inputs
therefore produce byte-identical exports and identities suitable for later
run-manifest traceability.

A model record declares:

- its exact parameter-schema ID and sorted required parameter names/SI units;
- plugin API version 1 and any exact required reviewed plugin identities;
- source, compatibility reference, calibration status, and limitations.

A parameter-set record binds its exact model ID/version and schema ID, source
SHA-256, and sorted parameter records. It distinguishes `MEASURED`,
`LITERATURE_DERIVED`, `FITTED`, `ASSUMED`, and `CALIBRATION_REQUIRED`
provenance independently from calibration status. Every parameter retains its
value, SI unit, source, citations, uncertainty, notes, and calibration status.
Numeric values require a non-placeholder provenance kind, source, and at least
one structured citation. Unknown values require the explicit placeholder for
value, provenance kind, source, uncertainty, and calibration status and cannot
claim supporting citations.

## Audited preset immutability

The built-in registry contains five named parameter sets for the existing P1
core, P2 quorum, EPS, physiology, and waste/shear schemas. Before registry
construction, BioMesh verifies each source TOML against its P2A-accepted
code-owned SHA-256 and validates it through the existing frozen schema.

Audited registry entries are accepted on import only when the complete record
equals the corresponding built-in identity. Changing data and recomputing a
record hash, or relabelling another record as audited, fails closed. Built-in
values remain `CALIBRATION_REQUIRED`; exporting them does not qualify them as
calibrated biological evidence.

## Import, export, and verification

```text
python -m biomesh registry verify [--registry REGISTRY_FILE_OR_DIRECTORY]
python -m biomesh registry export --output NEW_DIRECTORY
python -m biomesh registry import REGISTRY_FILE_OR_DIRECTORY \
  --output NEW_DIRECTORY
```

Verification rechecks record hashes, code-owned audited identities, exact
model/parameter references, parameter inventories, and units. A canonical
serialize/reload comparison proves that citations and uncertainty survive the
exchange. Export and import publish one `registry.json` through a sibling
staging directory and atomic replace; an existing target is rejected. Import
does not silently modify, merge, upgrade, or assign audited status to records.

## Pre-launch compatibility and plugin boundary

```text
python -m biomesh registry preflight \
  --registry REGISTRY_FILE_OR_DIRECTORY \
  --model-id MODEL_ID --model-version MODEL_VERSION \
  --parameter-set-id PARAMETER_SET_ID \
  --parameter-set-version PARAMETER_SET_VERSION \
  --plugins none|example
```

Preflight resolves exact versions, then checks model/schema binding, the exact
parameter inventory, and every SI unit before the controlled plugin loader can
import code. Placeholder-valued parameters block preflight. Numeric
software-fixture values may retain `CALIBRATION_REQUIRED` status; preflight is
a compatibility result, not a calibration decision or biological claim.

The plugin selection must exactly equal the model requirements and still pass
the P4-WP03 API, metadata, distribution/entry-point, and code-owned review
policy. The CLI exposes only zero plugins or the already reviewed packaged
example; it does not discover or trust third-party code. A successful report
contains exact registry, model, parameter-set, and plugin-selection hashes.
It launches no simulation and changes no project or raw artifact.

P4A remediation prospectively binds the accepted fixture executor to the
complete built-in registry identity, all five exact named/versioned model and
parameter-set records, their source-document hashes, and the canonical empty
plugin-set hash. New project definitions record that selection before launch;
completed run requests and receipts repeat it exactly. This does not make the
registry executable, alter any equation, or insert identities into historical
completed runs.

## Migration and scope boundary

There is no earlier registry schema to migrate. Existing parameter TOML,
mutable campaign-state records, completed artifacts, and P4-WP02 report schemas
remain byte-compatible and unchanged. Top-level project schema version 1
remains read-only compatible; schema version 2 is required for prospective
execution provenance. Existing raw-run/report traceability continues to
originate from hash-verified project artifacts; registry identities are not
retroactively inserted into accepted runs.

P4-WP04 adds no model equation, biological value, calibration result, GUI,
background queue, priority/resource scheduler, portable project archive,
packaging, acceleration, cloud execution, or automatic plugin trust. Those are
outside this work package or remain later P4 work.
