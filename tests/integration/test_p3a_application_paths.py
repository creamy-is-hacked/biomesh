"""P3A application paths collected by the documented integration gate."""

from __future__ import annotations

from pathlib import Path

from biomesh.p3_verification import compare_frontends, verify_checkpoint


def test_frontend_equivalence_and_checkpoint_replay(tmp_path: Path) -> None:
    output = tmp_path / "p3a-reference"
    comparison = compare_frontends(
        reference_file=Path("parameters/phase2_reference.yaml"),
        seed=42,
        output_directory=output,
    )
    assert comparison["passed"] is True
    assert comparison["mismatch_count"] == 0

    replay = verify_checkpoint(output)
    assert replay["passed"] is True
    assert replay["mismatch_count"] == 0
