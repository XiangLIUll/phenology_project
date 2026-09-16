# Project status

## Current stage

Stage 2 — input inventory completed on 2026-09-16.

## Completed

- Created the project directory structure and centralized configuration.
- Inventoried all 673 source GeoTIFF tile stacks.
- Created CSV and Parquet inventories, a band-level time index, grid summary,
  anomaly table, inventory report, and decision log.
- Confirmed all rasters are readable, Float32, DEFLATE-compressed, EPSG:3035,
  and aligned to a 250 m grid.
- Confirmed the modal temporal sequence contains 575 observations: 23 per year
  for every year from 2001 through 2025.
- Confirmed overview-sampled EVI values are consistent with already-scaled EVI;
  the configured scale factor for the next phase should be 1.0.

## Blocker before CDTS verification

`EVI_Series_ID_EU_150-X046-Y013_2001_2025.tif` has 575 readable bands but no
band descriptions. Its dates cannot be independently verified from its raster
metadata. A deterministic recovery rule must be documented and validated
before this tile enters phenology processing.

## Next stage after blocker review

Implement the CDTS API probe and synthetic ordinary-year, leap-year, year-boundary,
and 25-year no-drift tests before any pilot or continental run.

