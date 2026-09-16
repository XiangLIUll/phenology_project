# Decisions log

## 2026-09-16T19:51:31.097830+00:00 — Initial EVI inventory

1. **Source structure:** 673 spatial GeoTIFF stacks; each file stores the full
   2001–2025 time series as bands.
2. **Naming convention:** `EVI_Series_ID_<tile_id>_<start_year>_<end_year>.tif`.
3. **Date parser:** parse band descriptions formatted as `EVI_YYYY_MM_DD`; never infer leap-year
   dates from a fixed 365-day offset.
4. **Grid structure:** {'EPSG:3035': 673} at {(250.0, 250.0): 673}; spatially distinct tile
   transforms are retained and share 1 pixel-grid offset(s).
5. **EVI storage/scaling:** Float32 EVI is already in vegetation-index units; use scale factor 1.0.
6. **Missing/duplicate data:** 2 anomaly records; 2 distinct
   temporal signatures; duplicate tile IDs: none.
7. **Chunking strategy:** process one source tile at a time, with smaller spatial chunks inside
   each tile if needed; checkpoint by tile and metric.
8. **Blocking problems:** Review inventory_anomalies.csv before CDTS work.

## 2026-09-16 — One-tile CDTS performance benchmark

1. Selected the median-size, metadata-complete tile `EU_150-X047-Y018` rather
   than the tile with missing band descriptions.
2. Pinned CDTS 0.6.0 and installed only the minimal phenology runtime packages
   in the shared A-drive environment.
3. Used true one-based elapsed days from 2001-01-01 for the input time axis.
4. CDTS returned no metrics when real input curves retained missing observations;
   the benchmark therefore used full linear gap filling. This is not accepted as
   the production missing-data policy.
5. CDTS returned no metrics for sampled real curves when
   `min_season_length=45`; the benchmark used zero. This behavior requires a
   focused API/synthetic test before parameter selection.
6. The complete 679 × 678 × 575 tile took 796.45 seconds end-to-end with 30
   OpenMP threads and 32-row blocks. CDTS fitting accounted for 760.35 seconds.
7. The 475-band raw sequential-season output is retained only as an ignored
   intermediate. The tracked JSON/Markdown reports record timing and provenance.
