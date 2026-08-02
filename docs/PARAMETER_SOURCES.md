# Parameter Sources

P1-WP01 defines a versioned TOML parameter-file contract. The starter file,
`parameters/p1_core_model.toml`, contains the quantities required by completed
P1 work packages. P1-WP05 adds `maximum_permitted_cell_overlap` in metres as
the acceptance threshold corresponding to `MechanicsParameters.maximum_overlap_m`.
No scientific threshold has been approved, so its value, source, uncertainty,
and status remain `CALIBRATION_REQUIRED`. The file supplies no invented
constants, citations, or calibration results.

The other P1-WP05 controls are explicit runtime configuration rather than
biological constants: domain width is an experiment-specific SI length;
maximum iterations and displacement fraction are numerical convergence
controls; and attachment mode is the categorical model choice `bottom` or
`none`. None has a module default. Scientific runs must record the selected
controls and the source and uncertainty of experiment-specific geometry.

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
