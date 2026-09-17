# One-tile CDTS phenology benchmark

- Status: **partial**
- Tile: `EVI_Series_ID_EU_150-X047-Y018_2001_2025.tif`
- Source size: 679 × 678 pixels × 575 dates
- CDTS: 0.8.0
- Curve: AG; Whittaker lambda 5.0; minimum season 45 days; maximum raw seasons 25
- Output years: 2001â€“2025
- Date units: calendar day of year (DOY; 1â€“365 or 366)
- Threads: 30
- Row block: 32
- Eligible pixels: 3834
- Completed row blocks: 1 / 22
- Read time: 1.61 s
- Gap-fill/preparation time: 0.21 s
- CDTS compute time: 1.91 s
- GeoTIFF write time: 0.65 s
- End-to-end elapsed time: 4.55 s
- Throughput: 2010.96 eligible pixels s⁻¹
- Output: `04_intermediate\pilot\EVI_Series_ID_EU_150-X047-Y018_2001_2025_AG_W5_S25.tif`

## Annual-output validation

- Finite date values checked: 1,654,922
- Observed date range: 1-365 DOY
- Date bands outside their calendar-year range: 0
- Date bands containing non-integer DOY: 0
- LOS: minimum 46.02, median 48.13, maximum 49.19 days
- R2: minimum -34.190, median -1.794, maximum 0.858
- RMSE: minimum 0.0304, median 0.1855, maximum 0.5066 EVI

LOS values above 366 days and strongly negative R2 values are retained as transparent
QC candidates; they are not silently clipped or converted.

## Interpretation limits

This run is a performance and engineering test, not a release candidate. CDTS 0.8.0
correctly evaluates `min_season_length=45` in elapsed calendar days. Missing values are
linearly filled only for numerical continuity and receive zero reliability weight through
the `weights_array` interface. Date metrics are assigned to their event calendar year and
written as leap-year-aware integer DOY. LOS remains a duration in days. R2 and RMSE retain
their native dimensionless and EVI units and are assigned by the season's POP year. When
multiple raw seasons contribute the same metric in one year, the later detected season
wins, matching CDTS 0.8.0 annualization behavior. Multi-season sensitivity remains required
before production.
