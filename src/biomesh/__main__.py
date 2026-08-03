"""Command-line entry point for P1-WP07 validation and reproducibility."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

from biomesh import __version__
from biomesh.reference import (
    DEFAULT_REFERENCE_PARAMETER_FILE,
    default_output_directory,
    reproduce_reference,
    run_reference,
)
from biomesh.validation import (
    validate_diffusion,
    validate_growth,
    validate_mass_balance,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the P1 command parser without executing simulation behavior."""
    parser = argparse.ArgumentParser(
        prog="biomesh",
        description="BioMesh Phase 1 core-model runner and validation tools.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="show the installed BioMesh version and exit",
    )
    commands = parser.add_subparsers(dest="command")

    run_parser = commands.add_parser(
        "run", help="write the deterministic calibration-placeholder reference"
    )
    run_parser.add_argument(
        "parameter_file",
        nargs="?",
        type=Path,
        default=DEFAULT_REFERENCE_PARAMETER_FILE,
        help="reference TOML file (default: parameters/phase1_reference.toml)",
    )
    run_parser.add_argument("--seed", type=int, help="override the recorded seed")
    run_parser.add_argument(
        "--output", type=Path, help="write to this new run directory"
    )

    validate_parser = commands.add_parser(
        "validate", help="run a P1 numerical validation case"
    )
    validations = validate_parser.add_subparsers(dest="validation")
    validations.add_parser("diffusion", help="manufactured diffusion and refinement")
    validations.add_parser("growth", help="analytical well-mixed growth")
    validations.add_parser(
        "mass-balance", help="boundary-aware full-pipeline accounting"
    )

    reproduce_parser = commands.add_parser(
        "reproduce", help="recreate and byte-compare a recorded reference run"
    )
    reproduce_parser.add_argument(
        "run_directory",
        nargs="?",
        type=Path,
        help="recorded run (default: configured reference output)",
    )
    reproduce_parser.add_argument(
        "--parameter-file",
        type=Path,
        default=DEFAULT_REFERENCE_PARAMETER_FILE,
        help="reference TOML used to locate the default run",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Execute one explicit P1 application path and report failures clearly."""
    parser = build_parser()
    arguments = parser.parse_args(argv)
    repository_root = Path.cwd()
    try:
        if arguments.command is None:
            parser.print_help()
            return 0
        if arguments.command == "run":
            paths = run_reference(
                parameter_file=arguments.parameter_file,
                output_directory=arguments.output,
                seed=arguments.seed,
                repository_root=repository_root,
            )
            print(paths.run_directory)
            return 0
        if arguments.command == "validate":
            result = _run_validation(arguments.validation, repository_root)
            print(json.dumps(result, sort_keys=True))
            return 0 if result["passed"] else 1
        if arguments.command == "reproduce":
            run_directory = arguments.run_directory
            if run_directory is None:
                run_directory = default_output_directory(
                    parameter_file=arguments.parameter_file,
                    repository_root=repository_root,
                )
            mismatches = reproduce_reference(
                run_directory=run_directory,
                repository_root=repository_root,
            )
            print(
                json.dumps(
                    {
                        "mismatch_count": len(mismatches),
                        "mismatches": [str(path) for path in mismatches],
                        "passed": not mismatches,
                    },
                    sort_keys=True,
                )
            )
            return 0 if not mismatches else 1
    except (OSError, ValueError, RuntimeError) as error:
        print(f"biomesh: error: {error}", file=sys.stderr)
        return 2
    raise AssertionError("unhandled command")


def _run_validation(
    validation: str | None, repository_root: Path
) -> dict[str, float | bool]:
    if validation == "diffusion":
        return validate_diffusion()
    if validation == "growth":
        return validate_growth()
    if validation == "mass-balance":
        with tempfile.TemporaryDirectory(prefix="biomesh-validation-") as temporary:
            return validate_mass_balance(
                output_directory=Path(temporary) / "run",
                parameter_file=repository_root / DEFAULT_REFERENCE_PARAMETER_FILE,
                repository_root=repository_root,
            )
    raise ValueError("validate requires diffusion, growth, or mass-balance")


if __name__ == "__main__":
    raise SystemExit(main())
