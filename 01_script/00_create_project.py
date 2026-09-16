"""Create the project directory structure without touching raw input data."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import logging
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


DIRECTORIES = (
    "00_admin",
    "01_script/utils",
    "02_config",
    "03_inventory/anomalies",
    "04_intermediate/pilot",
    "04_intermediate/cubes",
    "04_intermediate/tiles",
    "04_intermediate/checkpoints",
    "05_pheno_product/annual",
    "05_pheno_product/multiyear",
    "05_pheno_product/masks",
    "05_pheno_product/quicklooks",
    "06_qc/temporal",
    "06_qc/spatial",
    "06_qc/parameter_sensitivity",
    "06_qc/failed_pixels",
    "06_qc/reports",
    "07_validation/reference_data",
    "07_validation/matched_samples",
    "07_validation/statistics",
    "07_validation/figures",
    "08_figures/manuscript",
    "08_figures/supplementary",
    "09_metadata",
    "10_manuscript",
    "11_environment",
    "12_logs/inventory",
    "12_logs/pilot",
    "12_logs/production",
    "12_logs/validation",
    "tests",
    "tmp",
)


def load_config(path: Path) -> dict:
    """Load the JSON-compatible YAML configuration with the standard library."""
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def command_version(command: list[str]) -> str:
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.CalledProcessError) as error:
        return f"unavailable ({error})"
    return (result.stdout or result.stderr).strip().splitlines()[0]


def write_software_versions(project_root: Path, gdalinfo: Path) -> None:
    output = project_root / "11_environment" / "software_versions.txt"
    lines = [
        f"recorded_utc: {datetime.now(timezone.utc).isoformat()}",
        f"python: {sys.version.replace(chr(10), ' ')}",
        f"platform: {platform.platform()}",
        f"gdal: {command_version([str(gdalinfo), '--version'])}",
    ]
    for package in ("cdts", "numpy", "pandas", "xarray", "dask", "rasterio", "scipy"):
        try:
            version = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            version = "not installed"
        lines.append(f"{package}: {version}")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "02_config" / "config.yaml",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    project_root = Path(config["project_root"])
    raw_root = Path(config["raw_root"])
    gdalinfo = Path(config["gdalinfo"])

    if project_root.resolve() != Path(__file__).resolve().parents[1]:
        raise RuntimeError("Configured project_root does not match this repository")
    if not raw_root.is_dir():
        raise FileNotFoundError(f"Raw root does not exist: {raw_root}")
    if not gdalinfo.is_file():
        raise FileNotFoundError(f"gdalinfo does not exist: {gdalinfo}")

    for relative in DIRECTORIES:
        (project_root / relative).mkdir(parents=True, exist_ok=True)

    log_path = project_root / "12_logs" / "inventory" / "project_setup.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(log_path, encoding="utf-8"), logging.StreamHandler()],
    )
    write_software_versions(project_root, gdalinfo)
    logging.info("Project structure ready at %s", project_root)
    logging.info("Raw input confirmed (read-only workflow): %s", raw_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
