"""Run a restartable, one-tile annual CDTS phenology benchmark.

Missing EVI observations are linearly filled for numerical continuity and
assigned zero reliability weight. Raw CDTS event dates are converted from a
continuous multi-year axis to calendar-year day of year (DOY) before writing.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import logging
import platform
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from cdts._core.phenology import CurveType, fit_phenology_batch
from rasterio.windows import Window


METRICS = (
    "TRS2.sos",
    "TRS2.eos",
    "TRS5.sos",
    "TRS5.eos",
    "TRS6.sos",
    "TRS6.eos",
    "DER.sos",
    "DER.pos",
    "DER.eos",
    "UD",
    "SD",
    "DD",
    "RD",
    "Greenup",
    "Maturity",
    "Senescence",
    "Dormancy",
    "LOS",
    "POP",
    "R2",
    "RMSE",
)

DATE_METRIC_INDICES = tuple(range(17)) + (18,)
LOS_INDEX = 17
POP_INDEX = 18
FIT_METRIC_INDICES = (19, 20)
CURVE_TYPES = ("BECK", "ELMORE", "GU", "KLOS", "ZHANG", "AG", "DL")


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def parse_dates(descriptions: tuple[str | None, ...], base_year: int) -> np.ndarray:
    """Convert EVI_YYYY_MM_DD descriptions to true elapsed days from base year."""
    base = date(base_year, 1, 1)
    parsed: list[float] = []
    for band_index, description in enumerate(descriptions, start=1):
        if not description or not description.startswith("EVI_"):
            raise ValueError(f"Band {band_index} has no parseable date description")
        timestamp = date.fromisoformat(description.removeprefix("EVI_").replace("_", "-"))
        parsed.append(float((timestamp - base).days + 1))
    dates = np.asarray(parsed, dtype=np.float64)
    if np.any(np.diff(dates) <= 0):
        raise ValueError("Band dates are not strictly increasing")
    return dates


def prepare_values_and_weights(
    values: np.ndarray, eligible: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Fill gaps and return zero weights for values that were originally missing."""
    selected = np.ascontiguousarray(values[eligible], dtype=np.float64)
    weights = np.isfinite(selected).astype(np.float64)
    steps = np.arange(selected.shape[1])
    for pixel in range(selected.shape[0]):
        finite = weights[pixel] > 0
        selected[pixel] = np.interp(
            steps, steps[finite], selected[pixel, finite]
        )
    return selected, weights


def continuous_days_to_year_doy(
    values: np.ndarray, base_year: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Convert one-based continuous days to calendar year and integer DOY."""
    finite = np.isfinite(values) & (values > 0)
    years = np.full(values.shape, -1, dtype=np.int32)
    doys = np.full(values.shape, np.nan, dtype=np.float32)
    if not np.any(finite):
        return years, doys, finite

    epoch = np.datetime64(f"{base_year}-01-01", "D")
    day_offsets = np.floor(values[finite]).astype(np.int64) - 1
    event_dates = epoch + day_offsets.astype("timedelta64[D]")
    event_year_starts = event_dates.astype("datetime64[Y]")
    years[finite] = event_year_starts.astype(np.int64) + 1970
    doys[finite] = (event_dates - event_year_starts).astype(np.int64) + 1
    return years, doys, finite


def annualize_fitted(
    fitted: np.ndarray,
    base_year: int,
    start_year: int,
    end_year: int,
) -> np.ndarray:
    """Map raw sequential CDTS seasons to annual DOY and non-date values.

    Date metrics are assigned to the calendar year in which each event occurs.
    LOS, R2, and RMSE are assigned to the year of that season's POP. If CDTS
    detects more than one event for the same metric and year, the later raw
    season wins, matching CDTS 0.8.0's annualization behavior.
    """
    if fitted.ndim != 3 or fitted.shape[0] != len(METRICS):
        raise ValueError(
            f"Expected ({len(METRICS)}, pixels, seasons), got {fitted.shape}"
        )

    year_count = end_year - start_year + 1
    annual = np.full(
        (len(METRICS), fitted.shape[1], year_count), np.nan, dtype=np.float32
    )
    pixel_indices = np.arange(fitted.shape[1])
    pop_years, _, valid_pop = continuous_days_to_year_doy(
        fitted[POP_INDEX], base_year
    )

    for season_index in range(fitted.shape[2]):
        for metric_index in DATE_METRIC_INDICES:
            event_years, event_doys, valid_event = continuous_days_to_year_doy(
                fitted[metric_index, :, season_index], base_year
            )
            year_indices = event_years - start_year
            keep = valid_event & (year_indices >= 0) & (year_indices < year_count)
            annual[
                metric_index,
                pixel_indices[keep],
                year_indices[keep],
            ] = event_doys[keep]

        pop_year_indices = pop_years[:, season_index] - start_year
        keep_season = (
            valid_pop[:, season_index]
            & (pop_year_indices >= 0)
            & (pop_year_indices < year_count)
        )
        for metric_index in (LOS_INDEX, *FIT_METRIC_INDICES):
            metric_values = fitted[metric_index, :, season_index]
            keep = keep_season & np.isfinite(metric_values)
            annual[
                metric_index,
                pixel_indices[keep],
                pop_year_indices[keep],
            ] = metric_values[keep]

    return annual


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
    temporary.replace(path)


def validate_output(output_path: Path, start_year: int, end_year: int) -> dict[str, Any]:
    """Validate annual units and summarize non-date metric ranges."""
    years = list(range(start_year, end_year + 1))
    year_count = len(years)
    invalid_date_bands: list[dict[str, Any]] = []
    non_integer_date_bands: list[str] = []
    finite_date_values = 0
    date_min = np.inf
    date_max = -np.inf

    with rasterio.open(output_path) as source:
        for metric_index in DATE_METRIC_INDICES:
            for year_index, year in enumerate(years):
                band = metric_index * year_count + year_index + 1
                values = source.read(band, out_dtype="float64")
                finite = values[np.isfinite(values)]
                if finite.size == 0:
                    continue
                lower = float(finite.min())
                upper = float(finite.max())
                limit = date(year, 12, 31).timetuple().tm_yday
                finite_date_values += int(finite.size)
                date_min = min(date_min, lower)
                date_max = max(date_max, upper)
                if lower < 1 or upper > limit:
                    invalid_date_bands.append(
                        {
                            "band": source.descriptions[band - 1],
                            "minimum": lower,
                            "maximum": upper,
                            "allowed_maximum": limit,
                        }
                    )
                if not np.all(finite == np.floor(finite)):
                    non_integer_date_bands.append(source.descriptions[band - 1])

        metric_summaries: dict[str, dict[str, float | int]] = {}
        for metric_index in (LOS_INDEX, POP_INDEX, *FIT_METRIC_INDICES):
            pieces = []
            for year_index in range(year_count):
                band = metric_index * year_count + year_index + 1
                values = source.read(band, out_dtype="float64")
                pieces.append(values[np.isfinite(values)])
            finite = np.concatenate(pieces)
            metric_summaries[METRICS[metric_index]] = {
                "finite_values": int(finite.size),
                "minimum": float(finite.min()) if finite.size else np.nan,
                "median": float(np.median(finite)) if finite.size else np.nan,
                "maximum": float(finite.max()) if finite.size else np.nan,
            }

    return {
        "finite_date_values": finite_date_values,
        "date_minimum": float(date_min) if finite_date_values else np.nan,
        "date_maximum": float(date_max) if finite_date_values else np.nan,
        "invalid_date_band_count": len(invalid_date_bands),
        "invalid_date_bands": invalid_date_bands,
        "non_integer_date_band_count": len(non_integer_date_bands),
        "non_integer_date_bands": non_integer_date_bands,
        "metrics": metric_summaries,
    }


def initialize_output(
    source: rasterio.io.DatasetReader,
    output_path: Path,
    years: range,
    metadata: dict[str, str],
) -> None:
    profile = source.profile.copy()
    profile.update(
        driver="GTiff",
        count=len(METRICS) * len(years),
        dtype="float32",
        nodata=np.nan,
        compress="ZSTD",
        predictor=3,
        tiled=True,
        blockxsize=256,
        blockysize=32,
        BIGTIFF="YES",
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(output_path, "w", **profile) as destination:
        destination.update_tags(RUN_STATUS="partial", **metadata)
        band = 1
        for metric in METRICS:
            for year in years:
                destination.set_band_description(
                    band, f"{metric.replace('.', '_')}_{year}"
                )
                band += 1


def render_report(summary: dict[str, Any]) -> str:
    totals = summary["timing_seconds"]
    status = summary["status"]
    validation = summary["output_validation"]
    los = validation["metrics"]["LOS"]
    r2 = validation["metrics"]["R2"]
    rmse = validation["metrics"]["RMSE"]
    return f"""# One-tile CDTS phenology benchmark

- Status: **{status}**
- Tile: `{summary['tile']}`
- Source size: {summary['width']} × {summary['height']} pixels × {summary['band_count']} dates
- CDTS: {summary['software']['cdts']}
- Curve: {summary['parameters']['curve_type']}; Whittaker lambda {summary['parameters']['whittaker_lambda']}; minimum season {summary['parameters']['min_season_length']} days; maximum raw seasons {summary['parameters']['max_seasons']}
- Output years: {summary['start_year']}â€“{summary['end_year']}
- Date units: calendar day of year (DOY; 1â€“365 or 366)
- Threads: {summary['parameters']['n_jobs']}
- Row block: {summary['parameters']['block_rows']}
- Eligible pixels: {summary['eligible_pixels']}
- Completed row blocks: {summary['completed_blocks']} / {summary['total_blocks']}
- Read time: {totals['read']:.2f} s
- Gap-fill/preparation time: {totals['prepare']:.2f} s
- CDTS compute time: {totals['compute']:.2f} s
- GeoTIFF write time: {totals['write']:.2f} s
- End-to-end elapsed time: {totals['wall']:.2f} s
- Throughput: {summary['throughput_eligible_pixels_per_second']:.2f} eligible pixels s⁻¹
- Output: `{summary['output']}`

## Annual-output validation

- Finite date values checked: {validation['finite_date_values']:,}
- Observed date range: {validation['date_minimum']:.0f}-{validation['date_maximum']:.0f} DOY
- Date bands outside their calendar-year range: {validation['invalid_date_band_count']}
- Date bands containing non-integer DOY: {validation['non_integer_date_band_count']}
- LOS: minimum {los['minimum']:.2f}, median {los['median']:.2f}, maximum {los['maximum']:.2f} days
- R2: minimum {r2['minimum']:.3f}, median {r2['median']:.3f}, maximum {r2['maximum']:.3f}
- RMSE: minimum {rmse['minimum']:.4f}, median {rmse['median']:.4f}, maximum {rmse['maximum']:.4f} EVI

LOS values above 366 days and strongly negative R2 values are retained as transparent
QC candidates; they are not silently clipped or converted.

## Interpretation limits

This run is a performance and engineering test, not a release candidate. CDTS 0.8.0
correctly evaluates `min_season_length=45` in elapsed calendar days. Missing values are
linearly filled only for numerical continuity and receive zero reliability weight through
the `weights_array` interface. Date metrics are assigned to their event calendar year and
written as leap-year-aware integer DOY. LOS remains a duration in days. R2 and RMSE retain
their native dimensionless and EVI units and are assigned by the season's POP year. When
multiple raw seasons contribute the same metric in one year, the later detected season
wins, matching CDTS 0.8.0 annualization behavior. Multi-season sensitivity remains required
before production.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "02_config" / "config.yaml",
    )
    parser.add_argument("--tile", help="Source filename; defaults to configured benchmark tile")
    parser.add_argument(
        "--curve-type",
        type=str.upper,
        choices=CURVE_TYPES,
        help="CDTS curve model; defaults to the configured curve_type",
    )
    parser.add_argument("--block-rows", type=int)
    parser.add_argument("--n-jobs", type=int)
    parser.add_argument("--max-blocks", type=int, help="Stop after N new blocks for a probe")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    project_root = Path(config["project_root"])
    raw_root = Path(config["raw_root"])
    settings = config["pilot_benchmark"]
    tile_name = args.tile or settings["tile"]
    source_path = raw_root / tile_name
    if not source_path.is_file():
        raise FileNotFoundError(source_path)

    block_rows = args.block_rows or int(settings["block_rows"])
    n_jobs = args.n_jobs or int(settings["n_jobs"])
    max_seasons = int(settings["max_seasons"])
    curve_type = (args.curve_type or settings["curve_type"]).upper()
    if curve_type not in CURVE_TYPES:
        raise ValueError(f"Unsupported curve type: {curve_type}")
    start_year = int(config["inventory"]["expected_start_year"])
    end_year = int(config["inventory"]["expected_end_year"])
    years = range(start_year, end_year + 1)
    lambda_label = f"{float(settings['whittaker_lambda']):g}".replace(".", "p")
    run_id = f"{source_path.stem}_{curve_type}_W{lambda_label}_S{max_seasons}"
    output_path = project_root / "04_intermediate" / "pilot" / f"{run_id}.tif"
    checkpoint_path = project_root / "04_intermediate" / "checkpoints" / f"{run_id}.json"
    summary_path = project_root / "06_qc" / "reports" / f"{run_id}_benchmark.json"
    report_path = project_root / "06_qc" / "reports" / f"{run_id}_benchmark.md"
    log_path = project_root / "12_logs" / "pilot" / f"{run_id}.log"
    raster_sidecars = (
        Path(f"{output_path}.aux.xml"),
        Path(f"{output_path}.ovr"),
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(log_path, encoding="utf-8"), logging.StreamHandler()],
    )

    if args.overwrite:
        for path in (
            output_path,
            *raster_sidecars,
            checkpoint_path,
            summary_path,
            report_path,
        ):
            if path.exists():
                path.unlink()
    elif output_path.exists() != checkpoint_path.exists():
        raise RuntimeError("Output/checkpoint mismatch; use --overwrite to restart")

    started = time.perf_counter()
    with rasterio.open(source_path) as source:
        dates = parse_dates(source.descriptions, 2001)
        if source.count != dates.size:
            raise RuntimeError("Raster band count and parsed date count differ")
        total_blocks = (source.height + block_rows - 1) // block_rows
        metadata = {
            "CDTS_VERSION": importlib.metadata.version("cdts"),
            "CURVE_TYPE": curve_type,
            "DATE_AXIS": "calendar day of year, 1-365/366",
            "ANNUAL_ASSIGNMENT": (
                "date metrics by event year; LOS/R2/RMSE by POP year; later season wins"
            ),
            "BENCHMARK_ONLY": "true",
            "GAP_FILL": "linear; interpolated values assigned reliability weight 0",
            "MIN_SEASON_LENGTH": str(settings["min_season_length"]),
        }
        if not output_path.exists():
            initialize_output(source, output_path, years, metadata)
            checkpoint: dict[str, Any] = {
                "run_id": run_id,
                "completed_block_starts": [],
                "blocks": [],
                "eligible_pixels": 0,
                "timing_seconds": {"read": 0.0, "prepare": 0.0, "compute": 0.0, "write": 0.0},
                "created_utc": datetime.now(timezone.utc).isoformat(),
            }
            write_json(checkpoint_path, checkpoint)
        else:
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            if "wall_seconds" not in checkpoint:
                previous_summary = (
                    json.loads(summary_path.read_text(encoding="utf-8"))
                    if summary_path.exists()
                    else {}
                )
                checkpoint["wall_seconds"] = previous_summary.get(
                    "timing_seconds", {}
                ).get("wall", 0.0)

        completed = set(int(item) for item in checkpoint["completed_block_starts"])
        new_blocks = 0
        with rasterio.open(output_path, "r+") as destination:
            for row_start in range(0, source.height, block_rows):
                if row_start in completed:
                    continue
                row_count = min(block_rows, source.height - row_start)
                window = Window(0, row_start, source.width, row_count)
                block_record: dict[str, Any] = {"row_start": row_start, "row_count": row_count}

                tick = time.perf_counter()
                cube = source.read(window=window, out_dtype="float64")
                cube[~np.isfinite(cube)] = np.nan
                block_record["read_seconds"] = time.perf_counter() - tick

                tick = time.perf_counter()
                values = np.ascontiguousarray(cube.reshape(source.count, -1).T)
                valid_counts = np.isfinite(values).sum(axis=1)
                eligible = valid_counts >= int(settings["minimum_valid_observations"])
                filled, reliability = prepare_values_and_weights(values, eligible)
                block_record["eligible_pixels"] = int(eligible.sum())
                block_record["prepare_seconds"] = time.perf_counter() - tick

                tick = time.perf_counter()
                fitted = fit_phenology_batch(
                    values_array=filled,
                    dates_array=dates,
                    curve_type=int(getattr(CurveType, curve_type)),
                    extraction_method=0,
                    max_seasons=max_seasons,
                    whittaker_lambda=float(settings["whittaker_lambda"]),
                    apply_whittaker=bool(settings["apply_whittaker"]),
                    apply_hants=bool(settings["apply_hants"]),
                    min_season_length=int(settings["min_season_length"]),
                    min_amplitude=float(settings["min_amplitude"]),
                    min_pixel_amplitude=float(settings["min_pixel_amplitude"]),
                    n_jobs=n_jobs,
                    weights_array=reliability,
                    season_retry=True,
                )
                block_record["compute_seconds"] = time.perf_counter() - tick

                tick = time.perf_counter()
                annual = annualize_fitted(
                    fitted,
                    base_year=start_year,
                    start_year=start_year,
                    end_year=end_year,
                )
                flat_output = np.full(
                    (len(METRICS) * len(years), values.shape[0]),
                    np.nan,
                    dtype=np.float32,
                )
                flat_output[:, eligible] = annual.transpose(0, 2, 1).reshape(
                    len(METRICS) * len(years), -1
                )
                output_block = flat_output.reshape(
                    len(METRICS) * len(years), row_count, source.width
                )
                destination.write(output_block, window=window)
                block_record["write_seconds"] = time.perf_counter() - tick
                block_record["finite_output_values"] = int(np.isfinite(annual).sum())

                checkpoint["completed_block_starts"].append(row_start)
                checkpoint["blocks"].append(block_record)
                checkpoint["eligible_pixels"] += block_record["eligible_pixels"]
                for key in ("read", "prepare", "compute", "write"):
                    checkpoint["timing_seconds"][key] += block_record[f"{key}_seconds"]
                write_json(checkpoint_path, checkpoint)
                logging.info(
                    "Block %d/%d rows %d:%d eligible=%d compute=%.2fs",
                    len(checkpoint["completed_block_starts"]),
                    total_blocks,
                    row_start,
                    row_start + row_count,
                    block_record["eligible_pixels"],
                    block_record["compute_seconds"],
                )
                new_blocks += 1
                if args.max_blocks and new_blocks >= args.max_blocks:
                    break

            is_complete = len(checkpoint["completed_block_starts"]) == total_blocks
            destination.update_tags(RUN_STATUS="complete" if is_complete else "partial")

    checkpoint["wall_seconds"] = checkpoint.get("wall_seconds", 0.0) + (
        time.perf_counter() - started
    )
    write_json(checkpoint_path, checkpoint)
    timing = {**checkpoint["timing_seconds"], "wall": checkpoint["wall_seconds"]}
    compute = timing["compute"]
    output_validation = validate_output(output_path, start_year, end_year)
    summary = {
        "status": "complete" if is_complete else "partial",
        "tile": tile_name,
        "output": str(output_path.relative_to(project_root)),
        "width": source.width,
        "height": source.height,
        "band_count": source.count,
        "start_year": start_year,
        "end_year": end_year,
        "total_blocks": total_blocks,
        "completed_blocks": len(checkpoint["completed_block_starts"]),
        "eligible_pixels": checkpoint["eligible_pixels"],
        "throughput_eligible_pixels_per_second": checkpoint["eligible_pixels"] / compute if compute else 0,
        "timing_seconds": timing,
        "output_validation": output_validation,
        "parameters": {
            **settings,
            "curve_type": curve_type,
            "block_rows": block_rows,
            "n_jobs": n_jobs,
        },
        "software": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "cdts": importlib.metadata.version("cdts"),
            "numpy": np.__version__,
            "rasterio": rasterio.__version__,
        },
        "finished_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(summary_path, summary)
    report_path.write_text(render_report(summary), encoding="utf-8")
    logging.info("Benchmark status=%s wall=%.2fs output=%s", summary["status"], timing["wall"], output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
