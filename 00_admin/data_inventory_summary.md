# EVI input inventory summary

Generated: `2026-09-16T19:51:31.097830+00:00`

## Executive conclusion

The raw source contains **673 GeoTIFF tile stacks**. **673** were readable and
**0** failed. Each normal source file is a spatial tile containing the
complete band-level time series rather than a single-date raster. The modal time sequence occurs in
**672 of 673** readable tiles.

**EVI scaling decision:** Float32 EVI is already in vegetation-index units; use scale factor 1.0.

## Required inventory questions

1. **How many files exist?** 673 GeoTIFFs (auxiliary sidecars are not inventory records).
2. **How many files per year?** Not applicable at file level: every tile spans
   2001–2025. Band-level counts are listed below.
3. **Are there 23 observations per year?** Yes.
4. **Are all years present?** Yes.
5. **Actual dates?** 2001-01-01 through
   2025-12-19; see `03_inventory/time_index.csv`.
6. **Same CRS?** True; {'EPSG:3035': 673}.
7. **Identical pixel sizes?** True; {(250.0, 250.0): 673}.
8. **Transforms aligned?** True; 673 distinct tile
   transforms share 1 pixel-grid offset(s): {(0.0, 0.0): 673}.
9. **Extents?** The dataset is tiled/polygon-based, with one stack per tile ID.
10. **Single- or multiband?** Multiband; modal band count is
    575.
11. **EVI representation?** Float32 EVI is already in vegetation-index units; use scale factor 1.0.
12. **Nodata/fill values?** {'-Infinity': 673}.
13. **Physically plausible?** Approximate overview-sampled range is
    -0.2000 to 1.0000.
14. **Duplicate dates?** No in the reference sequence.
15. **Missing dates?** No annual count gaps detected.
16. **Duplicate spatial units?** None.
17. **Corrupt/unreadable rasters?** 0; see the anomaly table.

## Band-level temporal coverage

| Year | Observations |
| --- | --- |
| 2001 | 23 |
| 2002 | 23 |
| 2003 | 23 |
| 2004 | 23 |
| 2005 | 23 |
| 2006 | 23 |
| 2007 | 23 |
| 2008 | 23 |
| 2009 | 23 |
| 2010 | 23 |
| 2011 | 23 |
| 2012 | 23 |
| 2013 | 23 |
| 2014 | 23 |
| 2015 | 23 |
| 2016 | 23 |
| 2017 | 23 |
| 2018 | 23 |
| 2019 | 23 |
| 2020 | 23 |
| 2021 | 23 |
| 2022 | 23 |
| 2023 | 23 |
| 2024 | 23 |
| 2025 | 23 |

## Storage and grid overview

- Data types: `{'Float32': 673}`
- Compression: `{'DEFLATE': 673}`
- Distinct temporal signatures: `2`
- Statistics: GDAL overview-based approximate statistics, with persistent auxiliary metadata disabled
- Mean per-tile, per-band valid fraction: `0.4455`
- Raw directory (read-only): `A:\_BioGeo\liuxianx\Co_authors\ana\output\MODIS_EU_EVI\2001_2025`

## Anomalies

Inventory recorded **2** anomaly entries. See
`03_inventory/anomalies/inventory_anomalies.csv` for file-level details.

## Processing implication

Process each spatial tile independently and preserve its 575-band time order. This avoids a
continental in-memory mosaic, provides natural restart checkpoints, and permits mosaicking only
the final phenology metrics. Before production, synthetic CDTS tests must verify leap-year and
calendar semantics using `days_since_base_plus_one` from the time index.
