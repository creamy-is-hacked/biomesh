"""Non-Qt P3-WP04 parameter-document validation and persistence tests."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from biomesh.config import BiologicalParameter
from biomesh.gui.experiment_document import (
    PARAMETER_SCHEMAS,
    BiologicalParameterFields,
    ExperimentDocumentError,
    ExperimentEditorSession,
    detect_parameter_document,
    load_parameter_document,
    repository_parameter_path,
)


def test_repository_templates_use_existing_validated_schemas_and_provenance() -> None:
    """Every editor template is the existing provenance-complete SI document."""
    repository_root = Path.cwd()
    expected_fields = tuple(BiologicalParameter.model_fields)

    for schema in PARAMETER_SCHEMAS:
        session = ExperimentEditorSession.from_template(
            repository_root, schema.schema_id
        )
        configuration = session.document.configuration
        assert session.document.schema is schema
        assert tuple(BiologicalParameter.model_fields) == expected_fields
        assert configuration.biological_parameters
        for index, parameter in enumerate(configuration.biological_parameters):
            assert session.field_text(index, "unit") == parameter.unit
            assert session.field_text(index, "source") == parameter.source
            assert session.field_text(index, "uncertainty") == parameter.uncertainty
            assert session.field_text(index, "notes") == parameter.notes
            assert (
                session.field_text(index, "calibration_status")
                == parameter.calibration_status
            )
        assert session.validated_document is not None
        assert not session.run_eligible


@pytest.mark.parametrize(
    "schema_id", [schema.schema_id for schema in PARAMETER_SCHEMAS]
)
def test_saved_configuration_round_trips_without_semantic_change(
    tmp_path: Path, schema_id: str
) -> None:
    """Atomic TOML save reloads through the same schema with equal semantics."""
    session = ExperimentEditorSession.from_template(Path.cwd(), schema_id)
    original = session.validated_document
    target = tmp_path / f"{schema_id}-copy.toml"

    saved = session.save(target)
    reloaded = load_parameter_document(target, schema_id)

    assert original is not None
    assert saved.configuration == original.configuration
    assert reloaded.configuration == original.configuration
    detected = detect_parameter_document(target)
    assert detected.schema.schema_id == schema_id
    assert detected.configuration == original.configuration
    assert session.target_path == target.resolve()


def test_invalid_draft_is_explicitly_ineligible_and_cannot_be_saved(
    tmp_path: Path,
) -> None:
    """Invalid text never becomes validated science or a saved configuration."""
    session = ExperimentEditorSession.from_template(Path.cwd(), "p2_eps")
    session.set_field(0, BiologicalParameterFields.VALUE.value, "not-a-number")

    assert session.validated_document is None
    assert not session.run_eligible
    assert session.validation_errors == {
        (0, "value"): "value must be a finite number or CALIBRATION_REQUIRED"
    }
    target = tmp_path / "invalid.toml"
    with pytest.raises(ExperimentDocumentError, match="invalid configuration"):
        session.save(target)
    assert not target.exists()


def test_run_eligibility_requires_resolved_validated_provenance() -> None:
    """Eligibility is false until every existing schema record is resolved."""
    session = ExperimentEditorSession.from_template(Path.cwd(), "p2_eps")
    for index, _parameter in enumerate(
        session.document.configuration.biological_parameters
    ):
        session.set_field(index, "value", "0.1")
        session.set_field(index, "source", "manufactured software test input")
        session.set_field(index, "uncertainty", "synthetic exact test input")
        session.set_field(index, "calibration_status", "DERIVED")

    assert session.validated_document is not None
    assert session.run_eligible

    session.set_field(0, "value", "-1")
    assert session.validated_document is None
    assert not session.run_eligible
    assert "must be within [0, 1]" in next(iter(session.validation_errors.values()))


def test_audited_presets_remain_read_only_and_protected(tmp_path: Path) -> None:
    """Neither direct view nor editable clones may overwrite audited records."""
    repository_root = Path.cwd()
    preset_path = repository_parameter_path(repository_root, "p2_waste_shear")
    before = hashlib.sha256(preset_path.read_bytes()).hexdigest()
    preset = ExperimentEditorSession.from_audited_preset(
        repository_root, "p2_waste_shear"
    )

    assert preset.is_read_only
    with pytest.raises(ExperimentDocumentError, match="read-only"):
        preset.set_field(0, "notes", "changed")
    with pytest.raises(ExperimentDocumentError, match="read-only"):
        preset.save(tmp_path / "preset.toml")

    clone = preset.clone_as_editable()
    assert not clone.is_read_only
    with pytest.raises(ExperimentDocumentError, match="cannot be overwritten"):
        clone.save(preset_path, overwrite=True)
    assert hashlib.sha256(preset_path.read_bytes()).hexdigest() == before


def test_audited_preset_rejects_bytes_outside_accepted_revision(
    tmp_path: Path,
) -> None:
    """A preset label is never applied to unverified current file contents."""
    source = repository_parameter_path(Path.cwd(), "p2_eps")
    fake_root = tmp_path / "repository"
    fake_parameters = fake_root / "parameters"
    fake_parameters.mkdir(parents=True)
    altered = source.read_bytes() + b"\n# altered after audit\n"
    (fake_parameters / source.name).write_bytes(altered)

    with pytest.raises(ExperimentDocumentError, match="does not match P2A revision"):
        ExperimentEditorSession.from_audited_preset(fake_root, "p2_eps")


def test_existing_user_configuration_requires_explicit_overwrite(
    tmp_path: Path,
) -> None:
    """An existing non-preset file is never replaced without explicit intent."""
    session = ExperimentEditorSession.from_template(Path.cwd(), "p1_core")
    target = tmp_path / "configuration.toml"
    target.write_text("user data\n", encoding="utf-8")

    with pytest.raises(ExperimentDocumentError, match="explicit overwrite"):
        session.save(target)
    assert target.read_text(encoding="utf-8") == "user data\n"

    session.save(target, overwrite=True)
    assert load_parameter_document(target, "p1_core").configuration == (
        session.validated_document.configuration  # type: ignore[union-attr]
    )
