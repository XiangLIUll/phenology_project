"""Run a restartable, one-tile CDTS phenology performance benchmark.

This benchmark intentionally writes raw sequential-season outputs. It is not a
release product: missing EVI observations are linearly filled so CDTS 0.6.0 can
fit them, and min_season_length is zero because the installed build rejected all
tested real curves when that filter was set to 45 days.
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
)


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


def fill_linear(values: np.ndarray, eligible: np.ndarray) -> np.ndarray:
    """Linearly fill all temporal gaps for eligible pixels (benchmark only)."""
    selected = np.ascontiguousarray(values[eligible], dtype=np.float64)
    steps = np.arange(selected.shape[1])
    for pixel in range(selected.shape[0]):
        finite = np.isfinite(selected[pixel])
        selected[pixel] = np.interp(
            steps, steps[finite], selected[pixel, finite]
        )
    return selected


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
    temporary.replace(path)


def initialize_output(
    source: rasterio.io.DatasetReader,
    output_path: Path,
    max_seasons: int,
    metadata: dict[str, str],
) -> None:
    profile = source.profile.copy()
    profile.update(
        driver="GTiff",
        count=len(METRICS) * max_seasons,
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
            for season in range(1, max_seasons + 1):
                destination.set_band_description(
                    band, f"{metric.replace('.', '_')}_season_{season:02d}"
                )
                band += 1


def render_report(summary: dict[str, Any]) -> str:
    totals = summary["timing_seconds"]
    status = summary["status"]
    return f"""# One-tile CDTS phenology benchmark

- Status: **{status}**
- Tile: `{summary['tile']}`
- Source size: {summary['width']} × {summary['height']} pixels × {summary['band_count']} dates
- CDTS: {summary['software']['cdts']}
- Curve: BECK; Whittaker lambda 5; maximum seasons 25
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

## Interpretation limits

This run is a performance and engineering test, not a release candidate. CDTS 0.6.0
returned no phenology for sampled real curves containing missing observations, so the
benchmark linearly fills all gaps, including long winter gaps. The installed build also
returned no metrics for the tested real curves when `min_season_length=45`; this benchmark
therefore uses zero for that filter. Raw sequential seasons are written as continuous day
numbers from 2001-01-01. Leap-year and annual-assignment validation remain required.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "02_config" / "config.yaml",
    )
    parser.add_argument("--tile", help="Source filename; defaults to configured benchmark tile")
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
    run_id = f"{source_path.stem}_BECK_W5_S{max_seasons}"
    output_path = project_root / "04_intermediate" / "pilot" / f"{run_id}.tif"
    checkpoint_path = project_root / "04_intermediate" / "checkpoints" / f"{run_id}.json"
    summary_path = project_root / "06_qc" / "reports" / f"{run_id}_benchmark.json"
    report_path = project_root / "06_qc" / "reports" / f"{run_id}_benchmark.md"
    log_path = project_root / "12_logs" / "pilot" / f"{run_id}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(log_path, encoding="utf-8"), logging.StreamHandler()],
    )

    if args.overwrite:
        for path in (output_path, checkpoint_path, summary_path, report_path):
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
            "CURVE_TYPE": "BECK",
            "DATE_AXIS": "true elapsed days since 2001-01-01, one-based",
            "BENCHMARK_ONLY": "true",
            "GAP_FILL": "linear, including leading and trailing gaps",
            "MIN_SEASON_LENGTH": str(settings["min_season_length"]),
        }
        if not output_path.exists():
            initialize_output(source, output_path, max_seasons, metadata)
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
                filled = fill_linear(values, eligible)
                block_record["eligible_pixels"] = int(eligible.sum())
                block_record["prepare_seconds"] = time.perf_counter() - tick

                tick = time.perf_counter()
                fitted = fit_phenology_batch(
                    values_array=filled,
                    dates_array=dates,
                    curve_type=int(getattr(CurveType, settings["curve_type"])),
                    extraction_method=0,
                    max_seasons=max_seasons,
                    whittaker_lambda=float(settings["whittaker_lambda"]),
                    apply_whittaker=bool(settings["apply_whittaker"]),
                    apply_hants=bool(settings["apply_hants"]),
                    min_season_length=int(settings["min_season_length"]),
                    min_amplitude=float(settings["min_amplitude"]),
                    min_pixel_amplitude=float(settings["min_pixel_amplitude"]),
                    n_jobs=n_jobs,
                )
                block_record["compute_seconds"] = time.perf_counter() - tick

                tick = time.perf_counter()
                flat_output = np.full(
                    (len(METRICS) * max_seasons, values.shape[0]), np.nan, dtype=np.float32
                )
                flat_output[:, eligible] = fitted.transpose(0, 2, 1).reshape(
                    len(METRICS) * max_seasons, -1
                )
                output_block = flat_output.reshape(
                    len(METRICS) * max_seasons, row_count, source.width
                )
                destination.write(output_block, window=window)
                block_record["write_seconds"] = time.perf_counter() - tick
                block_record["finite_output_values"] = int(np.isfinite(fitted).sum())

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
    summary = {
        "status": "complete" if is_complete else "partial",
        "tile": tile_name,
        "output": str(output_path.relative_to(project_root)),
        "width": source.width,
        "height": source.height,
        "band_count": source.count,
        "total_blocks": total_blocks,
        "completed_blocks": len(checkpoint["completed_block_starts"]),
        "eligible_pixels": checkpoint["eligible_pixels"],
        "throughput_eligible_pixels_per_second": checkpoint["eligible_pixels"] / compute if compute else 0,
        "timing_seconds": timing,
        "parameters": {**settings, "block_rows": block_rows, "n_jobs": n_jobs},
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
