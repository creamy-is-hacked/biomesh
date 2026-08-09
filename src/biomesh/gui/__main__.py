"""Executable entry point for the P3-WP04 desktop shell."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtWidgets import QApplication

from biomesh import __version__
from biomesh.gui.main_window import MainWindow
from biomesh.gui.preferences import UiPreferencesStore


def build_parser() -> argparse.ArgumentParser:
    """Build the independent desktop-GUI command parser."""
    parser = argparse.ArgumentParser(
        prog="biomesh-gui",
        description="BioMesh P3-WP04 Linux desktop viewer and experiment editor.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--preferences-file",
        type=Path,
        help="override the UI-only preferences path",
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="construct and close the shell without entering the event loop",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Start the desktop GUI or perform its headless startup smoke test."""
    arguments = build_parser().parse_args(argv)
    application = QApplication.instance()
    if application is None:
        application = QApplication(["biomesh-gui"])
    application.setApplicationName("BioMesh")
    application.setOrganizationName("BioMesh")
    window = MainWindow(UiPreferencesStore(arguments.preferences_file))
    if arguments.smoke_test:
        window.show()
        application.processEvents()
        window.close()
        return 0
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
