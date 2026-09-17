# Changelog

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
