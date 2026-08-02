# Parameter Sources

P1-WP01 defines a versioned TOML parameter-file contract. P1-WP02 extends the
starter file, `parameters/p1_core_model.toml`, with effective carbon and
oxygen diffusivities plus the two top-boundary bulk concentrations. The file
contains only quantities required by the implemented P1 equations and marks
every value, source, and uncertainty as
`CALIBRATION_REQUIRED`. It supplies no biological constants, citations, or
calibration results.

## Required parameter record

| Field | Required content |
| --- | --- |
| Name | Stable parameter name |
| Value | Numeric value or `CALIBRATION_REQUIRED` |
| Unit | SI unit used internally |
| Source | Citation, dataset, or `CALIBRATION_REQUIRED` |
| Uncertainty | Quantified uncertainty or documented unknown |
| Notes | Context, transformations, and applicability |
| Calibration status | Measured, derived, calibrated, or calibration required |

Every future biological parameter must include all fields. Unknown values must
remain explicit rather than being silently defaulted.

## File contract

`schema_version` is currently `1`. Each `[[biological_parameters]]` record
must include `name`, `value`, `unit`, `source`, `uncertainty`, `notes`, and
`calibration_status`. Unknown values require `CALIBRATION_REQUIRED` for the
value, source, uncertainty, and calibration status. Numeric values require a
non-placeholder source. Units are recorded in SI form and parameter names may
not be duplicated.
