# Pan-European MODIS EVI phenology

Reproducible workflow for a 250 m annual land-surface phenology dataset for
Europe derived from MODIS EVI, 2001–2025.

The project is currently in **Stage 2: input inventory**. No continental
phenology processing should begin until the inventory report and its anomaly
checks have been reviewed.

A one-tile CDTS 0.8.0 engineering benchmark is included. Its code and timing
report are reproducible, while its phenology raster remains an intermediate
benchmark rather than a scientific release product.

## Current workflow

```powershell
& "A:\_BioGeo\liuxianx\RSdiversity\.venv\Scripts\python.exe" `
  .\01_script\00_create_project.py

& "A:\_BioGeo\liuxianx\RSdiversity\.venv\Scripts\python.exe" `
  .\01_script\01_inventory_evi.py

& "A:\_BioGeo\liuxianx\RSdiversity\.venv\Scripts\python.exe" `
  .\01_script\06_pilot_phenology.py
```

Configuration is centralized in [`02_config/config.yaml`](02_config/config.yaml).
The file uses JSON syntax, which is valid YAML, so the setup and inventory
stages require only the Python standard library plus the existing GDAL command
line tools.

## Inventory deliverables

- `00_admin/data_inventory_summary.md`
- `00_admin/decisions_log.md`
- `03_inventory/raster_inventory.csv`
- `03_inventory/raster_inventory.parquet`
- `03_inventory/time_index.csv`
- `03_inventory/grid_summary.csv`
- `03_inventory/anomalies/inventory_anomalies.csv`

Raw EVI inputs are treated as read-only. Generated raster products and large
intermediates are intentionally excluded from Git.

## Minimal CDTS benchmark environment

CDTS 0.8.0 declares several optional AI/STAC dependencies that the phenology
benchmark does not use. Install the pinned runtime dependencies first, then
install CDTS without its optional dependency set:

```powershell
python -m pip install -r .\11_environment\requirements.txt
python -m pip install --no-deps cdts==0.8.0
```

The exact resolved versions used in the benchmark are recorded in
`11_environment/requirements_lock.txt`.
