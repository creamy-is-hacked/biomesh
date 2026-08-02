# Parameter Sources

M0 – Repository Bootstrap defines provenance requirements only. It contains no biological parameter
values and no inferred constants.

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
