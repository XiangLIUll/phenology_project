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
