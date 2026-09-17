# Decisions log

## 2026-09-17 - Curve-model screening

BECK and ELMORE were compared on the same tile with identical Whittaker,
season-duration, amplitude, missing-data, annualization, block, and thread
settings. ELMORE passed synthetic and real-data checks and was run for the full
tile. It produced a slightly higher median R2 (0.951 versus 0.944) and lower
median RMSE (0.0328 versus 0.0348 EVI), but was 56% slower and returned fewer
finite date values. ZHANG and AG failed the fit-quality gate in synthetic or
one-block tests and were stopped rather than expanded into misleading full-tile
rasters. No curve model is frozen for production at this stage.

## 2026-09-17 - Annual date-output correction

The first CDTS 0.8.0 benchmark wrote low-level sequential-season event dates as
one-based elapsed days since 2001-01-01. Those values are valid internal CDTS
coordinates but are not annual DOY and can exceed 9,000 over 2001-2025.

The pilot now converts date metrics to leap-year-aware calendar DOY and assigns
them by the event's actual calendar year. LOS remains a duration. R2 and RMSE are
assigned using the corresponding season's POP year. If more than one raw season
maps the same metric to the same year, the later detected season wins, matching
CDTS 0.8.0 annualization behavior. Multi-season handling must still be tested
before the production parameter set is frozen.

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

## 2026-09-17 — CDTS 0.8.0 replacement benchmark

1. Replaced CDTS 0.6.0 with 0.8.0 after confirming that the C++ season filter
   now compares actual elapsed dates rather than observation indices.
2. Restored `min_season_length=45`; it now correctly represents 45 calendar
   days for the one-based elapsed-day time axis.
3. Updated the output contract from 19 to 21 metrics by retaining the new
   per-season `R2` and `RMSE` diagnostics.
4. Continued linear gap filling only for numerical continuity, while assigning
   every originally missing observation reliability weight zero through
   `weights_array`. Valid observations receive weight one.
5. Replaced the old intermediate with a 525-band output tagged CDTS 0.8.0,
   `MIN_SEASON_LENGTH=45`, and `RUN_STATUS=complete`.
6. The corrected full-tile run processed 361,244 eligible pixels in 894.07
   seconds: 839.49 seconds compute, 31.13 seconds write, 14.24 seconds
   preparation, and 8.16 seconds read. Throughput was 430.31 eligible pixels
   per second.
7. This supersedes the CDTS 0.6.0 benchmark result. The new run was about 12%
   slower, reflecting weighted fitting and two additional output metrics.
