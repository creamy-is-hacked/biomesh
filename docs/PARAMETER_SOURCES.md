# Parameter Sources

P1-WP01 defines a versioned TOML parameter-file contract. The starter file,
`parameters/p1_core_model.toml`, contains the quantities required by completed
P1 work packages. P1A adds the previously omitted `cell_radius` capsule
quantity as `CALIBRATION_REQUIRED`. P1-WP05 adds
`maximum_permitted_cell_overlap` in metres as
the acceptance threshold corresponding to `MechanicsParameters.maximum_overlap_m`.
No scientific threshold has been approved, so its value, source, uncertainty,
and status remain `CALIBRATION_REQUIRED`. The file supplies no invented
constants, citations, or calibration results.

The isolated `parameters/p2_quorum_signal.toml` manifest adds
`effective_quorum_signal_diffusivity` in `m^2 s^-1`,
`quorum_signal_top_bulk_concentration` and
`quorum_activation_half_saturation_constant` in `mol m^-3`,
`quorum_signal_degradation_rate` in `s^-1`, basal and induced whole-cell
production rates in `mol s^-1`, and the dimensionless
`quorum_hill_coefficient`. Every value, source, uncertainty, and calibration
status remains `CALIBRATION_REQUIRED`. An induced rate of zero is the explicit
configuration that disables positive feedback; the software does not silently
select it.

The isolated `parameters/p2_eps_model.toml` manifest adds the dimensionless
`maximum_eps_allocation_fraction` and the
`eps_cohesion_sensitivity` and `eps_attachment_strength_sensitivity` values in
`m^3 kg^-1`. The sensitivities convert local EPS density in `kg m^-3` to
dimensionless relative-strength multipliers. All three values, sources,
uncertainties, and calibration statuses remain `CALIBRATION_REQUIRED`; the
software supplies no biological defaults.

P2-WP03 adds no numeric biological parameter. Producer and nonproducer strain
identities are explicit categorical experiment configuration. Frequencies,
per-capita dry-biomass change rates in `s^-1`, nearest-neighbour segregation,
and local matrix modifiers are derived from existing state. Competition
continues to use the P1 metabolism parameters and the P2-WP01/P2-WP02 quorum
and EPS parameters, all of which retain their recorded provenance and
calibration status.

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

The P1 schema continues to require the complete P1 biological-parameter
inventory. The separate P2-WP01 schema requires exactly the seven quorum
records, and the P2-WP02 schema requires exactly the three EPS records. All
reuse the same provenance fields, validate canonical SI units, and reject
nonphysical numeric domains before values reach component constructors.

## File contract

`schema_version` is currently `1`. Each `[[biological_parameters]]` record
must include `name`, `value`, `unit`, `source`, `uncertainty`, `notes`, and
`calibration_status`. Unknown values require `CALIBRATION_REQUIRED` for the
value, source, uncertainty, and calibration status. Numeric values require a
non-placeholder source. Units are recorded in SI form and parameter names may
not be duplicated.
