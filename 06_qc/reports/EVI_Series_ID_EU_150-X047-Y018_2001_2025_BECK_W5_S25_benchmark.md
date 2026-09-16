# One-tile CDTS phenology benchmark

- Status: **complete**
- Tile: `EVI_Series_ID_EU_150-X047-Y018_2001_2025.tif`
- Source size: 679 × 678 pixels × 575 dates
- CDTS: 0.6.0
- Curve: BECK; Whittaker lambda 5; maximum seasons 25
- Threads: 30
- Row block: 32
- Eligible pixels: 361244
- Completed row blocks: 22 / 22
- Read time: 7.32 s
- Gap-fill/preparation time: 8.23 s
- CDTS compute time: 760.35 s
- GeoTIFF write time: 19.78 s
- End-to-end elapsed time: 796.45 s
- Throughput: 475.10 eligible pixels s⁻¹
- Output: `04_intermediate\pilot\EVI_Series_ID_EU_150-X047-Y018_2001_2025_BECK_W5_S25.tif`

## Interpretation limits

This run is a performance and engineering test, not a release candidate. CDTS 0.6.0
returned no phenology for sampled real curves containing missing observations, so the
benchmark linearly fills all gaps, including long winter gaps. The installed build also
returned no metrics for the tested real curves when `min_season_length=45`; this benchmark
therefore uses zero for that filter. Raw sequential seasons are written as continuous day
numbers from 2001-01-01. Leap-year and annual-assignment validation remain required.
