# Pan-European MODIS EVI phenology

Reproducible workflow for a 250 m annual land-surface phenology dataset for
Europe derived from MODIS EVI, 2001–2025.

The project is currently in **Stage 2: input inventory**. No continental
phenology processing should begin until the inventory report and its anomaly
checks have been reviewed.

## Current workflow

```powershell
& "A:\_BioGeo\liuxianx\RSdiversity\.venv\Scripts\python.exe" `
  .\01_script\00_create_project.py

& "A:\_BioGeo\liuxianx\RSdiversity\.venv\Scripts\python.exe" `
  .\01_script\01_inventory_evi.py
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

