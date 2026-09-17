# AI Agent Task — Pan-European MODIS EVI Land Surface Phenology, 2001–2025

## Current implementation note — 2026-09-17

The CDTS 0.8.0 low-level API returns event dates as one-based continuous days
from the configured base year. These raw values are valid internal coordinates
but must not be published as annual day of year (DOY), because later years
naturally have values in the thousands.

The pilot workflow now converts all date metrics to leap-year-aware calendar DOY
(1–365/366) and names bands by calendar year. Date metrics are assigned by the
event's actual year; LOS remains a duration in days; R2 and RMSE retain their
native values and are assigned by POP year. If more than one detected season
maps the same metric to the same year, the later detected season wins, matching
CDTS 0.8.0 annualization behavior. This tie rule remains a pilot choice and must
be evaluated in the required multi-season sensitivity analysis before release.

The corrected one-tile benchmark checked 149,368,652 finite date values. All
were integer DOY in the legal 1–365/366 calendar range. LOS values above 366
days and strongly negative R2 values are retained as QC candidates rather than
silently clipped.

## 0. Mission

Build a **fully reproducible, publication-grade pan-European land surface phenology (LSP) dataset** from the existing MODIS EVI 250 m time series for 2001–2025, using the Python package **CDTS** (`sacridini/cdts`) as the primary phenology engine.

The project must be designed so that the resulting dataset, metadata, code, validation, and documentation can support a **data-centric paper**, with **Scientific Data** as a possible target journal.

Do not treat this as a one-off analysis. Treat it as a versioned scientific data-production pipeline.

The final system must be:

- reproducible;
- restartable after interruption;
- memory-safe for continental-scale processing;
- explicit about parameter choices;
- transparent about failed pixels and missing observations;
- publication-ready;
- able to regenerate every released raster from the raw EVI input and a pinned software environment.

---

# 1. Fixed paths

Use these exact Windows paths.

## Raw EVI input

```text
A:\_BioGeo\liuxianx\Co_authors\ana\output\MODIS_EU_EVI\2001_2025
```

Treat the raw directory as **read-only**.

Never rename, delete, overwrite, resample, or modify original files in place.

## Project root

```text
A:\_BioGeo\liuxianx\phenology_project
```

All code, configuration, logs, intermediate products, final outputs, metadata, figures, and manuscript-support files must be created under this project root.

In Python, use raw strings or `pathlib.Path`, for example:

```python
from pathlib import Path

RAW_ROOT = Path(r"A:\_BioGeo\liuxianx\Co_authors\ana\output\MODIS_EU_EVI\2001_2025")
PROJECT_ROOT = Path(r"A:\_BioGeo\liuxianx\phenology_project")
```

Do not hard-code the paths repeatedly across scripts. Put them in one YAML configuration file.

---

# 2. Required project structure

Create this structure if it does not already exist:

```text
phenology_project/
│
├── 00_admin/
│   ├── project_status.md
│   ├── decisions_log.md
│   └── data_inventory_summary.md
│
├── 01_script/
│   ├── 00_create_project.py
│   ├── 01_inventory_evi.py
│   ├── 02_validate_rasters.py
│   ├── 03_build_time_index.py
│   ├── 04_cdts_api_probe.py
│   ├── 05_build_evi_cube.py
│   ├── 06_pilot_phenology.py
│   ├── 07_parameter_sensitivity.py
│   ├── 08_run_europe_phenology.py
│   ├── 09_export_products.py
│   ├── 10_qc_spatial_temporal.py
│   ├── 11_validate_external_products.py
│   ├── 12_validation_statistics.py
│   ├── 13_make_dataset_figures.py
│   ├── 14_build_metadata.py
│   ├── 15_build_data_dictionary.py
│   ├── 16_package_release.py
│   └── utils/
│       ├── io.py
│       ├── dates.py
│       ├── raster.py
│       ├── qc.py
│       ├── logging_utils.py
│       └── cdts_utils.py
│
├── 02_config/
│   ├── config.yaml
│   ├── phenology_parameters.yaml
│   └── validation_datasets.yaml
│
├── 03_inventory/
│   ├── raster_inventory.csv
│   ├── raster_inventory.parquet
│   ├── time_index.csv
│   ├── grid_summary.csv
│   └── anomalies/
│
├── 04_intermediate/
│   ├── pilot/
│   ├── cubes/
│   ├── tiles/
│   └── checkpoints/
│
├── 05_pheno_product/
│   ├── annual/
│   ├── multiyear/
│   ├── masks/
│   └── quicklooks/
│
├── 06_qc/
│   ├── temporal/
│   ├── spatial/
│   ├── parameter_sensitivity/
│   ├── failed_pixels/
│   └── reports/
│
├── 07_validation/
│   ├── reference_data/
│   ├── matched_samples/
│   ├── statistics/
│   └── figures/
│
├── 08_figures/
│   ├── manuscript/
│   └── supplementary/
│
├── 09_metadata/
│   ├── data_dictionary.csv
│   ├── file_manifest.csv
│   ├── checksums_sha256.txt
│   ├── citation.cff
│   ├── metadata.json
│   └── README_dataset.md
│
├── 10_manuscript/
│   ├── paper_outline.md
│   ├── methods_notes.md
│   ├── technical_validation_notes.md
│   ├── data_records_notes.md
│   └── usage_notes.md
│
├── 11_environment/
│   ├── environment.yml
│   ├── requirements.txt
│   ├── requirements_lock.txt
│   └── software_versions.txt
│
├── 12_logs/
│   ├── inventory/
│   ├── pilot/
│   ├── production/
│   └── validation/
│
└── README.md
```

Do not create another nested `phenology_project/phenology_project` directory.

---

# 3. Scientific target

The intended product is approximately:

> A 250 m annual land surface phenology dataset for Europe derived from MODIS MOD13Q1 EVI, covering 2001–2025, with multiple phenological transition metrics, quality-control layers, validation, uncertainty/sensitivity information, and a fully reproducible processing workflow.

Do **not** claim that this is simply “the first European phenology dataset”.

Existing European phenology products already exist at other resolutions, sensors, vegetation indices, methods, or time spans.

The potentially defensible distinguishing features should instead be investigated and documented, such as:

- 250 m native MOD13Q1 EVI;
- full European coverage;
- annual 2001–2025 product;
- consistent processing across the complete MODIS era;
- 19 CDTS/phenofit-style phenology metrics;
- pixel-level QC and validity layers;
- explicit sensitivity to curve/smoothing parameters;
- external validation;
- reproducible open-source production workflow;
- cloud-optimized release format and machine-readable metadata.

Any novelty statement must be evidence-based after a structured literature/product review.

For a Scientific Data submission, prioritize **technical quality, completeness, validation, reuse, metadata, and reproducibility** over a hypothesis-driven ecological story.

---

# 4. CDTS references that must be checked before coding

Primary package:

```text
https://github.com/sacridini/cdts
```

Phenology tutorial:

```text
https://sacridini.github.io/cdts/tutorials/phenology/
```

The current CDTS documentation indicates that the phenology engine can:

- fit several seasonal curve types including Beck, Elmore, Gu, Klosterman, Zhang, asymmetric Gaussian, and double logistic;
- use Whittaker or HANTS smoothing;
- use Dask/Xarray for large rasters;
- use C++/OpenMP for pixel-wise processing;
- return 19 phenological metrics.

The current documented metrics include:

```text
TRS2.sos
TRS2.eos
TRS5.sos
TRS5.eos
TRS6.sos
TRS6.eos
DER.sos
DER.eos
DER.pos
UD
SD
DD
RD
Greenup
Maturity
Senescence
Dormancy
LOS
POP
```

Before relying on these names, the agent must verify them against the **installed CDTS version**.

Do not assume that the GitHub `main` API and installed PyPI release are identical.

Record:

- CDTS version;
- exact Git commit if installed from GitHub;
- Python version;
- NumPy;
- Pandas;
- Xarray;
- Dask;
- Rasterio;
- rioxarray;
- GDAL;
- PROJ;
- compiler/OpenMP availability.

Pin the final production environment.

---

# 5. Phase 1 — Inventory the raw data before processing anything

The first scientific task is to understand the actual file organization.

Recursively scan:

```text
A:\_BioGeo\liuxianx\Co_authors\ana\output\MODIS_EU_EVI\2001_2025
```

For every raster, record at minimum:

```text
full_path
relative_path
filename
year
date
DOY
MODIS_composite_index
tile_or_polygon_id
band_count
dtype
nodata
width
height
CRS
transform
pixel_size_x
pixel_size_y
bounds
compression
file_size_bytes
minimum
maximum
mean
valid_fraction
```

Statistics may initially be approximate/sample-based for speed.

Write:

```text
03_inventory/raster_inventory.csv
03_inventory/raster_inventory.parquet
```

Generate a human-readable summary:

```text
00_admin/data_inventory_summary.md
```

The summary must answer:

1. How many files exist?
2. How many files per year?
3. Are there 23 MOD13Q1 16-day observations per year?
4. Are all years 2001–2025 present?
5. What are the actual acquisition/composite dates?
6. Are all rasters on the same CRS?
7. Are pixel sizes identical?
8. Are transforms aligned?
9. Are extents identical or is the dataset tiled/polygon-based?
10. Are files single-band or multi-band?
11. Is EVI stored as scaled integer or floating-point EVI?
12. What nodata/fill values occur?
13. Are values physically plausible?
14. Are there duplicate dates?
15. Are there missing dates?
16. Are there duplicate spatial units?
17. Are any rasters corrupted or unreadable?

Do not start continental phenology processing before this report exists.

---

# 6. Critical EVI scaling rule

MODIS vegetation-index source products commonly store EVI using an integer scale factor, but this dataset may already have been preprocessed.

Therefore:

**Never automatically multiply by 0.0001.**

Instead:

1. inspect raster dtype;
2. inspect value ranges;
3. inspect metadata/tags if available;
4. inspect previous preprocessing scripts if present;
5. determine whether values look like:
   - scaled integers, e.g. thousands; or
   - already converted EVI, approximately in a vegetation-index range;
6. document the evidence;
7. put the chosen scale factor in `02_config/config.yaml`.

Add a sanity test that fails loudly if the resulting EVI is outside the expected practical range.

Do not silently clip extreme values merely to make the algorithm run.

Flag suspect observations.

---

# 7. Time axis — do not make a leap-year error

This is a critical requirement.

The CDTS phenology tutorial currently demonstrates a multi-year continuous day number using a simplified expression conceptually equivalent to:

```python
DOY + (year - base_year) * 365
```

Do **not** blindly use that formula for a 25-year production dataset.

It can mishandle leap years unless the CDTS implementation explicitly expects that convention.

The agent must create:

```text
01_script/03_build_time_index.py
01_script/04_cdts_api_probe.py
```

and test the expected date semantics.

Preferred continuous time representation, if accepted by CDTS, is:

```python
days_since_base = (
    timestamp.normalize() - pd.Timestamp(f"{base_year}-01-01")
).days + 1
```

This preserves true elapsed days through leap years.

However, because `return_annual=True` and `base_year` may perform internal year mapping, the agent must verify the implementation with synthetic tests.

Required unit tests:

### Test A — one ordinary year
Generate a known synthetic single-season curve and confirm retrieved transition dates.

### Test B — leap year
Run a synthetic 2004 curve and verify DOY mapping.

### Test C — boundary across 2003 → 2004
Verify no duplicated time coordinate.

### Test D — boundary across 2004 → 2005
Verify no one-day shift.

### Test E — 25-year synthetic sequence
Place the same idealized seasonal curve on the same calendar DOY every year from 2001–2025.

The retrieved annual phenology should not systematically drift because of leap years.

If CDTS internally requires a 365-day artificial calendar, document this explicitly and quantify the effect.

Do not proceed to final production until this is understood.

---

# 8. Build the input cube lazily

The full European data volume may be very large.

Do not load all 25 years into RAM as a dense NumPy array.

Use:

- Xarray;
- rioxarray;
- Dask;
- chunked raster reads;
- spatial tiling;
- lazy computation.

Preferred cube dimensions:

```text
time, y, x
```

For tiled or polygon-based source data, first determine whether:

### Strategy A
Each spatial unit already contains a complete 2001–2025 temporal stack.

or

### Strategy B
Each date contains multiple spatial units that must be processed independently.

or

### Strategy C
Each year/date is already a complete European raster.

Select the strategy after inventory.

Do not mosaic the entire continent into memory.

If spatial units are perfectly aligned and non-overlapping, process them independently and mosaic only final products.

If they overlap, define a deterministic overlap rule and document it.

---

# 9. Pilot study before production

Before running Europe, choose a small but ecologically diverse pilot sample.

At minimum include example areas representing:

- northern/boreal vegetation;
- temperate deciduous forest;
- Mediterranean vegetation;
- agricultural land;
- alpine/high-elevation vegetation;
- an evergreen-dominated area;
- a low-amplitude/non-vegetated area for rejection testing.

The pilot should include multiple years, including:

```text
2003
2004
2005
2010
2018
2022
2025
```

so leap years, climatic extremes, and recent data are represented.

The agent may adjust the exact spatial pilot units based on the input tiling scheme, but must record their IDs.

---

# 10. Baseline CDTS phenology configuration

Start with a reproducible baseline, not an arbitrary final choice.

A reasonable initial candidate is:

```python
from cdts._core.phenology import CurveType

pheno = evi_cube.cdts.run_phenology(
    dates=dates_numeric,
    curve_type=int(CurveType.BECK),
    max_seasons=number_of_years,
    apply_whittaker=True,
    whittaker_lambda=5.0,
    apply_hants=False,
    min_season_length=45,
    min_amplitude=0.10,
    min_pixel_amplitude=0.10,
    return_annual=True,
    base_year=2001,
    n_jobs=30,
)
```

This is only a **pilot starting point**.

Do not use these values for the final dataset without testing.

In particular:

- the optimal Whittaker lambda may differ for MOD13Q1 EVI;
- `min_amplitude=0.10` may exclude meaningful low-amplitude northern or evergreen systems;
- agricultural multi-cropping may violate a one-season-per-calendar-year assumption;
- evergreen and Mediterranean vegetation may require special scrutiny;
- annual calendar boundaries can split winter-growing vegetation.

All parameter choices must be justified by sensitivity testing and validation.

---

# 11. Parameter sensitivity experiment

Create:

```text
01_script/07_parameter_sensitivity.py
```

Evaluate a manageable factorial or structured subset of:

## Curve models

At least:

```text
BECK
ELMORE
ZHANG
```

If computationally feasible, also test:

```text
GU
KLOSTERMAN
DL
AG
```

## Smoothing

Compare:

```text
Whittaker
HANTS
```

For Whittaker, test for example:

```text
lambda = 1
lambda = 2
lambda = 5
lambda = 10
```

For HANTS, test a small reasonable set of harmonic frequencies supported by the current API.

## Minimum amplitude

Test, subject to observed EVI distribution:

```text
0.05
0.10
0.15
```

## Minimum season length

For example:

```text
30
45
60
90 days
```

Do not choose the final parameter set merely because it yields the most valid pixels.

Evaluate:

- fit plausibility;
- temporal stability;
- spatial coherence;
- agreement with reference phenology;
- failure rate;
- sensitivity across land-cover classes;
- sensitivity across latitude/elevation/climate zones.

Save the full pilot experiment table under:

```text
06_qc/parameter_sensitivity/
```

---

# 12. Multi-season and calendar-boundary problem

Europe is not uniformly single-season.

The workflow must explicitly investigate:

- double cropping;
- winter crops;
- Mediterranean winter/spring vegetation;
- irrigated crops;
- bimodal seasonal curves;
- pixels with two genuine vegetation peaks;
- seasons crossing 31 December.

Do not force every pixel into a biologically unrealistic one-season template.

At minimum produce a pilot comparison between:

```text
return_annual=True
```

and a suitable:

```text
return_annual=False
```

multi-season configuration.

Determine whether the released dataset should contain:

### Option 1
A standardized primary annual season only.

### Option 2
Primary and secondary seasons.

### Option 3
A primary annual dataset plus a secondary-season companion product.

If a primary season is selected from multiple detected seasons, define the selection rule explicitly, such as greatest seasonal amplitude, and record a `season_count` or `multi_season_flag`.

Never silently discard secondary seasons without a flag.

---

# 13. Production strategy

After the pilot configuration is frozen, create:

```text
01_script/08_run_europe_phenology.py
```

Requirements:

- process spatially in chunks/tiles;
- process data lazily;
- use Dask appropriately;
- avoid nested uncontrolled parallelism between Dask workers and OpenMP;
- expose worker count / `n_jobs` through YAML;
- save checkpoints;
- skip already completed valid outputs;
- write one log per unit;
- record start/end time;
- record failures;
- record peak memory if feasible;
- never require rerunning completed tiles after a crash;
- support a `--dry-run`;
- support `--tile`;
- support `--year` or equivalent debug subset;
- support `--overwrite` only when explicitly requested.

Do not set both a large number of Dask workers and `n_jobs=-1` per worker without controlling CPU oversubscription.

Benchmark a few combinations first.

---

# 14. Required phenology output metrics

CDTS currently documents 19 metrics.

Retain all metrics if computationally and scientifically valid:

```text
TRS2.sos
TRS2.eos
TRS5.sos
TRS5.eos
TRS6.sos
TRS6.eos
DER.sos
DER.eos
DER.pos
UD
SD
DD
RD
Greenup
Maturity
Senescence
Dormancy
LOS
POP
```

Also create useful ancillary layers where possible:

```text
valid_obs_count
valid_obs_fraction
annual_evi_min
annual_evi_max
annual_evi_amplitude
season_count
multi_season_flag
fit_success_flag
low_amplitude_flag
temporal_gap_flag
edge_year_flag
source_qc_flag
```

If CDTS exposes goodness-of-fit or residual metrics, save them.

If it does not, derive independent curve-fit diagnostics on the validation/pilot sample rather than inventing an undocumented metric.

---

# 15. Edge years

Phenology fitting near the beginning and end of a time series can suffer edge effects.

Investigate whether 2001 and 2025 are less stable because no preceding/following full year is available.

If needed:

- use temporal padding from neighboring observations if they exist;
- or mark edge-year products with an `edge_year_flag`;
- or document higher uncertainty.

Do not hide this limitation.

---

# 16. Output data model

Prefer publication-ready geospatial formats.

Primary recommendation:

- Cloud-Optimized GeoTIFF (COG);
- DEFLATE or ZSTD compression, depending on compatibility;
- internal tiling;
- overviews;
- consistent nodata;
- meaningful raster tags;
- EPSG/CRS preserved;
- deterministic filenames.

Evaluate whether phenology dates can safely be stored as integer DOY:

```text
Int16 / UInt16
```

with a clear nodata value, rather than Float32, to reduce data volume.

LOS can also usually be integer days.

Continuous EVI-related variables may need scaled Int16 or Float32 depending on precision requirements.

Never cast before checking valid ranges.

---

# 17. Proposed file naming convention

Use a deterministic convention similar to:

```text
EU_MODIS_EVI250_PHENO_v1.0_<METRIC>_<YEAR>.tif
```

Examples:

```text
EU_MODIS_EVI250_PHENO_v1.0_TRS2_SOS_2001.tif
EU_MODIS_EVI250_PHENO_v1.0_TRS2_EOS_2001.tif
EU_MODIS_EVI250_PHENO_v1.0_DER_SOS_2001.tif
EU_MODIS_EVI250_PHENO_v1.0_GREENUP_2001.tif
EU_MODIS_EVI250_PHENO_v1.0_LOS_2001.tif
EU_MODIS_EVI250_PHENO_v1.0_POP_2001.tif
```

Avoid dots in metric names inside filenames if they create tooling ambiguity.

Maintain exact mapping in:

```text
09_metadata/data_dictionary.csv
```

The original CDTS metric name must be preserved as a metadata field.

---

# 18. Spatial quality control

For every metric/year, calculate at least:

```text
valid pixel count
valid fraction
nodata fraction
minimum
maximum
median
mean
standard deviation
1st percentile
5th percentile
25th percentile
75th percentile
95th percentile
99th percentile
```

For DOY-like metrics, identify impossible or suspicious values.

Create maps of:

- missingness;
- failure frequency over 25 years;
- median SOS;
- median EOS;
- median LOS;
- interannual standard deviation;
- trend only as an optional diagnostic, not as the central result of a Data Descriptor;
- count of valid years.

Flag isolated artifacts and tile-edge discontinuities.

Do not apply a spatial smoothing filter to published phenology dates just to make maps look cleaner unless it is scientifically justified and explicitly released/documented as a separate derived product.

---

# 19. Temporal quality control

At pixel/sample level check:

```text
SOS < POP < EOS
LOS ≈ EOS - SOS
```

where those definitions are expected to correspond.

Because different CDTS metric families define transitions differently, do not assume every pair must satisfy exactly the same ordering without checking the documented definition.

Also evaluate:

- year-to-year jumps;
- repeated exact values;
- persistent failure;
- unrealistic seasonal length;
- apparent boundary wrapping;
- northern latitude behavior;
- Mediterranean winter-season behavior;
- agricultural double-season behavior.

Create QC masks, not only summary plots.

---

# 20. Validation strategy for a publication-grade dataset

A data paper will be much stronger with multiple complementary validation layers.

Investigate and, if licensing/access permits, use a subset of the following.

## A. Copernicus HR-VPP

Pan-European vegetation phenology at approximately 10 m, available for recent years.

Use as a high-spatial-resolution phenology comparison.

Aggregate/reproject carefully to the MODIS support.

Compare at least SOS/EOS-like metrics after matching definitions as closely as possible.

## B. Copernicus MR-VPP

Pan-European MODIS-based medium-resolution phenology products exist for 2000–2025 at approximately 392 m / 500 m depending on product/version.

This is an important independent product-level comparison.

Do not call it true ground truth.

## C. PEP725 / in-situ phenology

Investigate access to European ground phenological observations.

Where observations correspond conceptually to satellite transition metrics, match them spatially and temporally.

Be explicit that point observations and 250 m land-surface phenology are not identical quantities.

## D. PhenoCam or other camera phenology

Use where geographically and temporally suitable.

## E. Published regional 250 m phenology

A 250 m EVI2 phenology study/product exists for the Iberian Peninsula for roughly 2001–2021.

This can be a useful regional cross-check, while recognizing:

- EVI2 is not identical to MOD13Q1 EVI;
- compositing can differ;
- smoothing/fitting methods can differ;
- phenology definitions can differ.

---

# 21. Validation statistics

For matched observations/products, report appropriate statistics such as:

```text
n
bias
median bias
MAE
RMSE
correlation
Spearman correlation
R² where appropriate
robust regression slope
interquartile error range
```

Stratify, where sample size permits, by:

- year;
- land-cover class;
- latitude zone;
- elevation band;
- broad bioclimatic zone;
- deciduous/evergreen;
- forest/grassland/cropland;
- SOS vs EOS;
- metric definition.

Do not pool everything into one continental correlation coefficient.

For spatial autocorrelation, avoid treating millions of neighboring pixels as statistically independent validation samples.

Prefer spatially stratified or blocked sampling.

---

# 22. Land-cover stratification

Use a stable European/global land-cover product only if needed for QC and validation stratification.

Do not alter the primary phenology product based on a single land-cover map unless scientifically justified.

At minimum distinguish broad classes useful for interpretation:

```text
deciduous forest
evergreen forest
mixed forest
grassland
cropland
shrubland
wetland
sparse vegetation
urban/built-up
water
snow/ice where relevant
```

Water and permanently non-vegetated areas should normally fail amplitude/vegetation checks, but the mask logic must be explicit.

---

# 23. Reproducibility requirements

Every executable script must:

- have a `main()` function;
- use `argparse` or an equivalent CLI;
- write structured logs;
- read configuration from YAML;
- avoid manual edits between runs;
- use deterministic random seeds where random sampling occurs;
- raise errors rather than silently continue after corrupted input;
- return non-zero exit status after fatal errors;
- record software versions;
- be idempotent where practical.

Use relative project paths derived from `PROJECT_ROOT`, not scattered absolute output paths.

Create a small test suite if feasible:

```text
tests/
```

At minimum test:

- date parser;
- filename parser;
- leap-year conversion;
- EVI scaling detection;
- raster alignment;
- output filename generation;
- phenology synthetic curve behavior.

---

# 24. Provenance

For every final file, retain provenance linking it to:

- source input files;
- source dates;
- source MODIS product/version if known;
- scale factor;
- missing-data handling;
- CDTS version/commit;
- curve model;
- smoothing method;
- all threshold parameters;
- processing date;
- pipeline version.

Create:

```text
09_metadata/file_manifest.csv
```

with at least:

```text
filename
relative_path
metric
year
dtype
nodata
crs
resolution
bounds
size_bytes
sha256
pipeline_version
cdts_version
parameter_set_id
creation_timestamp
```

---

# 25. Dataset versioning

Start with:

```text
v0.1 = pilot
v0.5 = complete internal production
v0.9 = validation candidate
v1.0 = public release
```

Do not overwrite released versions.

Put version in filenames and metadata.

Maintain:

```text
CHANGELOG.md
```

---

# 26. Figures needed for a Scientific Data-style paper

Generate publication-quality figures, but keep the final Data Descriptor focused on data description and validation rather than ecological hypothesis testing.

Suggested figures:

## Figure 1
Study area, spatial coverage, input MODIS sampling, and processing workflow.

## Figure 2
Representative EVI time series and fitted phenology curves across major European ecosystem types.

Show raw EVI, smoothed curve, fitted seasonal curve, and selected transition dates.

## Figure 3
Example pan-European maps for representative metrics, such as median SOS, EOS, and LOS.

## Figure 4
Data completeness / valid-year count / QC failure map.

## Figure 5
Technical validation against one or more independent reference datasets.

## Figure 6
Parameter/model sensitivity across ecosystem types.

Optional additional figures should be used only when they support technical understanding of the dataset.

Save source data used for every figure so the figures are reproducible.

---

# 27. Manuscript preparation

Create:

```text
10_manuscript/paper_outline.md
```

using a Scientific Data Data Descriptor structure:

```text
Title
Abstract
Background & Summary
Methods
  Input data
  MODIS EVI preprocessing
  Time-series construction
  Phenology extraction
  Parameter selection
  Quality control
  Data production
Data Records
Data Overview (optional and limited)
Technical Validation
Usage Notes
Data Availability
Code Availability
References
Author Contributions
Competing Interests
Acknowledgements
Funding
```

The manuscript should not be written as a conventional Results/Discussion ecological paper.

Do not make unsupported subjective statements such as:

```text
the first
the most comprehensive
unprecedented
highly accurate
superior
```

unless they are rigorously supported and appropriate for the journal.

---

# 28. Data paper positioning

A safer working title is something like:

```text
A 250 m annual MODIS EVI land surface phenology dataset for Europe, 2001–2025
```

Alternative:

```text
Pan-European land surface phenology from 25 years of 250 m MODIS EVI observations
```

A stronger eventual dataset contribution would include:

1. annual 250 m phenology;
2. multiple transition definitions rather than one arbitrary SOS/EOS pair;
3. consistent 25-year coverage;
4. QC layers;
5. model/parameter sensitivity;
6. independent validation;
7. open code;
8. machine-readable metadata;
9. COG or similarly reusable raster distribution;
10. a stable DOI for data and code.

---

# 29. Important existing products to acknowledge

The agent should conduct a proper literature/product review, but begin with these known comparators.

## Copernicus / EEA Medium Resolution Vegetation Phenology and Productivity

Pan-European MODIS-based phenology is available for 2000–2025 at approximately 392 m / 500 m in current product listings.

Use this as a major comparator, not as evidence that the proposed 250 m EVI product lacks value.

## Copernicus HR-VPP

Pan-European high-resolution vegetation phenology exists at approximately 10 m for recent years.

Use as an important recent-year validation/comparison product.

## JRC global land surface phenology

JRC distributes MODIS-derived phenology products based on lower-resolution/long-term-average processing.

## European long-term NDVI phenology datasets

Other European phenology datasets based on long-term NDVI records exist and must be cited.

## Iberian 250 m EVI2 phenology

Regional 250 m MODIS EVI2 phenology has been published for the Iberian Peninsula.

Therefore, novelty must be framed around the exact combination of:

```text
Europe + 250 m + MOD13Q1 EVI + annual 2001–2025 + multi-metric + QC + validation + reproducibility
```

and should be verified systematically before submission.

---

# 30. Suggested external references

CDTS:

```text
https://github.com/sacridini/cdts
https://sacridini.github.io/cdts/tutorials/phenology/
```

Scientific Data submission guidance:

```text
https://www.nature.com/sdata/submission-guidelines
```

Copernicus/EEA Medium Resolution VPP:

```text
https://www.eea.europa.eu/en/datahub/datahubitem-view/8da5d056-287c-4f2a-8168-03df3a94e427
```

Copernicus/EEA 500 m VPP:

```text
https://www.eea.europa.eu/en/datahub/datahubitem-view/09eac45f-6ce0-49de-bc24-4f7b48f8397a
```

Published Iberian 250 m EVI2 example:

```text
https://doi.org/10.1016/j.scitotenv.2024.176453
```

Phenofit method reference:

```text
Kong et al. (2022), Methods in Ecology and Evolution
https://doi.org/10.1111/2041-210X.13870
```

---

# 31. Agent execution order

Execute the project in this order.

## Stage 1 — Setup

- create directories;
- create configuration files;
- detect Python environment;
- install/pin dependencies;
- record versions;
- confirm raw path exists;
- confirm project path is writable.

## Stage 2 — Inventory

Run the recursive inventory.

Produce inventory CSV/Parquet and markdown summary.

Do not continue automatically if there are unexplained missing years, duplicate dates, inconsistent grids, unreadable rasters, or ambiguous EVI scaling.

Instead create a clear anomaly report and resolve programmatically where possible.

## Stage 3 — CDTS API verification

- inspect installed API;
- test metric names;
- test curve enum names;
- test date semantics;
- run synthetic phenology tests;
- specifically test leap years.

## Stage 4 — Pilot

- select representative spatial units;
- build lazy cube;
- run baseline;
- visualize curves;
- examine failures;
- test multi-season behavior.

## Stage 5 — Sensitivity

- compare curve models;
- compare smoothing;
- compare amplitude threshold;
- compare minimum season duration;
- freeze parameter set;
- assign a `parameter_set_id`.

## Stage 6 — Production

Run all European units using checkpoints.

Generate raw phenology outputs and QC layers.

## Stage 7 — Export

Create standardized COG products.

Validate every output's:

```text
dimensions
CRS
transform
dtype
nodata
COG compliance
checksum
```

## Stage 8 — Validation

Acquire/reference permitted external validation products.

Perform matched comparisons and stratified statistics.

## Stage 9 — Metadata

Create:

```text
data dictionary
file manifest
checksums
README
citation metadata
provenance
software environment
```

## Stage 10 — Manuscript support

Prepare figures, methods notes, validation notes, Data Records description, and paper outline.

---

# 32. Agent behavior rules

The agent should work autonomously but scientifically.

### Do

- inspect before assuming;
- log every decision;
- preserve raw data;
- use small tests before large jobs;
- save checkpoints;
- make code reusable;
- favor config-driven parameters;
- validate intermediate outputs;
- document uncertainty;
- report unexpected patterns instead of hiding them;
- keep publication reproducibility in mind at every step.

### Do not

- overwrite source files;
- resample repeatedly;
- load the continent into memory;
- silently drop failed pixels;
- silently interpolate large temporal gaps;
- assume all years have identical usable observations;
- assume EVI needs scaling without checking;
- assume one growing season is valid everywhere;
- use a simplified multi-year calendar without leap-year tests;
- apply cosmetic spatial smoothing to the scientific product;
- choose parameters solely for prettier maps;
- claim novelty without a literature/product review.

---

# 33. Completion criteria

The project is not complete until all of the following exist.

## Data engineering

- [ ] complete input inventory;
- [ ] no unexplained duplicate timestamps;
- [ ] documented EVI scaling;
- [ ] documented CRS/grid;
- [ ] tested time-axis logic;
- [ ] tested leap-year behavior;
- [ ] successful pilot;
- [ ] frozen phenology parameter set;
- [ ] full Europe processing;
- [ ] restartable production pipeline.

## Final dataset

- [ ] annual 2001–2025 products;
- [ ] chosen phenology metrics;
- [ ] ancillary QC layers;
- [ ] consistent COG output;
- [ ] valid nodata;
- [ ] metadata embedded;
- [ ] checksums.

## Validation

- [ ] independent comparison product(s);
- [ ] temporal validation;
- [ ] spatial validation;
- [ ] stratified validation;
- [ ] parameter sensitivity;
- [ ] failure/missingness analysis.

## Reproducibility

- [ ] pinned environment;
- [ ] code repository-ready structure;
- [ ] README;
- [ ] config files;
- [ ] logs;
- [ ] provenance;
- [ ] data dictionary;
- [ ] manifest.

## Publication

- [ ] Data Descriptor outline;
- [ ] Methods notes;
- [ ] Data Records notes;
- [ ] Technical Validation notes;
- [ ] Usage Notes;
- [ ] manuscript figures;
- [ ] dataset DOI plan;
- [ ] code DOI plan.

---

# 34. First action for the AI agent

Begin by creating the project folder structure and then run **only the inventory phase**.

The first substantive deliverable should be:

```text
A:\_BioGeo\liuxianx\phenology_project\00_admin\data_inventory_summary.md
```

plus:

```text
A:\_BioGeo\liuxianx\phenology_project\03_inventory\raster_inventory.csv
A:\_BioGeo\liuxianx\phenology_project\03_inventory\raster_inventory.parquet
```

After inventory, create a short decision note in:

```text
A:\_BioGeo\liuxianx\phenology_project\00_admin\decisions_log.md
```

containing:

1. discovered source file structure;
2. discovered naming convention;
3. date parser;
4. grid structure;
5. EVI storage/scaling conclusion;
6. missing/duplicate data;
7. proposed chunking strategy;
8. any blocking problem.

Then proceed to the CDTS synthetic/leap-year verification and pilot workflow.

---

# 35. Final principle

The central deliverable is not merely a collection of SOS/EOS rasters. All script should be simple, easy to understand, remove unneccery founctions.

It is a **scientifically defensible European phenology data product** whose processing history, limitations, quality, uncertainty, validation, and software environment are sufficiently documented that another researcher can understand, reuse, and reproduce it.
