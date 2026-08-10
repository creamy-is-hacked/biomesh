"""Command-line entry point for P1-WP07 validation and reproducibility."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

from biomesh import __version__
from biomesh.p2_campaign import report_campaign, run_fixture_command, validate_all
from biomesh.p3_verification import compare_frontends, verify_checkpoint
from biomesh.project_campaign import CampaignService, create_project
from biomesh.reference import (
    DEFAULT_REFERENCE_PARAMETER_FILE,
    default_output_directory,
    reproduce_reference,
    run_reference,
)
from biomesh.runtime_resources import runtime_root
from biomesh.validation import (
    validate_diffusion,
    validate_growth,
    validate_mass_balance,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the P1 command parser without executing simulation behavior."""
    parser = argparse.ArgumentParser(
        prog="biomesh",
        description=(
            "BioMesh Phase 1 core-model runner, validation, P2 campaign, "
            "P3 verification, and P4 project tools."
        ),
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
    validations.add_parser("all", help="validate P1 checks and P2 fixture contracts")

    experiment_parser = commands.add_parser(
        "experiment", help="run one manufactured P2 software-validation fixture"
    )
    experiment_parser.add_argument("fixture_file", type=Path)
    experiment_parser.add_argument("--output", type=Path)

    sweep_parser = commands.add_parser(
        "sweep", help="run one manufactured P2 software-validation sweep"
    )
    sweep_parser.add_argument("fixture_file", type=Path)
    sweep_parser.add_argument("--output", type=Path)

    report_parser = commands.add_parser(
        "report", help="validate a P2 campaign and write its report plot"
    )
    report_parser.add_argument("output_directory", type=Path)

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

    compare_parser = commands.add_parser(
        "compare-frontends",
        help="byte-compare CLI and P3 application artifacts for one reference",
    )
    compare_parser.add_argument("reference_file", type=Path)
    compare_parser.add_argument("--seed", required=True, type=int)
    compare_parser.add_argument("--output", type=Path)

    checkpoint_parser = commands.add_parser(
        "verify-checkpoint",
        help="replay and byte-verify a P3 frontend-comparison checkpoint",
    )
    checkpoint_parser.add_argument("run_directory", type=Path)

    project_parser = commands.add_parser(
        "project", help="create a versioned local P4 research project"
    )
    project_commands = project_parser.add_subparsers(dest="project_command")
    project_create = project_commands.add_parser(
        "create", help="create a project from a strict JSON definition"
    )
    project_create.add_argument("definition_file", type=Path)
    project_create.add_argument("project_directory", type=Path)

    campaign_parser = commands.add_parser(
        "campaign", help="inspect, resume, or retry a P4 project campaign"
    )
    campaign_commands = campaign_parser.add_subparsers(dest="campaign_command")
    for operation in ("status", "resume", "retry"):
        operation_parser = campaign_commands.add_parser(operation)
        operation_parser.add_argument("project_directory", type=Path)
        operation_parser.add_argument("campaign_id")
        if operation == "retry":
            operation_parser.add_argument(
                "--run-id",
                action="append",
                dest="run_ids",
                help="retry one failed run ID; repeat to select multiple runs",
            )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Execute one explicit P1 application path and report failures clearly."""
    parser = build_parser()
    command_line = list(sys.argv[1:] if argv is None else argv)
    if command_line == ["help"]:
        parser.print_help()
        return 0
    arguments = parser.parse_args(command_line)
    working_directory = Path.cwd().resolve()
    repository_root = runtime_root(working_directory)
    try:
        if arguments.command is None:
            parser.print_help()
            return 0
        if arguments.command == "run":
            parameter_file = _resolve_runtime_path(
                arguments.parameter_file, repository_root
            )
            output = arguments.output
            if output is None and repository_root != working_directory:
                output = working_directory / "outputs" / "p1-wp07-reference-seed-42"
            paths = run_reference(
                parameter_file=parameter_file,
                output_directory=output,
                seed=arguments.seed,
                repository_root=repository_root,
            )
            print(paths.run_directory)
            return 0
        if arguments.command == "validate":
            if arguments.validation == "all":
                all_result = validate_all(repository_root)
                print(json.dumps(all_result, sort_keys=True))
                return 0
            result = _run_validation(arguments.validation, repository_root)
            print(json.dumps(result, sort_keys=True))
            return 0 if result["passed"] else 1
        if arguments.command == "reproduce":
            run_directory = arguments.run_directory
            if run_directory is None:
                parameter_file = _resolve_runtime_path(
                    arguments.parameter_file, repository_root
                )
                run_directory = default_output_directory(
                    parameter_file=parameter_file,
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
        if arguments.command in {"experiment", "sweep"}:
            fixture_file = _resolve_runtime_path(
                arguments.fixture_file, repository_root
            )
            output = arguments.output
            if output is None:
                output = working_directory / "outputs" / (
                    f"{fixture_file.stem}-{arguments.command}"
                )
            fixture_output = run_fixture_command(
                fixture_file=fixture_file,
                output_directory=output,
                expected_kind=arguments.command,
            )
            print(fixture_output)
            return 0
        if arguments.command == "report":
            print(report_campaign(arguments.output_directory))
            return 0
        if arguments.command == "compare-frontends":
            reference_file = _resolve_runtime_path(
                arguments.reference_file, repository_root
            )
            output = arguments.output
            if output is None:
                output = working_directory / "outputs" / (
                    f"p3a-reference-seed-{arguments.seed}"
                )
            comparison_result = compare_frontends(
                reference_file=reference_file,
                seed=arguments.seed,
                output_directory=output,
            )
            print(json.dumps(comparison_result, sort_keys=True))
            return 0
        if arguments.command == "verify-checkpoint":
            checkpoint_result = verify_checkpoint(arguments.run_directory)
            print(json.dumps(checkpoint_result, sort_keys=True))
            return 0
        if arguments.command == "project":
            if arguments.project_command != "create":
                raise ValueError("project requires create")
            created = create_project(
                arguments.definition_file, arguments.project_directory
            )
            print(json.dumps({"project_directory": str(created)}, sort_keys=True))
            return 0
        if arguments.command == "campaign":
            if arguments.campaign_command is None:
                raise ValueError("campaign requires status, resume, or retry")
            service = CampaignService(arguments.project_directory)
            if arguments.campaign_command == "status":
                status = service.status(arguments.campaign_id)
            elif arguments.campaign_command == "resume":
                status = service.resume(arguments.campaign_id)
            elif arguments.campaign_command == "retry":
                status = service.retry(arguments.campaign_id, arguments.run_ids)
            else:
                raise AssertionError("unhandled campaign command")
            print(json.dumps(status.as_dict(), sort_keys=True))
            return 1 if status.failed and arguments.campaign_command != "status" else 0
    except (OSError, ValueError, RuntimeError) as error:
        print(f"biomesh: error: {error}", file=sys.stderr)
        return 2
    raise AssertionError("unhandled command")


def _resolve_runtime_path(path: Path, repository_root: Path) -> Path:
    """Resolve packaged defaults while preserving explicit caller paths."""
    if path.is_absolute() or path.exists():
        return path
    packaged_candidate = repository_root / path
    return packaged_candidate if packaged_candidate.exists() else path


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
