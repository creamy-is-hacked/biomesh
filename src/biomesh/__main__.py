"""Command-line entry point for BioMesh."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from biomesh import __version__


def build_parser() -> argparse.ArgumentParser:
    """Build the M0 – Repository Bootstrap package-discovery parser."""
    parser = argparse.ArgumentParser(
        prog="biomesh",
        description="BioMesh biofilm simulator (M0 – Repository Bootstrap).",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="show the installed BioMesh version and exit",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface without executing a simulation."""
    build_parser().parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
