"""Inventory multiband EVI GeoTIFF stacks without modifying source data."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import math
import os
import re
import statistics
import subprocess
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable


INVENTORY_FIELDS = (
    "full_path",
    "relative_path",
    "filename",
    "year",
    "date",
    "DOY",
    "MODIS_composite_index",
    "tile_or_polygon_id",
    "start_year",
    "end_year",
    "first_date",
    "last_date",
    "band_count",
    "dtype",
    "nodata",
    "width",
    "height",
    "CRS",
    "transform",
    "pixel_size_x",
    "pixel_size_y",
    "bounds",
    "grid_offset_x",
    "grid_offset_y",
    "compression",
    "file_size_bytes",
    "minimum",
    "maximum",
    "mean",
    "valid_fraction",
    "date_count",
    "date_sequence_sha256",
    "readable",
    "error",
)


@dataclass(frozen=True)
class InventoryResult:
    row: dict[str, Any]
    dates: tuple[date, ...]
    anomalies: tuple[dict[str, str], ...]


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def as_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def band_metadata(band: dict[str, Any]) -> dict[str, Any]:
    metadata = band.get("metadata", {})
    return metadata.get("", {}) if isinstance(metadata, dict) else {}


def band_value(band: dict[str, Any], key: str, metadata_key: str) -> float | None:
    value = band.get(key)
    if value is None:
        value = band_metadata(band).get(metadata_key)
    return as_number(value)


def projected_epsg(wkt: str) -> str:
    matches = re.findall(r'ID\["EPSG",\s*(\d+)\]', wkt)
    return f"EPSG:{matches[-1]}" if matches else wkt.replace("\n", " ")


def parse_band_dates(
    bands: list[dict[str, Any]], pattern: re.Pattern[str]
) -> tuple[tuple[date, ...], list[dict[str, str]]]:
    parsed: list[date] = []
    anomalies: list[dict[str, str]] = []
    missing_descriptions: list[int] = []
    malformed_descriptions: list[str] = []
    for band in bands:
        description = str(band.get("description", ""))
        match = pattern.fullmatch(description)
        if not match:
            if not description:
                missing_descriptions.append(int(band.get("band", 0)))
            else:
                malformed_descriptions.append(
                    f"band {band.get('band')}: {description!r}"
                )
            continue
        try:
            parsed.append(
                date(
                    int(match.group("year")),
                    int(match.group("month")),
                    int(match.group("day")),
                )
            )
        except ValueError as error:
            anomalies.append(
                {
                    "severity": "error",
                    "code": "invalid_band_date",
                    "detail": f"band {band.get('band')}: {error}",
                }
            )
    if missing_descriptions:
        anomalies.append(
            {
                "severity": "error",
                "code": "missing_band_descriptions",
                "detail": (
                    f"{len(missing_descriptions)} bands have blank descriptions; "
                    f"first={missing_descriptions[0]}, last={missing_descriptions[-1]}"
                ),
            }
        )
    if malformed_descriptions:
        anomalies.append(
            {
                "severity": "error",
                "code": "unparsed_band_descriptions",
                "detail": f"{len(malformed_descriptions)} malformed; {malformed_descriptions[:3]}",
            }
        )
    return tuple(parsed), anomalies


def summarize_bands(bands: list[dict[str, Any]]) -> dict[str, Any]:
    minima = [band_value(b, "minimum", "STATISTICS_MINIMUM") for b in bands]
    maxima = [band_value(b, "maximum", "STATISTICS_MAXIMUM") for b in bands]
    means = [band_value(b, "mean", "STATISTICS_MEAN") for b in bands]
    valid_percent = [
        as_number(band_metadata(b).get("STATISTICS_VALID_PERCENT")) for b in bands
    ]
    finite_minima = [v for v in minima if v is not None]
    finite_maxima = [v for v in maxima if v is not None]
    weighted_pairs = [
        (mean, valid)
        for mean, valid in zip(means, valid_percent)
        if mean is not None and valid is not None and valid > 0
    ]
    if weighted_pairs:
        weighted_mean = sum(mean * valid for mean, valid in weighted_pairs) / sum(
            valid for _, valid in weighted_pairs
        )
    else:
        finite_means = [v for v in means if v is not None]
        weighted_mean = statistics.fmean(finite_means) if finite_means else None
    finite_valid = [v / 100.0 for v in valid_percent if v is not None]
    return {
        "minimum": min(finite_minima) if finite_minima else None,
        "maximum": max(finite_maxima) if finite_maxima else None,
        "mean": weighted_mean,
        "valid_fraction": statistics.fmean(finite_valid) if finite_valid else None,
    }


def inspect_raster(
    path: Path,
    raw_root: Path,
    gdalinfo: Path,
    filename_pattern: re.Pattern[str],
    band_pattern: re.Pattern[str],
    expected_band_count: int,
    compute_approx_stats: bool,
) -> InventoryResult:
    relative = path.relative_to(raw_root)
    base_row: dict[str, Any] = {field: "" for field in INVENTORY_FIELDS}
    base_row.update(
        {
            "full_path": str(path),
            "relative_path": str(relative),
            "filename": path.name,
            "file_size_bytes": path.stat().st_size,
            "readable": False,
        }
    )
    anomalies: list[dict[str, str]] = []
    file_match = filename_pattern.fullmatch(path.name)
    if file_match:
        base_row.update(file_match.groupdict())
        base_row["tile_or_polygon_id"] = file_match.group("tile_id")
        base_row["year"] = f"{file_match.group('start_year')}-{file_match.group('end_year')}"
    else:
        anomalies.append(
            {"severity": "error", "code": "unparsed_filename", "detail": path.name}
        )

    try:
        command = [str(gdalinfo), "-json"]
        if compute_approx_stats:
            command.append("-approx_stats")
        command.append(str(path))
        gdal_env = os.environ.copy()
        gdal_env["GDAL_PAM_ENABLED"] = "NO"
        possible_gdal_data = gdalinfo.parent.parent / "share" / "gdal"
        if possible_gdal_data.is_dir():
            gdal_env.setdefault("GDAL_DATA", str(possible_gdal_data))
        process = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=gdal_env,
        )
        info = json.loads(process.stdout)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        base_row["error"] = str(error)
        anomalies.append(
            {"severity": "error", "code": "unreadable_raster", "detail": str(error)}
        )
        return InventoryResult(base_row, (), tuple(anomalies))

    bands = info.get("bands", [])
    parsed_dates, date_anomalies = parse_band_dates(bands, band_pattern)
    anomalies.extend(date_anomalies)
    transform = info.get("geoTransform", [])
    corners = list(info.get("cornerCoordinates", {}).values())
    numeric_corners = [p for p in corners if isinstance(p, list) and len(p) == 2]
    xs = [p[0] for p in numeric_corners]
    ys = [p[1] for p in numeric_corners]
    bounds = [min(xs), min(ys), max(xs), max(ys)] if xs and ys else []
    wkt = info.get("coordinateSystem", {}).get("wkt", "")
    image_structure = info.get("metadata", {}).get("IMAGE_STRUCTURE", {})
    dtypes = sorted({str(b.get("type", "")) for b in bands})
    nodata = sorted({str(b.get("noDataValue", "")) for b in bands})
    band_summary = summarize_bands(bands)
    date_text = [item.isoformat() for item in parsed_dates]

    base_row.update(
        {
            "date": f"{date_text[0]}..{date_text[-1]}" if date_text else "",
            "DOY": "band-level; see time_index.csv",
            "MODIS_composite_index": "band-level; see time_index.csv",
            "first_date": date_text[0] if date_text else "",
            "last_date": date_text[-1] if date_text else "",
            "band_count": len(bands),
            "dtype": "|".join(dtypes),
            "nodata": "|".join(nodata),
            "width": info.get("size", ["", ""])[0],
            "height": info.get("size", ["", ""])[1],
            "CRS": projected_epsg(wkt),
            "transform": json.dumps(transform, separators=(",", ":")),
            "pixel_size_x": transform[1] if len(transform) == 6 else "",
            "pixel_size_y": abs(transform[5]) if len(transform) == 6 else "",
            "bounds": json.dumps(bounds, separators=(",", ":")),
            "grid_offset_x": transform[0] % abs(transform[1]) if len(transform) == 6 else "",
            "grid_offset_y": transform[3] % abs(transform[5]) if len(transform) == 6 else "",
            "compression": image_structure.get("COMPRESSION", ""),
            "date_count": len(parsed_dates),
            "date_sequence_sha256": hashlib.sha256(
                "\n".join(date_text).encode("utf-8")
            ).hexdigest(),
            "readable": True,
            **band_summary,
        }
    )

    if len(bands) != expected_band_count:
        anomalies.append(
            {
                "severity": "error",
                "code": "unexpected_band_count",
                "detail": f"observed={len(bands)}, expected={expected_band_count}",
            }
        )
    duplicate_dates = sorted(item.isoformat() for item, n in Counter(parsed_dates).items() if n > 1)
    if duplicate_dates:
        anomalies.append(
            {
                "severity": "error",
                "code": "duplicate_band_dates",
                "detail": ";".join(duplicate_dates),
            }
        )
    return InventoryResult(base_row, parsed_dates, tuple(anomalies))


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def create_parquet(csv_path: Path, parquet_path: Path, ogr2ogr: Path) -> None:
    if parquet_path.exists():
        parquet_path.unlink()
    env = os.environ.copy()
    possible_gdal_data = ogr2ogr.parent.parent / "share" / "gdal"
    if possible_gdal_data.is_dir():
        env.setdefault("GDAL_DATA", str(possible_gdal_data))
    subprocess.run(
        [
            str(ogr2ogr),
            "-f",
            "Parquet",
            str(parquet_path),
            str(csv_path),
            "-oo",
            "AUTODETECT_TYPE=YES",
            "-lco",
            "COMPRESSION=ZSTD",
        ],
        check=True,
        env=env,
    )


def build_time_rows(dates: tuple[date, ...]) -> list[dict[str, Any]]:
    per_year: defaultdict[int, int] = defaultdict(int)
    rows: list[dict[str, Any]] = []
    base = date(dates[0].year, 1, 1) if dates else date(2001, 1, 1)
    for band_index, timestamp in enumerate(dates, start=1):
        per_year[timestamp.year] += 1
        rows.append(
            {
                "band_index": band_index,
                "date": timestamp.isoformat(),
                "year": timestamp.year,
                "DOY": timestamp.timetuple().tm_yday,
                "MODIS_composite_index": per_year[timestamp.year],
                "days_since_base_plus_one": (timestamp - base).days + 1,
            }
        )
    return rows


def markdown_table(headers: list[str], rows: Iterable[Iterable[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(str(cell) for cell in row) + " |" for row in rows)
    return "\n".join(lines)


def fmt(value: Any, digits: int = 4) -> str:
    if value in (None, ""):
        return "NA"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def write_reports(
    project_root: Path,
    raw_root: Path,
    rows: list[dict[str, Any]],
    reference_dates: tuple[date, ...],
    anomaly_rows: list[dict[str, str]],
    expected_start_year: int,
    expected_end_year: int,
    expected_per_year: int,
) -> None:
    readable = [row for row in rows if row["readable"] is True]
    signature_counts = Counter(row["date_sequence_sha256"] for row in readable)
    crs_counts = Counter(row["CRS"] for row in readable)
    resolution_counts = Counter(
        (row["pixel_size_x"], row["pixel_size_y"]) for row in readable
    )
    transform_count = len({row["transform"] for row in readable})
    grid_offset_counts = Counter(
        (row["grid_offset_x"], row["grid_offset_y"]) for row in readable
    )
    dtype_counts = Counter(row["dtype"] for row in readable)
    nodata_counts = Counter(row["nodata"] for row in readable)
    compression_counts = Counter(row["compression"] for row in readable)
    values_min = [row["minimum"] for row in readable if row["minimum"] is not None]
    values_max = [row["maximum"] for row in readable if row["maximum"] is not None]
    valid = [row["valid_fraction"] for row in readable if row["valid_fraction"] is not None]
    dates_per_year = Counter(item.year for item in reference_dates)
    expected_years = set(range(expected_start_year, expected_end_year + 1))
    missing_years = sorted(expected_years - set(dates_per_year))
    wrong_year_counts = {
        year: count for year, count in sorted(dates_per_year.items()) if count != expected_per_year
    }
    duplicate_tiles = sorted(
        tile for tile, count in Counter(row["tile_or_polygon_id"] for row in rows).items() if count > 1
    )
    scale_conclusion = (
        "Float32 EVI is already in vegetation-index units; use scale factor 1.0."
        if dtype_counts and all("Float" in key for key in dtype_counts)
        and values_min and values_max and min(values_min) >= -1.0 and max(values_max) <= 1.0
        else "Scaling remains ambiguous and must be resolved before phenology processing."
    )
    generated = datetime.now(timezone.utc).isoformat()
    summary = f"""# EVI input inventory summary

Generated: `{generated}`

## Executive conclusion

The raw source contains **{len(rows)} GeoTIFF tile stacks**. **{len(readable)}** were readable and
**{len(rows) - len(readable)}** failed. Each normal source file is a spatial tile containing the
complete band-level time series rather than a single-date raster. The modal time sequence occurs in
**{signature_counts.most_common(1)[0][1] if signature_counts else 0} of {len(readable)}** readable tiles.

**EVI scaling decision:** {scale_conclusion}

## Required inventory questions

1. **How many files exist?** {len(rows)} GeoTIFFs (auxiliary sidecars are not inventory records).
2. **How many files per year?** Not applicable at file level: every tile spans
   {expected_start_year}–{expected_end_year}. Band-level counts are listed below.
3. **Are there 23 observations per year?** {'Yes.' if not wrong_year_counts else f'No: {wrong_year_counts}'}
4. **Are all years present?** {'Yes.' if not missing_years else f'No; missing {missing_years}.'}
5. **Actual dates?** {reference_dates[0].isoformat() if reference_dates else 'NA'} through
   {reference_dates[-1].isoformat() if reference_dates else 'NA'}; see `03_inventory/time_index.csv`.
6. **Same CRS?** {len(crs_counts) == 1}; {dict(crs_counts)}.
7. **Identical pixel sizes?** {len(resolution_counts) == 1}; {dict(resolution_counts)}.
8. **Transforms aligned?** {len(grid_offset_counts) == 1}; {transform_count} distinct tile
   transforms share {len(grid_offset_counts)} pixel-grid offset(s): {dict(grid_offset_counts)}.
9. **Extents?** The dataset is tiled/polygon-based, with one stack per tile ID.
10. **Single- or multiband?** Multiband; modal band count is
    {Counter(row['band_count'] for row in readable).most_common(1)[0][0] if readable else 'NA'}.
11. **EVI representation?** {scale_conclusion}
12. **Nodata/fill values?** {dict(nodata_counts)}.
13. **Physically plausible?** Approximate overview-sampled range is
    {fmt(min(values_min) if values_min else None)} to {fmt(max(values_max) if values_max else None)}.
14. **Duplicate dates?** {'No in the reference sequence.' if len(reference_dates) == len(set(reference_dates)) else 'Yes; see anomalies.'}
15. **Missing dates?** {'No annual count gaps detected.' if not wrong_year_counts and not missing_years else 'See anomalies.'}
16. **Duplicate spatial units?** {'None.' if not duplicate_tiles else ', '.join(duplicate_tiles)}
17. **Corrupt/unreadable rasters?** {len(rows) - len(readable)}; see the anomaly table.

## Band-level temporal coverage

{markdown_table(['Year', 'Observations'], sorted(dates_per_year.items()))}

## Storage and grid overview

- Data types: `{dict(dtype_counts)}`
- Compression: `{dict(compression_counts)}`
- Distinct temporal signatures: `{len(signature_counts)}`
- Statistics: GDAL overview-based approximate statistics, with persistent auxiliary metadata disabled
- Mean per-tile, per-band valid fraction: `{fmt(statistics.fmean(valid) if valid else None)}`
- Raw directory (read-only): `{raw_root}`

## Anomalies

Inventory recorded **{len(anomaly_rows)}** anomaly entries. See
`03_inventory/anomalies/inventory_anomalies.csv` for file-level details.

## Processing implication

Process each spatial tile independently and preserve its 575-band time order. This avoids a
continental in-memory mosaic, provides natural restart checkpoints, and permits mosaicking only
the final phenology metrics. Before production, synthetic CDTS tests must verify leap-year and
calendar semantics using `days_since_base_plus_one` from the time index.
"""
    (project_root / "00_admin" / "data_inventory_summary.md").write_text(
        summary, encoding="utf-8"
    )

    decisions = f"""# Decisions log

## {generated} — Initial EVI inventory

1. **Source structure:** {len(rows)} spatial GeoTIFF stacks; each file stores the full
   {expected_start_year}–{expected_end_year} time series as bands.
2. **Naming convention:** `EVI_Series_ID_<tile_id>_<start_year>_<end_year>.tif`.
3. **Date parser:** parse band descriptions formatted as `EVI_YYYY_MM_DD`; never infer leap-year
   dates from a fixed 365-day offset.
4. **Grid structure:** {dict(crs_counts)} at {dict(resolution_counts)}; spatially distinct tile
   transforms are retained and share {len(grid_offset_counts)} pixel-grid offset(s).
5. **EVI storage/scaling:** {scale_conclusion}
6. **Missing/duplicate data:** {len(anomaly_rows)} anomaly records; {len(signature_counts)} distinct
   temporal signatures; duplicate tile IDs: {duplicate_tiles or 'none'}.
7. **Chunking strategy:** process one source tile at a time, with smaller spatial chunks inside
   each tile if needed; checkpoint by tile and metric.
8. **Blocking problems:** {'None identified by inventory.' if not anomaly_rows else 'Review inventory_anomalies.csv before CDTS work.'}
"""
    (project_root / "00_admin" / "decisions_log.md").write_text(
        decisions, encoding="utf-8"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "02_config" / "config.yaml",
    )
    parser.add_argument("--workers", type=int, help="Override configured worker count")
    parser.add_argument("--limit", type=int, help="Inspect only the first N rasters for debugging")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    project_root = Path(config["project_root"])
    raw_root = Path(config["raw_root"])
    gdalinfo = Path(config["gdalinfo"])
    ogr2ogr = Path(config["ogr2ogr"])
    settings = config["inventory"]

    if not raw_root.is_dir():
        raise FileNotFoundError(raw_root)
    for executable in (gdalinfo, ogr2ogr):
        if not executable.is_file():
            raise FileNotFoundError(executable)

    log_path = project_root / "12_logs" / "inventory" / "inventory.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(log_path, encoding="utf-8"), logging.StreamHandler()],
    )

    extensions = {item.lower() for item in settings["extensions"]}
    paths = sorted(
        path for path in raw_root.rglob("*") if path.is_file() and path.suffix.lower() in extensions
    )
    if args.limit:
        paths = paths[: args.limit]
    if not paths:
        raise RuntimeError(f"No rasters found under {raw_root}")

    filename_pattern = re.compile(settings["filename_pattern"])
    band_pattern = re.compile(settings["band_description_pattern"])
    workers = args.workers or int(settings["workers"])
    logging.info("Inspecting %d rasters with %d workers", len(paths), workers)
    results: list[InventoryResult] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                inspect_raster,
                path,
                raw_root,
                gdalinfo,
                filename_pattern,
                band_pattern,
                int(settings["expected_band_count"]),
                bool(settings.get("compute_approx_stats", True)),
            ): path
            for path in paths
        }
        for completed, future in enumerate(as_completed(futures), start=1):
            result = future.result()
            results.append(result)
            if completed % 50 == 0 or completed == len(futures):
                logging.info("Completed %d/%d", completed, len(futures))

    results.sort(key=lambda item: item.row["relative_path"])
    rows = [result.row for result in results]
    signature_counts = Counter(row["date_sequence_sha256"] for row in rows if row["readable"] is True)
    modal_signature = signature_counts.most_common(1)[0][0] if signature_counts else ""
    reference_dates = next(
        (result.dates for result in results if result.row["date_sequence_sha256"] == modal_signature),
        (),
    )

    anomaly_rows: list[dict[str, str]] = []
    for result in results:
        for anomaly in result.anomalies:
            anomaly_rows.append(
                {"relative_path": result.row["relative_path"], **anomaly}
            )
        if result.row["readable"] is True and result.row["date_sequence_sha256"] != modal_signature:
            anomaly_rows.append(
                {
                    "relative_path": result.row["relative_path"],
                    "severity": "error",
                    "code": "non_modal_date_sequence",
                    "detail": result.row["date_sequence_sha256"],
                }
            )

    inventory_dir = project_root / "03_inventory"
    csv_path = inventory_dir / "raster_inventory.csv"
    parquet_path = inventory_dir / "raster_inventory.parquet"
    write_csv(csv_path, rows, INVENTORY_FIELDS)
    create_parquet(csv_path, parquet_path, ogr2ogr)

    time_rows = build_time_rows(reference_dates)
    write_csv(
        inventory_dir / "time_index.csv",
        time_rows,
        (
            "band_index",
            "date",
            "year",
            "DOY",
            "MODIS_composite_index",
            "days_since_base_plus_one",
        ),
    )
    grid_rows = [
        {
            "CRS": key[0],
            "pixel_size_x": key[1],
            "pixel_size_y": key[2],
            "dtype": key[3],
            "nodata": key[4],
            "compression": key[5],
            "grid_offset_x": key[6],
            "grid_offset_y": key[7],
            "raster_count": count,
        }
        for key, count in Counter(
            (
                row["CRS"],
                row["pixel_size_x"],
                row["pixel_size_y"],
                row["dtype"],
                row["nodata"],
                row["compression"],
                row["grid_offset_x"],
                row["grid_offset_y"],
            )
            for row in rows
            if row["readable"] is True
        ).items()
    ]
    write_csv(
        inventory_dir / "grid_summary.csv",
        grid_rows,
        (
            "CRS",
            "pixel_size_x",
            "pixel_size_y",
            "dtype",
            "nodata",
            "compression",
            "grid_offset_x",
            "grid_offset_y",
            "raster_count",
        ),
    )
    write_csv(
        inventory_dir / "anomalies" / "inventory_anomalies.csv",
        anomaly_rows,
        ("relative_path", "severity", "code", "detail"),
    )
    write_reports(
        project_root,
        raw_root,
        rows,
        reference_dates,
        anomaly_rows,
        int(settings["expected_start_year"]),
        int(settings["expected_end_year"]),
        int(settings["expected_observations_per_year"]),
    )
    logging.info("Inventory complete: %s", csv_path)
    logging.info("Anomalies: %d", len(anomaly_rows))
    return 1 if any(item["severity"] == "error" for item in anomaly_rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
