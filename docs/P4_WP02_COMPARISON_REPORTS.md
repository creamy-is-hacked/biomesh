# P4-WP02 Comparison and Reports

P4-WP02 adds a read-only comparison and reporting boundary over the strict,
hash-verified P4-WP01 project model. It does not change project definitions,
campaign state, raw run artifacts, the P1–P3 engine or GUI, biological
parameters, calibration status, or accepted update order.

## Source metrics and units

The report registry declares 16 existing scalar columns from five canonical
raw Parquet artifacts:

- `summary.parquet`: total dry biomass (`kg`), cell and division-event counts
  (`1`), biofilm height (`m`), and biofilm roughness (`m`);
- `eps_summary.parquet`: total EPS (`kg`);
- `competition_summary.parquet`: producer cell and biomass frequencies and
  nearest-neighbor segregation fraction (`1`);
- `physiology_summary.parquet`: active, slow, dormant, dead, and detached
  biomass (`kg`); and
- `shear_summary.parquet`: surface-parallel shear stress (`Pa`) and detachment
  rate (`s^-1`).

The report layer neither converts units nor creates biological values. The
project's overall status remains `CALIBRATION_REQUIRED`; manufactured fixture
values remain software-validation inputs rather than calibration evidence.

## Raw-run traceability

Before reading any metric, `CampaignService.verified_records()` validates the
project definition hash, state/run plan, completion receipts, exact artifact
sets, byte sizes, SHA-256 values, path containment, and absence of symlinks.
Any drift fails before report publication.

Every value in a condition distribution records its project-relative raw
artifact path, artifact SHA-256 and byte size, Parquet row index and column,
run ID, deterministic seed, and replicate index. The report records the exact
project-definition hash and campaign-state generation it consumed. Reporting
does not alter campaign state or any run artifact.

## Comparison and uncertainty data

For each sweep point, metric, and stored time, report data contains the complete
available replicate distribution, mean, median, minimum, maximum, sample
variance, sample standard deviation, and a two-sided 95% Student-t confidence
interval. Every pair of sweep points at a common metric/time contains:

- the left-minus-right difference in means in the metric's SI unit;
- bias-corrected Hedges g when pooled variance is defined; and
- a two-sided 95% Welch Student-t interval for the difference in means.

These records are descriptive data for a later HTML/PDF presentation layer.
They do not make a significance decision, scientific interpretation, or
calibration claim, and no conclusion logic is embedded in the desktop GUI.

## Missing runs and single seeds

`run_coverage` contains every planned run with its current status and explicit
failure record. Available summary rows also list missing run IDs. Pending,
running, and failed runs are not rewritten as observations or silently removed
from coverage.

A campaign planned with one seed receives `SINGLE_SEED_CAMPAIGN`. Any summary
or comparison with only one observation on a side is labelled
`SINGLE_SEED_ONLY`; sample variance and confidence bounds remain `null` rather
than being invented. A campaign with missing runs receives `MISSING_RUNS`.

## Output and CLI application path

```text
python -m biomesh campaign report PROJECT_DIRECTORY CAMPAIGN_ID \
  --output NEW_REPORT_DIRECTORY
```

The new directory is atomically published and contains:

- `report_data.json`, the complete presentation-neutral data model;
- `run_coverage.csv`, including failures and missing status;
- `observations.csv`, one raw-traced scalar observation per row;
- `condition_summaries.csv`;
- `pairwise_comparisons.csv`; and
- `report_manifest.json`, which records the project/campaign identity, source
  state generation, and SHA-256/size of all five data files.

An existing output target, output inside `artifacts/`, malformed source table,
artifact drift, or publication failure is explicit and leaves no partial final
report.

## Migration and scope boundary

P4-WP01 schema version 1 is unchanged; no migration is required. Existing
projects gain a read-only report command and are not rewritten. Reports are
not imported into project state, and portable project/report archives remain
P4-WP06 work.

P4-WP02 adds no report GUI, PDF renderer, plugin API, model/parameter registry,
background queue, archive format, packaging, acceleration, cloud behavior, or
scientific mechanism. Those remain outside this work package.
