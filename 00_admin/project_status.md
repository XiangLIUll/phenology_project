# Project status

## Current stage

Stage 3 — CDTS verification started; one-tile engineering benchmark completed
on 2026-09-16.

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
- Benchmarked CDTS 0.6.0 on tile `EU_150-X047-Y018`: 361,244 eligible pixels,
  13 minutes 16 seconds end-to-end, and 475 eligible pixels per second.

## Blocker before CDTS verification

`EVI_Series_ID_EU_150-X046-Y013_2001_2025.tif` has 575 readable bands but no
band descriptions. Its dates cannot be independently verified from its raster
metadata. A deterministic recovery rule must be documented and validated
before this tile enters phenology processing.

## Next stage after blocker review

Complete the CDTS API probe and synthetic ordinary-year, leap-year, year-boundary,
and 25-year no-drift tests. Resolve missing-observation handling and the observed
`min_season_length` behavior before any scientific pilot or continental run.
