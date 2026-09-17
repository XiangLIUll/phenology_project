# Changelog

## 2026-09-17 - Add curve-model sensitivity comparison

- Parameterized the one-tile runner for all CDTS 0.8.0 curve enums.
- Completed an identical-parameter ELMORE benchmark alongside BECK.
- Added full-raster, per-metric BECK-versus-ELMORE difference statistics.
- Recorded failed one-block ZHANG and AG fit-quality screens.
- Added an ELMORE synthetic regression test.

## 2026-09-17 — Correct annual date output

- Converted low-level CDTS cumulative event dates to leap-year-aware annual DOY.
- Replaced sequential-season band labels with metric-and-calendar-year labels.
- Preserved LOS, R2, and RMSE in their correct non-date units.
- Added annual-output range validation and a leap-year regression test.
- Recomputed and validated the complete one-tile benchmark raster.

## v0.1.0 - 2026-09-16

- Initialized the reproducible project structure.
- Added centralized configuration and the read-only EVI inventory workflow.
- Added CSV and GeoParquet-compatible tabular inventory outputs.
- Added automated checks for file naming, grid properties, temporal coverage,
  duplicate dates, raster readability, and EVI storage scale.
- Added a restartable, block-wise CDTS 0.6.0 one-tile phenology benchmark and
  recorded its complete timing and interpretation limits.
- Upgraded the benchmark to CDTS 0.8.0, restored the intended 45-calendar-day
  season filter, added zero-weight handling for interpolated observations, and
  added the new R2/RMSE outputs.
