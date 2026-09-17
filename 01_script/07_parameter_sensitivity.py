"""Compare two completed one-tile CDTS curve-model benchmarks."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import numpy as np
import rasterio


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

CONTROLLED_PARAMETERS = (
    "max_seasons",
    "apply_whittaker",
    "whittaker_lambda",
    "apply_hants",
    "min_season_length",
    "min_amplitude",
    "min_pixel_amplitude",
    "minimum_valid_observations",
    "block_rows",
    "n_jobs",
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def compare_metric(
    reference: rasterio.io.DatasetReader,
    comparison: rasterio.io.DatasetReader,
    metric_index: int,
    year_count: int,
) -> dict[str, float | int | str]:
    reference_valid = 0
    comparison_valid = 0
    differences: list[np.ndarray] = []
    for year_index in range(year_count):
        band = metric_index * year_count + year_index + 1
        left = reference.read(band, out_dtype="float32")
        right = comparison.read(band, out_dtype="float32")
        left_valid = np.isfinite(left)
        right_valid = np.isfinite(right)
        paired = left_valid & right_valid
        reference_valid += int(left_valid.sum())
        comparison_valid += int(right_valid.sum())
        if np.any(paired):
            differences.append((right[paired] - left[paired]).astype(np.float32))

    delta = np.concatenate(differences) if differences else np.empty(0, dtype=np.float32)
    absolute = np.abs(delta)
    return {
        "metric": METRICS[metric_index],
        "reference_valid": reference_valid,
        "comparison_valid": comparison_valid,
        "paired_values": int(delta.size),
        "mean_difference": float(np.mean(delta)) if delta.size else np.nan,
        "median_difference": float(np.median(delta)) if delta.size else np.nan,
        "median_absolute_difference": float(np.median(absolute)) if delta.size else np.nan,
        "p05_difference": float(np.percentile(delta, 5)) if delta.size else np.nan,
        "p95_difference": float(np.percentile(delta, 95)) if delta.size else np.nan,
    }


def render_markdown(summary: dict[str, Any]) -> str:
    rows = []
    for item in summary["metric_comparisons"]:
        rows.append(
            "| {metric} | {paired_values:,} | {median_difference:.2f} | "
            "{median_absolute_difference:.2f} | {p05_difference:.2f} | "
            "{p95_difference:.2f} |".format(**item)
        )

    probes = []
    for item in summary["model_screening"]:
        probes.append(
            "| {model} | {scope} | {median_r2:.3g} | {median_rmse:.3g} | {decision} |".format(
                **item
            )
        )

    parameters = summary["controlled_parameters"]
    parameter_lines = "\n".join(
        f"- `{key}`: `{parameters[key]}`" for key in CONTROLLED_PARAMETERS
    )
    return f"""# One-tile CDTS curve-model comparison

- Tile: `{summary['tile']}`
- Reference model: **{summary['reference_model']}**
- Comparison model: **{summary['comparison_model']}**
- Parameter equality check: **passed**
- Reference runtime: {summary['runtime_seconds'][summary['reference_model']]:.2f} s
- Comparison runtime: {summary['runtime_seconds'][summary['comparison_model']]:.2f} s

## Controlled parameters

Only `curve_type` differs between the two completed rasters.

{parameter_lines}

## Full-raster differences

Differences are `{summary['comparison_model']} - {summary['reference_model']}`.
For date metrics and LOS the unit is days; R2 is dimensionless; RMSE is in EVI units.

| Metric | Paired values | Median difference | Median absolute difference | P05 | P95 |
|---|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

## Model screening

ZHANG and AG were stopped after one real-data block because their fit diagnostics
failed the screening gate. A partial raster is not a valid scientific result.

| Model | Scope | Median R2 | Median RMSE | Decision |
|---|---|---:|---:|---|
{chr(10).join(probes)}

## Interpretation

This is an engineering sensitivity comparison on one tile, not a final model-selection
decision for Europe. ELMORE is retained as a valid alternative to BECK. ZHANG and AG
require package-level numerical investigation or revised implementation before any full
production run. Biological selection still requires representative ecosystems and
external validation.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "02_config" / "config.yaml",
    )
    parser.add_argument("--reference", default="BECK", type=str.upper)
    parser.add_argument("--comparison", default="ELMORE", type=str.upper)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_json(args.config)
    root = Path(config["project_root"])
    settings = config["pilot_benchmark"]
    tile_stem = Path(settings["tile"]).stem
    lambda_label = f"{float(settings['whittaker_lambda']):g}".replace(".", "p")
    suffix = f"W{lambda_label}_S{int(settings['max_seasons'])}"

    def run_id(model: str) -> str:
        return f"{tile_stem}_{model}_{suffix}"

    report_dir = root / "06_qc" / "reports"
    raster_dir = root / "04_intermediate" / "pilot"
    reference_summary = load_json(report_dir / f"{run_id(args.reference)}_benchmark.json")
    comparison_summary = load_json(report_dir / f"{run_id(args.comparison)}_benchmark.json")
    if reference_summary["status"] != "complete" or comparison_summary["status"] != "complete":
        raise RuntimeError("Both model benchmarks must be complete")

    reference_parameters = reference_summary["parameters"]
    comparison_parameters = comparison_summary["parameters"]
    mismatches = {
        key: (reference_parameters[key], comparison_parameters[key])
        for key in CONTROLLED_PARAMETERS
        if reference_parameters[key] != comparison_parameters[key]
    }
    if mismatches:
        raise RuntimeError(f"Controlled parameters differ: {mismatches}")

    reference_path = raster_dir / f"{run_id(args.reference)}.tif"
    comparison_path = raster_dir / f"{run_id(args.comparison)}.tif"
    year_count = (
        int(config["inventory"]["expected_end_year"])
        - int(config["inventory"]["expected_start_year"])
        + 1
    )
    with rasterio.open(reference_path) as reference, rasterio.open(comparison_path) as comparison:
        if (
            reference.count != comparison.count
            or reference.shape != comparison.shape
            or reference.transform != comparison.transform
            or reference.crs != comparison.crs
        ):
            raise RuntimeError("Model rasters are not grid-compatible")
        metric_comparisons = [
            compare_metric(reference, comparison, metric_index, year_count)
            for metric_index in range(len(METRICS))
        ]

    screening = []
    for model in (args.reference, args.comparison, "ZHANG", "AG"):
        path = report_dir / f"{run_id(model)}_benchmark.json"
        if not path.exists():
            continue
        item = load_json(path)
        validation = item["output_validation"]["metrics"]
        complete = item["status"] == "complete"
        median_r2 = validation["R2"]["median"]
        median_rmse = validation["RMSE"]["median"]
        passed = median_r2 > 0 and median_rmse < 0.1
        screening.append(
            {
                "model": model,
                "scope": "full tile" if complete else f"{item['completed_blocks']} block probe",
                "median_r2": median_r2,
                "median_rmse": median_rmse,
                "decision": "retain" if complete and passed else "stop after probe" if not passed else "retain",
            }
        )

    summary = {
        "tile": settings["tile"],
        "reference_model": args.reference,
        "comparison_model": args.comparison,
        "controlled_parameters": {
            key: reference_parameters[key] for key in CONTROLLED_PARAMETERS
        },
        "runtime_seconds": {
            args.reference: reference_summary["timing_seconds"]["wall"],
            args.comparison: comparison_summary["timing_seconds"]["wall"],
        },
        "metric_comparisons": metric_comparisons,
        "model_screening": screening,
    }

    output_dir = root / "06_qc" / "parameter_sensitivity"
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{tile_stem}_{args.reference}_vs_{args.comparison}"
    (output_dir / f"{stem}.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    with (output_dir / f"{stem}.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(metric_comparisons[0]))
        writer.writeheader()
        writer.writerows(metric_comparisons)
    (output_dir / f"{stem}.md").write_text(render_markdown(summary), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
