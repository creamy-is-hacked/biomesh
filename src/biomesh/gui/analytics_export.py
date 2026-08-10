"""Deterministic atomic P3-WP06 analytics and canonical-artifact export."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import struct
import tempfile
import threading
import zlib
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any, cast

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from biomesh.application import ApplicationService
from biomesh.application_types import ApplicationError, RunSnapshot, RunStatus
from biomesh.gui.analytics import (
    ANALYTICS_PLOTS,
    ANALYTICS_SERIES,
    AnalyticsRecord,
    analytics_records,
    series_records,
)

EXPORT_SCHEMA_VERSION = 1


class AnalyticsExportCancelled(ApplicationError):
    """Raised when cancellation is accepted before atomic publication."""


@dataclass(frozen=True, slots=True)
class AnalyticsExportResult:
    """Identity of one atomically published P3-WP06 export bundle."""

    output_directory: Path
    manifest_file: Path
    files: tuple[Path, ...]


def export_analytics_bundle(
    service: ApplicationService,
    output_directory: Path,
    snapshots: tuple[RunSnapshot, ...],
    cancel_event: threading.Event,
) -> AnalyticsExportResult:
    """Publish canonical fields/tables plus exact analytics representations."""
    if not isinstance(service, ApplicationService):
        raise ApplicationError("export requires an ApplicationService")
    if not isinstance(output_directory, Path):
        raise ApplicationError("output_directory must be a Path")
    if not isinstance(cancel_event, threading.Event):
        raise ApplicationError("cancel_event must be a threading.Event")
    if service.status is not RunStatus.COMPLETED:
        raise ApplicationError("analytics export requires a completed session")
    if output_directory.exists() or output_directory.is_symlink():
        raise ApplicationError("output_directory must not already exist")
    if not output_directory.parent.is_dir():
        raise ApplicationError("output_directory parent directory must exist")
    records = analytics_records(snapshots)
    if not records:
        raise ApplicationError("analytics export requires stored metric snapshots")
    final_snapshot = max(snapshots, key=lambda item: item.step_index)
    if final_snapshot.status is not RunStatus.COMPLETED:
        raise ApplicationError("analytics export requires a completed snapshot")

    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{output_directory.name}.", dir=output_directory.parent
        )
    )
    try:
        _check_cancelled(cancel_event)
        canonical = staging / ".canonical"
        service.export(canonical)
        _check_cancelled(cancel_event)
        metadata = _read_json_object(canonical / "run_metadata.json")
        _validate_provenance(metadata, final_snapshot)
        _validate_stored_metric_equivalence(canonical, records)
        _organize_canonical_artifacts(canonical, staging, cancel_event)
        analytics_directory = staging / "analytics"
        plots_directory = staging / "plots"
        analytics_directory.mkdir()
        plots_directory.mkdir()
        _write_csv(analytics_directory / "metrics.csv", records)
        _check_cancelled(cancel_event)
        _write_parquet(analytics_directory / "metrics.parquet", records)
        for plot in ANALYTICS_PLOTS:
            _check_cancelled(cancel_event)
            _write_plot(plots_directory / f"{plot.name}.png", plot.series, records)
        _check_cancelled(cancel_event)
        manifest = _manifest_payload(staging, metadata, final_snapshot, records)
        (staging / "run_manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _check_cancelled(cancel_event)
        os.replace(staging, output_directory)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    files = tuple(
        sorted(
            path.relative_to(output_directory)
            for path in output_directory.rglob("*")
            if path.is_file()
        )
    )
    return AnalyticsExportResult(
        output_directory=output_directory,
        manifest_file=output_directory / "run_manifest.json",
        files=files,
    )


def _organize_canonical_artifacts(
    canonical: Path, staging: Path, cancel_event: threading.Event
) -> None:
    tables = staging / "tables"
    fields = staging / "fields"
    tables.mkdir()
    fields.mkdir()
    for path in sorted(canonical.glob("*.parquet"), key=lambda item: item.name):
        _check_cancelled(cancel_event)
        os.replace(path, tables / path.name)
    canonical_fields = canonical / "fields"
    for path in sorted(canonical_fields.glob("*.npz"), key=lambda item: item.name):
        _check_cancelled(cancel_event)
        os.replace(path, fields / path.name)
    os.replace(canonical / "run_metadata.json", staging / "run_metadata.json")
    shutil.rmtree(canonical)


def _write_csv(path: Path, records: tuple[AnalyticsRecord, ...]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(
            (
                "step_index",
                "time_s",
                "series",
                "label",
                "unit",
                "value",
                "source_metric",
            )
        )
        for record in records:
            writer.writerow(
                (
                    record.step_index,
                    format(record.time_s, ".17g"),
                    record.series,
                    record.label,
                    record.unit,
                    format(record.value, ".17g"),
                    record.source_metric,
                )
            )


def _validate_stored_metric_equivalence(
    canonical: Path, records: tuple[AnalyticsRecord, ...]
) -> None:
    """Fail if public snapshot values drift from corresponding raw tables."""
    summary = _parquet_rows(canonical / "summary.parquet")
    competition = _parquet_rows(canonical / "competition_summary.parquet")
    eps = _parquet_rows(canonical / "eps_summary.parquet")
    quorum = _parquet_rows(canonical / "quorum_history.parquet")
    stored_by_series: dict[str, dict[float, float]] = {
        "population_cell_count": {
            float(row["time_s"]): float(row["cell_count"]) for row in summary
        },
        "total_dry_biomass_kg": {
            float(row["time_s"]): float(row["total_dry_biomass_kg"])
            for row in summary
        },
        "producer_cell_frequency": {
            float(row["time_s"]): float(row["producer_cell_frequency"])
            for row in competition
        },
        "total_eps_kg": {
            float(row["time_s"]): float(row["total_eps_kg"]) for row in eps
        },
        "biofilm_thickness_m": {
            float(row["time_s"]): float(row["biofilm_height_m"])
            for row in summary
        },
        "biofilm_roughness_m": {
            float(row["time_s"]): float(row["biofilm_roughness_m"])
            for row in summary
        },
        "quorum_active_fraction": _quorum_fraction_by_time(quorum),
    }
    for series_name, stored in stored_by_series.items():
        for record in series_records(records, series_name):
            if record.time_s not in stored or stored[record.time_s] != record.value:
                raise ApplicationError(
                    f"analytics series {series_name!r} does not exactly match "
                    "the canonical stored application artifact"
                )


def _parquet_rows(path: Path) -> list[dict[str, Any]]:
    try:
        return cast(list[dict[str, Any]], pq.read_table(path).to_pylist())
    except (OSError, ValueError, pa.ArrowException) as error:
        raise ApplicationError(
            f"unable to read canonical table {path.name}: {error}"
        ) from error


def _quorum_fraction_by_time(rows: list[dict[str, Any]]) -> dict[float, float]:
    values: dict[float, list[float]] = {}
    for row in rows:
        values.setdefault(float(row["time_s"]), []).append(
            float(row["activation_fraction"])
        )
    return {
        time_s: sum(activation) / len(activation)
        for time_s, activation in values.items()
    }


def _write_parquet(path: Path, records: tuple[AnalyticsRecord, ...]) -> None:
    schema = pa.schema(
        (
            pa.field("step_index", pa.int64(), nullable=False),
            pa.field("time_s", pa.float64(), nullable=False),
            pa.field("series", pa.string(), nullable=False),
            pa.field("label", pa.string(), nullable=False),
            pa.field("unit", pa.string(), nullable=False),
            pa.field("value", pa.float64(), nullable=False),
            pa.field("source_metric", pa.string(), nullable=False),
        )
    )
    table = pa.Table.from_pylist(
        [
            {
                "step_index": record.step_index,
                "time_s": record.time_s,
                "series": record.series,
                "label": record.label,
                "unit": record.unit,
                "value": record.value,
                "source_metric": record.source_metric,
            }
            for record in records
        ],
        schema=schema,
    )
    pq.write_table(table, path)


def _write_plot(
    path: Path,
    series_names: tuple[str, ...],
    records: tuple[AnalyticsRecord, ...],
) -> None:
    width, height = 800, 480
    left, top, right, bottom = 64, 24, width - 24, height - 48
    pixels = bytearray(b"\xff" * (width * height * 4))
    for fraction in (0.25, 0.5, 0.75):
        x = round(left + fraction * (right - left))
        y = round(top + fraction * (bottom - top))
        _draw_line(pixels, width, height, x, top, x, bottom, (224, 228, 235, 255))
        _draw_line(pixels, width, height, left, y, right, y, (224, 228, 235, 255))
    _draw_line(pixels, width, height, left, top, left, bottom, (20, 24, 32, 255))
    _draw_line(
        pixels, width, height, left, bottom, right, bottom, (20, 24, 32, 255)
    )
    selected_by_series = {
        name: series_records(records, name) for name in series_names
    }
    all_records = tuple(
        record for name in series_names for record in selected_by_series[name]
    )
    minimum_time = min(record.time_s for record in all_records)
    maximum_time = max(record.time_s for record in all_records)
    minimum_value = min(record.value for record in all_records)
    maximum_value = max(record.value for record in all_records)
    colors = ((40, 121, 255, 255), (232, 67, 147, 255))
    for series_name in series_names:
        selected = selected_by_series[series_name]
        color = colors[series_names.index(series_name)]
        coordinates = tuple(
            (
                _scale(record.time_s, minimum_time, maximum_time, left, right),
                _scale(record.value, minimum_value, maximum_value, bottom, top),
            )
            for record in selected
        )
        for start, end in zip(coordinates, coordinates[1:], strict=False):
            _draw_line(pixels, width, height, *start, *end, color)
        for x, y in coordinates:
            _draw_point(pixels, width, height, x, y, color)
    title = next(
        item.title for item in ANALYTICS_PLOTS if item.series == series_names
    )
    _write_png(
        path,
        width,
        height,
        pixels,
        title=title,
        series=",".join(series_names),
        unit=next(
            item.unit for item in ANALYTICS_SERIES if item.name == series_names[0]
        ),
    )


def _scale(
    value: float,
    minimum: float,
    maximum: float,
    output_minimum: int,
    output_maximum: int,
) -> int:
    if minimum == maximum:
        return round((output_minimum + output_maximum) / 2)
    fraction = (value - minimum) / (maximum - minimum)
    return round(output_minimum + fraction * (output_maximum - output_minimum))


def _draw_line(
    pixels: bytearray,
    width: int,
    height: int,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    color: tuple[int, int, int, int],
) -> None:
    delta_x = abs(x1 - x0)
    step_x = 1 if x0 < x1 else -1
    delta_y = -abs(y1 - y0)
    step_y = 1 if y0 < y1 else -1
    error = delta_x + delta_y
    while True:
        _set_pixel(pixels, width, height, x0, y0, color)
        if x0 == x1 and y0 == y1:
            break
        doubled = 2 * error
        if doubled >= delta_y:
            error += delta_y
            x0 += step_x
        if doubled <= delta_x:
            error += delta_x
            y0 += step_y


def _draw_point(
    pixels: bytearray,
    width: int,
    height: int,
    center_x: int,
    center_y: int,
    color: tuple[int, int, int, int],
) -> None:
    for y in range(center_y - 3, center_y + 4):
        for x in range(center_x - 3, center_x + 4):
            if (x - center_x) ** 2 + (y - center_y) ** 2 <= 9:
                _set_pixel(pixels, width, height, x, y, color)


def _set_pixel(
    pixels: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    color: tuple[int, int, int, int],
) -> None:
    if 0 <= x < width and 0 <= y < height:
        offset = (y * width + x) * 4
        pixels[offset : offset + 4] = bytes(color)


def _write_png(
    path: Path,
    width: int,
    height: int,
    pixels: bytearray,
    *,
    title: str,
    series: str,
    unit: str,
) -> None:
    rows = b"".join(
        b"\x00" + pixels[row * width * 4 : (row + 1) * width * 4]
        for row in range(height)
    )
    contents = b"\x89PNG\r\n\x1a\n"
    contents += _png_chunk(
        b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    )
    contents += _png_chunk(b"tEXt", b"Title\x00" + title.encode("latin-1"))
    contents += _png_chunk(b"tEXt", b"Series\x00" + series.encode("latin-1"))
    contents += _png_chunk(b"tEXt", b"Unit\x00" + unit.encode("latin-1"))
    contents += _png_chunk(b"IDAT", zlib.compress(rows, level=9))
    contents += _png_chunk(b"IEND", b"")
    path.write_bytes(contents)


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)


def _manifest_payload(
    staging: Path,
    metadata: dict[str, Any],
    snapshot: RunSnapshot,
    records: tuple[AnalyticsRecord, ...],
) -> dict[str, object]:
    artifacts: list[dict[str, object]] = []
    for path in sorted(
        (item for item in staging.rglob("*") if item.is_file()),
        key=lambda item: item.relative_to(staging).as_posix(),
    ):
        relative = path.relative_to(staging).as_posix()
        artifacts.append(
            {
                "kind": _artifact_kind(relative),
                "path": relative,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "size_bytes": path.stat().st_size,
            }
        )
    return {
        "artifacts": artifacts,
        "biological_parameter_files": [
            {"label": item.label, "sha256": item.sha256}
            for item in snapshot.parameter_provenance
        ],
        "calibration_status": snapshot.calibration_status,
        "commit_hash": metadata["commit_hash"],
        "condition_id": snapshot.condition_id,
        "configuration_sha256": snapshot.configuration_sha256,
        "metric_records": len(records),
        "metric_series": [
            {
                "name": item.name,
                "source_metric": item.source_metric,
                "unit": item.unit,
            }
            for item in ANALYTICS_SERIES
        ],
        "schema_version": EXPORT_SCHEMA_VERSION,
        "seed": snapshot.seed,
        "software_versions": {
            "dependency_versions": {
                **metadata["dependency_versions"],
                "PySide6": version("PySide6"),
                "pyqtgraph": version("pyqtgraph"),
            },
            "package_version": metadata["package_version"],
            "platform": metadata["platform"],
            "python_version": metadata["python_version"],
        },
    }


def _artifact_kind(relative: str) -> str:
    if relative.startswith("plots/"):
        return "plot_png"
    if relative.startswith("fields/"):
        return "canonical_field"
    if relative.startswith("tables/"):
        return "canonical_table"
    if relative == "run_metadata.json":
        return "canonical_run_metadata"
    return "analytics_table"


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        value: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ApplicationError(
            f"unable to read canonical run metadata: {error}"
        ) from error
    if not isinstance(value, dict):
        raise ApplicationError("canonical run metadata must be a JSON object")
    return value


def _validate_provenance(metadata: dict[str, Any], snapshot: RunSnapshot) -> None:
    required = {
        "commit_hash",
        "dependency_versions",
        "package_version",
        "platform",
        "python_version",
        "seed",
    }
    if not required <= set(metadata):
        raise ApplicationError("canonical run metadata provenance is incomplete")
    if metadata["seed"] != snapshot.seed:
        raise ApplicationError("canonical run metadata seed does not match snapshot")
    if not isinstance(metadata["commit_hash"], str) or not metadata["commit_hash"]:
        raise ApplicationError("canonical run metadata commit is malformed")
    if not isinstance(metadata["dependency_versions"], dict):
        raise ApplicationError("canonical dependency versions are malformed")


def _check_cancelled(cancel_event: threading.Event) -> None:
    if cancel_event.is_set():
        raise AnalyticsExportCancelled("analytics export cancelled before publication")
