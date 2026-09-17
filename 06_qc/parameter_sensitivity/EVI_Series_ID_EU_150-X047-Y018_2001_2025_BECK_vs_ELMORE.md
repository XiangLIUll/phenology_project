# One-tile CDTS curve-model comparison

- Tile: `EVI_Series_ID_EU_150-X047-Y018_2001_2025.tif`
- Reference model: **BECK**
- Comparison model: **ELMORE**
- Parameter equality check: **passed**
- Reference runtime: 921.09 s
- Comparison runtime: 1435.96 s

## Controlled parameters

Only `curve_type` differs between the two completed rasters.

- `max_seasons`: `25`
- `apply_whittaker`: `True`
- `whittaker_lambda`: `5.0`
- `apply_hants`: `False`
- `min_season_length`: `45`
- `min_amplitude`: `0.1`
- `min_pixel_amplitude`: `0.1`
- `minimum_valid_observations`: `100`
- `block_rows`: `32`
- `n_jobs`: `30`

## Full-raster differences

Differences are `ELMORE - BECK`.
For date metrics and LOS the unit is days; R2 is dimensionless; RMSE is in EVI units.

| Metric | Paired values | Median difference | Median absolute difference | P05 | P95 |
|---|---:|---:|---:|---:|---:|
| TRS2.sos | 7,997,813 | 0.00 | 0.00 | -4.00 | 2.00 |
| TRS2.eos | 7,837,498 | 0.00 | 1.00 | -6.00 | 8.00 |
| TRS5.sos | 8,002,149 | 0.00 | 0.00 | -2.00 | 5.00 |
| TRS5.eos | 7,889,579 | 0.00 | 0.00 | -12.00 | 4.00 |
| TRS6.sos | 8,003,294 | 0.00 | 0.00 | -2.00 | 6.00 |
| TRS6.eos | 7,896,954 | 0.00 | 0.00 | -15.00 | 4.00 |
| DER.sos | 8,004,178 | 0.00 | 0.00 | -2.00 | 6.00 |
| DER.pos | 7,999,528 | 0.00 | 2.00 | -31.00 | 15.00 |
| DER.eos | 7,891,021 | 0.00 | 1.00 | -16.00 | 6.00 |
| UD | 8,001,396 | 0.00 | 0.00 | -3.00 | 3.00 |
| SD | 8,004,876 | 0.00 | 0.00 | -3.00 | 12.00 |
| DD | 7,904,087 | 0.00 | 1.00 | -69.00 | 9.00 |
| RD | 7,871,500 | 0.00 | 1.00 | -8.00 | 7.00 |
| Greenup | 8,001,434 | 0.00 | 0.00 | -3.00 | 3.00 |
| Maturity | 8,004,857 | 0.00 | 0.00 | -3.00 | 12.00 |
| Senescence | 7,904,094 | 0.00 | 1.00 | -69.00 | 9.00 |
| Dormancy | 7,871,506 | 0.00 | 1.00 | -8.00 | 7.00 |
| LOS | 7,999,479 | 0.00 | 1.00 | -22.06 | 10.93 |
| POP | 7,999,528 | 0.00 | 2.00 | -31.00 | 15.00 |
| R2 | 7,999,528 | 0.00 | 0.00 | -0.03 | 0.10 |
| RMSE | 7,999,528 | -0.00 | 0.00 | -0.03 | 0.01 |

## Model screening

ZHANG and AG were stopped after one real-data block because their fit diagnostics
failed the screening gate. A partial raster is not a valid scientific result.

| Model | Scope | Median R2 | Median RMSE | Decision |
|---|---|---:|---:|---|
| BECK | full tile | 0.944 | 0.0348 | retain |
| ELMORE | full tile | 0.951 | 0.0328 | retain |
| ZHANG | 1 block probe | -3.71e+09 | 4.57e+03 | stop after probe |
| AG | 1 block probe | -1.79 | 0.185 | stop after probe |

## Interpretation

This is an engineering sensitivity comparison on one tile, not a final model-selection
decision for Europe. ELMORE is retained as a valid alternative to BECK. ZHANG and AG
require package-level numerical investigation or revised implementation before any full
production run. Biological selection still requires representative ecosystems and
external validation.
