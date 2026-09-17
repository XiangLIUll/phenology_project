# One-tile CDTS phenology benchmark

- Status: **complete**
- Tile: `EVI_Series_ID_EU_150-X047-Y018_2001_2025.tif`
- Source size: 679 × 678 pixels × 575 dates
- CDTS: 0.8.0
- Curve: BECK; Whittaker lambda 5; minimum season 45 days; maximum seasons 25
- Threads: 30
- Row block: 32
- Eligible pixels: 361244
- Completed row blocks: 22 / 22
- Read time: 8.16 s
- Gap-fill/preparation time: 14.24 s
- CDTS compute time: 839.49 s
- GeoTIFF write time: 31.13 s
- End-to-end elapsed time: 894.07 s
- Throughput: 430.31 eligible pixels s⁻¹
- Output: `04_intermediate\pilot\EVI_Series_ID_EU_150-X047-Y018_2001_2025_BECK_W5_S25.tif`

## Interpretation limits

This run is a performance and engineering test, not a release candidate. CDTS 0.8.0
correctly evaluates `min_season_length=45` in elapsed calendar days. Missing values are
linearly filled only for numerical continuity and receive zero reliability weight through
the new `weights_array` interface. Raw sequential seasons are written as continuous day
numbers from 2001-01-01. Leap-year and annual-assignment validation remain required.
