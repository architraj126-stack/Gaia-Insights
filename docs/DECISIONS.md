# Architecture Decisions & Research Log

This log records non-obvious engineering decisions, data source investigations, and research findings for the Earth Science Explorer project.

---

## ADR-001: NOAA PSL GPCP V2.3 Access and Time/Fill Metadata Quirks

**Date:** 2026-11-13  
**Status:** Accepted  
**Context:**  
Phase 0 requires a data-access spike (`backend/scripts/spike_gpcp.py`) accessing the NOAA PSL GPCP V2.3 monthly precipitation NetCDF without hardcoding or guessing URLs, and documenting dimensions, variable names, units, time boundaries, and missing-value conventions.

### Discovery & Findings
1. **Dynamic Catalog Discovery:**
   - Source page: `https://www.psl.noaa.gov/data/gridded/data.gpcp.html`
   - Page embeds `datasetID = 44`.
   - Querying NOAA PSL metadata API:
     - Variable API: `https://www.psl.noaa.gov/cgi-bin/mddb2/mddb2.py?action=getVariables&datasetID=44`
     - Identified Monthly Mean Precipitation: Variable ID `1631`, path `/Datasets/gpcp`.
     - File API: `https://www.psl.noaa.gov/cgi-bin/mddb2/mddb2.py?action=getVariableFiles&variableID=1631`
     - Discovered filename: `precip.mon.mean.nc`.
   - Canonical URLs:
     - **OPeNDAP**: `https://psl.noaa.gov/thredds/dodsC/Datasets/gpcp/precip.mon.mean.nc`
     - **HTTP Direct Download**: `https://downloads.psl.noaa.gov/Datasets/gpcp/precip.mon.mean.nc`
     - **THREDDS Catalog**: `https://www.psl.noaa.gov/thredds/catalog/Datasets/gpcp/catalog.html?dataset=Datasets/gpcp/precip.mon.mean.nc`

2. **Dataset Properties & Dimensions:**
   - **Dimensions:** `time: 574`, `nv: 2`, `lat: 72`, `lon: 144`
   - **Spatial Resolution:** $2.5^\circ \times 2.5^\circ$ global grid (72 latitudes from $90^\circ\text{N}$ to $-90^\circ\text{S}$, 144 longitudes from $0^\circ\text{E}$ to $357.5^\circ\text{E}$)
   - **Primary Variable:** `precip` (Long Name: "Average Monthly Rate of Precipitation", Var Desc: "Precipitation")
   - **Units:** `mm/day` (rate variable requiring accumulation by days in month when computing monthly totals, as mandated by Scientific Rule 7)
   - **Temporal Range:**
     - Raw units: `days since 1800-1-1 00:00:0.0`
     - First time step: `1979-01-01`
     - Latest complete observation date: `2026-10-01` (574 monthly observations)

3. **Critical Encoding & Xarray Parsing Anomaly:**
   - Standard `xr.open_dataset(..., decode_times=True)` fails with `OutOfBoundsTimedelta` because the auxiliary variable `time_bnds` contains:
     - An unmasked fill value `9.96921e+36` (standard `NC_FILL_FLOAT`).
     - A malformed unit string `'days since 1800-01-01 00:00:00 0:00'` containing redundant `:00`.
     - Without explicit `_FillValue` on `time_bnds`, pandas tries to interpret `9.96921e+36` as days since 1800, exceeding 64-bit nanosecond timestamp bounds.
   - **Solution:** Open datasets with `decode_times=False` and decode the coordinate `time` explicitly using `cftime.num2date(ds['time'].values, ds['time'].attrs['units'])`.

4. **Missing-Value Convention:**
   - Missing-value indicator: `-9.96921e+36` (`encoding['missing_value']`).
   - Valid range: `[0.0, 100.0]`. Actual range: `[0.0, 47.327435]`.
   - **Enforcement:** In accordance with Scientific Rule 3 ("Decode fill values to NaN. Missing is never zero. Never interpolate silently"), all values $\le -9.0\times 10^{36}$ or outside valid range are decoded strictly to `NaN`.

---

## ADR-002: Backend Architecture & Secret Safety

**Date:** 2026-11-13  
**Status:** Accepted  
**Context:**  
Phase 0 requires a FastAPI backend with structured logging, CORS for frontend dev server, config via `pydantic-settings`, and strict prevention of credential leaks (Scientific Rule 11).

### Decisions
1. **Configuration:** Centralized in `backend/app/config.py` using `pydantic_settings.BaseSettings`, reading from `.env` with fallback defaults.
2. **Structured Logging (`backend/app/logging.py`):**
   - Outputs JSON log records.
   - Integrates recursive redaction filter (`redact_sensitive_value`) that scrubs dictionary keys and string patterns matching passwords, API keys, tokens, auth headers, and URI connection strings.
   - Verified via unit test `backend/tests/test_config.py::test_json_formatter_never_leaks_secrets`.
3. **API Contracts:**
   - `GET /health`: Returns service health and environment.
   - `GET /api/catalog/variables`: Returns variables and datasets.

---

## ADR-003: Frontend State Management and Invalidation Rules

**Date:** 2026-11-13  
**Status:** Accepted  
**Context:**  
SPEC 13.1 and 13.3 mandate a unified client store (`AnalysisSession`) with strict downstream invalidation rules.

### Decisions
1. **Zustand with LocalStorage Persistence:**
   - Store `useSession` manages `AnalysisSession` with `persist` middleware key `earth-science-session-storage`.
2. **Invalidation Pipeline:**
   - Modifying `selectedVariables`, `dateRange`, `frequency`, or `region` automatically clears `page3ResultId`, `page4ResultId`, and `page5ResultId`.
   - Dedicated invalidation helper function `invalidateDownstreamResults` isolated and unit-tested in `frontend/src/store/session.test.ts`.

---

## ADR-004: Phase 1 Catalog Seed and Truthful Null-Field Policy

**Date:** 2026-11-13  
**Status:** Accepted  
**Context:**  
Phase 1 onboarding requires seeding the curated precipitation variable with dataset `gpcp_monthly_v23` via `backend/catalog/seed/precipitation.yaml` and serving it through FastAPI endpoints `GET /api/catalog/variables` and `GET /api/catalog/datasets?variable=`.

### Decisions
1. **Pydantic-Enforced YAML Seed:**
   - Seed YAML files in `backend/catalog/seed/` are loaded dynamically and strictly validated against `VariableModel` and `DatasetModel`.
   - Contains NOAA PSL GPCP V2.3 metadata verified directly from the data-access spike and PSL dataset specifications.
2. **Scientific Truthfulness & Zero Hallucination (Rule 1 & Rule 5):**
   - In adherence to Rule 5, `latest_observation_date` is populated strictly from the actual dataset time coordinate at runtime and never from file/catalog modified date.
   - Any attribute not directly verified on the official page/spike output (e.g., DOI, update latency) is set to `null` with an accompanying status `"Needs validation"`.
   - `fill_value` is set to `-9.96921e+36` with explicit mask semantics documented in the seed.

---

## ADR-005: Geographic Explorer Boundary Bundling, Geodesics, and Antimeridian Normalization

**Date:** 2026-11-13  
**Status:** Accepted  
**Context:**  
Phase 2 implements Page 2 (Geographic Explorer) per SPEC 7 and 11.3, enabling spatial region selection (Admin-0 countries, Admin-1 states/provinces, custom hand-drawn polygons, rectangles, and point + buffer), geometry validation and repair, and dataset availability evaluations.

### Decisions & Engineering Architecture
1. **Bundled Natural Earth Boundaries (`backend/data/boundaries/`):**
   - Bundled Natural Earth 110m Admin-0 Countries (`admin_0.geojson`, 177 features, ~480 KB) and 10m simplified Admin-1 States/Provinces (`admin_1.geojson`, 4596 features, ~7.7 MB) with full public domain license and attribution in `LICENSE.md`.
   - Indexed in memory upon startup for sub-millisecond search (`GET /api/regions/search?q=`) and geometry extraction (`GET /api/regions/{id}/geometry`).
2. **Geometry Normalization & Antimeridian Splitting (`backend/app/services/geometry.py`):**
   - Geometries crossing the antimeridian (180°/-180°), such as Fiji, Chukotka, or custom hand-drawn rectangles across the Pacific, are detected by coordinate jumps $|\Delta\text{lon}| > 180^\circ$.
   - The ring coordinates are unwrapped into a continuous longitude domain, split along the 180° meridian, and re-normalized back to $[-180, 180]$ as a valid `MultiPolygon`.
   - Self-intersecting geometries (e.g. bowtie polygons) are automatically repaired using `shapely.validation.make_valid` with an informative warning.
3. **Geodesic Metric Computations (Rule 6):**
   - Accurate geodesic area is computed on the WGS84 ellipsoid via `pyproj.Geod(ellps="WGS84")`, preventing latitude-dependent distortion of planar degrees.
   - Point + buffer mode generates true geodesic polygons on the ellipsoid using forward geodesic projection (`geod.fwd`).
4. **Spatial & Temporal Dataset Availability (`backend/app/services/availability.py`):**
   - Evaluates declared grid cell size against the region: calculates cell count by testing grid cell center containment.
   - Issues scientific warnings if a region is significantly smaller than a grid cell or contains 0 or fewer than 4 cell centers.
5. **Frontend 3-Column Responsive Architecture (`frontend/src/pages/RegionPage.tsx`):**
   - Layout follows 23% / 52% / 25% on desktop and stacked on mobile.
   - Left: Mode switcher, administrative search, point + buffer inputs, Page 1 variable context card.
   - Centre: Leaflet map with base-map switcher (Street, Satellite, Terrain), Leaflet-Geoman draw/edit/delete tools, and geometry outline rendering.
   - Right: Region name, type, geodesic area, bounding box, centroid, per-variable availability status chips, and scientific warnings.
   - Region confirmation updates Zustand store (`AnalysisRegion`) and automatically invalidates downstream results per SPEC 13.3.

---

## ADR-006: Phase 3a — SQLAlchemy ORM, Alembic Migrations, and Dataset Registry

**Date:** 2026-11-13  
**Status:** Accepted  
**Context:**  
Phase 3a requires a database-backed dataset registry (SPEC 13.2, 6.2) with provenance tracking, latest-observation logic, and a protected refresh endpoint.

### Decisions & Engineering Architecture
1. **SQLAlchemy 2.x (async) + asyncpg:**
   - All DB interactions use `AsyncSession` via `sqlalchemy[asyncio]` + `asyncpg`.
   - Engine created once at module import time with `pool_pre_ping=True`.
   - `expire_on_commit=False` to prevent lazy-load failures after `session.commit()`.

2. **9 ORM Tables (SPEC 13.2 + additions):**
   - `variables`, `dataset_products`, `dataset_fields`, `regions`, `analysis_runs`, `analysis_outputs`, `reports`, `jobs`, `provenance_events`.
   - `dataset_products` stores every field required by SPEC 6.2 (provider, short name, version, DOI, native field, units, valid range, fill value, grid and CRS, coverage, temporal/spatial resolution, update latency, citation, access URL, licence notes, known limitations, no-data semantics).
   - Multi-dialect JSON support: `sa.JSON().with_variant(postgresql.JSONB, "postgresql")` ensures full native PostgreSQL JSONB support in production while allowing SQLite in-memory testing.
   - `provenance_events` is an append-only audit log; never updated, never deleted (SPEC 6.4).

3. **Two separate timestamps per SPEC 15.3:**
   - `latest_observation_date` (Python `date`) — the data's own time coordinate date.
   - `last_catalogue_check` (Python `datetime` with tz) — UTC wall-clock of when the backend queried the source.
   - The old `latest_observation_status = "Not yet checked"` string is removed from the API; the two timestamps replace it.

4. **Latest-observation logic (SPEC 6.3):**
   - Opens OPeNDAP / HTTP NetCDF with `decode_times=False` (ADR-001 cftime fix).
   - Decodes time coordinate with `cftime.num2date`.
   - A step is "complete" when `UTC now > first instant of the NEXT month after the step`.
   - If the final step is the in-progress current month, the previous step is returned.
   - Logic extracted into `find_latest_complete_month()` for pure-function testing.

5. **Idempotent seeding:**
   - `seed_catalog()` upserts (INSERT or UPDATE) on every startup from `backend/catalog/seed/*.yaml`.
   - Version changes during re-seed trigger a `ProvenanceEvent(event_type='version_change')` before updating the row, ensuring history is never overwritten.
   - Re-seeding the same version never produces duplicate provenance events.

6. **DB fallback in catalog API:**
   - `catalog.py` queries PostgreSQL first; on connection exception it transparently falls back to YAML seed.
   - Prevents startup crashes when PostgreSQL is not running (dev/CI environments).

7. **Alembic migration (revision 0001):**
   - Script at `alembic/versions/0001_initial.py` creates all 9 tables.
   - `alembic.ini` and `env.py` support environment URL overrides (`DATABASE_URL`).
   - Verified clean upgrade to `head`, downgrade to `base`, and re-upgrade via `backend/tests/test_migrations.py`.

8. **Admin refresh endpoint:**
   - `POST /api/admin/catalog/refresh` (optional `?dataset_id=`).
   - Protected by `ADMIN_TOKEN` from `.env` using `hmac.compare_digest` (constant-time).
   - Called at startup AND available for manual on-demand refresh.

9. **Frontend updates (Page 1 & Page 2):**
   - `catalog.ts`: replaced `latest_observation_status` with `latest_observation_date` + `last_catalogue_check` helper functions `formatObservationDate` and `formatCatalogueCheck`.
   - `ExplorePage.tsx` (Page 1): "Not yet checked" placeholder removed. Displays real latest complete observation date and separate "last catalogue check" time in both configuration card and specifications drawer.
   - `RegionPage.tsx` (Page 2): Availability panel now displays `Date Coverage: start → latest_observation_date` and `Last catalogue check: timestamp`, eliminating `*Latest date status: Not yet checked`.

---

## ADR-007: Phase 3b - GPCP Time-Series Pipeline, Spatial Masking, and Provenance

**Date:** 2026-11-13  
**Status:** Accepted  
**Context:**  
Phase 3b requires a production-grade time-series pipeline for GPCP V2.3 monthly precipitation adhering to SPEC sections 12, 14, 15.1, 15.4, 16.3 and scientific non-negotiables (area-weighting, fill value NaN decoding, precipitation accumulation with leap-year awareness, missing-step auditing, and deterministic subset caching).

### Decisions & Architecture

1. **Lazy Ingestion and Grid Normalization (`services/ingest.py`):**
   - Coordinates: Longitudes normalised from $[0, 360)$ to $[-180, 180)$. Spatial coordinates (`lat`, `lon`) sorted ascending to enable fast bounding box slicing.
   - Time decoding: Parsed via `cftime.num2date` to avoid pandas 64-bit nanosecond overflow (ADR-001).
   - Missing/Fill values: Values $\le -9.0\times 10^{36}$ or outside $[0.0, 100.0]$ are decoded strictly to `NaN` (Scientific Rule 3).
   - Expected steps auditing: Evaluates continuous monthly sequence between requested start and end dates. Any gap in observation time steps is explicitly surfaced in `missing_steps` and warned in the response.

2. **Spatial Masking and Area-Weighting (`services/regions.py`):**
   - Geodesic Cell Area: Computed using spherical authalic formula $A = R^2 \cdot \Delta\lambda_{\text{rad}} \cdot |\sin(\phi_2) - \sin(\phi_1)|$ with $R = 6371.0088\text{ km}$ (Scientific Rule 6).
   - Fractional Overlap: Intersects each grid cell bounding box against the target geometry using Shapely `intersection() / cell_nominal_area`. Falls back to cell-centre containment only if geometric intersection encounters topological errors.
   - Valid area & cell count tracking: Every time step computes valid cell count and valid area ($\text{km}^2$), taking `NaN` cells into account so that missing pixels do not distort the denominator.

3. **Temporal Aggregation (`services/aggregate.py`):**
   - Monthly accumulation: Daily precipitation rate ($\text{mm/day}$) is multiplied by exact days in calendar month using Python's `calendar.monthrange(year, month)` to strictly handle leap years (e.g. Feb 1992 has 29 days vs Feb 1990 has 28 days).
   - Annual aggregation: Sum of all 12 valid calendar months. If any single month is missing or `NaN`, the annual total is set to `None`/`NaN` with an explicit `incomplete_year` flag.
   - Seasonal aggregation: DJF, MAM, JJA, and SON require all 3 constituent months to be valid; otherwise `None`/`NaN` with an incomplete flag.

4. **Deterministic Subset Caching & Provenance (`api/analysis.py`):**
   - Cache key: SHA-256 hash of `collection + version + start_date + end_date + geom_hash + processing_settings`. Subsets are cached under `data/cache/subsets/{cache_key}.json`.
   - Results: Full time series points, summary statistics, and SPEC 15.4 provenance are persisted under `data/cache/results/series_{run_id}.json` and mirrored in the database (`AnalysisRun`, `AnalysisOutput`, `Job`).
   - SPEC 12.3 response shape returned to client with `job_id`, `status: "completed"`, `coverage`, `series_url`, `summary`, and `warnings`.
   - Error handling: In the event of provider unreachability, the pipeline returns a failed job status with the provider's exact error message.



---

## ADR-008: Phase 4 — Trend Analysis Engine, Analytical Confidence Bands, and Unified Series Derivation

**Date:** 2026-11-13  
**Status:** Accepted  
**Context:**  
Phase 4 implements Page 3 (Trend Analysis) per SPEC sections 8, 14.6, and scientific non-negotiables (honest empty/gap states, no silent interpolation, analytical confidence bands strictly from the regression itself, non-parametric Theil-Sen robust slopes, serial autocorrelation corrections via Hamed-Rao modified Mann-Kendall, and unified series derivation across chart, table, and metrics).

### Decisions & Mathematical Architecture

1. **Statistical Trend Pipeline (`backend/app/services/trends.py`):**
   - **OLS Linear Regression:** Computes slope, intercept, standard error, $R^2$, and $p$-value using continuous decimal time coordinates. Slope is reported in native units per year ($\text{units/year}$).
   - **Analytical Regression Confidence Band:** Evaluated strictly from linear regression theory (Working-Hotelling / pointwise confidence band for $E[Y|X=x_0]$):
     $$SE(x_0) = s_e \sqrt{\frac{1}{n} + \frac{(x_0 - \bar{x})^2}{S_{xx}}}$$
     $$CI(x_0) = \hat{y}(x_0) \pm t_{1 - \alpha/2, n-2} \cdot SE(x_0)$$
     Never uses an arbitrary or constant $\pm$ offset.
   - **Non-Parametric Theil-Sen Estimator:** Computes median pairwise slopes and non-parametric rank-based confidence interval via `scipy.stats.theilslopes` with confidence degree $1 - \alpha$.
   - **Mann-Kendall & Seasonal Mann-Kendall:** Tests for monotonic trend without normality assumptions. Seasonal Mann-Kendall groups observations by month ($\text{period}=12$) or season ($\text{period}=4$) to avoid confounding seasonality with trend.
   - **Autocorrelation-Aware Modified Mann-Kendall:** Implements Hamed & Rao (1998) variance correction via `pymannkendall.hamed_rao_modification_test`, adjusting test statistic variance upward for positively correlated AR(1) processes to eliminate inflated false significance.
   - **Config-Driven Thresholds:** Trend direction classification (`increasing`, `decreasing`, `no clear trend`, `insufficient data`) enforces `TREND_ALPHA` (0.05) and minimum observation threshold `TREND_MIN_DATA_POINTS` (12) from `Settings`.

2. **Single Series Derivation Rule:**
   - `analyze_timeseries_trends` enriches each series point with `fitted_ols`, `ols_ci_lower`, `ols_ci_upper`, `sens_line`, and `moving_avg`, and outputs the top-level `summary` metrics from the exact same data vector.
   - Both `points` and `summary` are stored in `series_{run_id}.json` and returned by `POST /api/analysis/timeseries`.
   - The Plotly chart, virtual data table, and summary metrics cards all consume this identical series object, guaranteed by unit test `test_unified_series_derivation` and Vitest component test `asserts that chart, table, and metrics all derive from one series object`.

3. **Gap Preservation (Scientific Rule 3):**
   - Plotly is strictly configured with `connectgaps: false`. Missing months (due to missing timestamps or masked cells) evaluate to `NaN` and are never interpolated silently.
   - Verified via Playwright screenshot `docs/screenshots/phase4_trends_gap.png` showing a visible gap in the time series trace and corresponding `NaN (gap)` / `Missing` status in the expandable virtual table.

4. **Frontend 3-Column Responsive Architecture (`frontend/src/pages/TrendsPage.tsx`):**
   - Follows 23% / 52% / 25% column layout on desktop and stacked on mobile.
   - Left: Variable context, read-only region link back to Page 2, clamped date range, aggregation selector (Monthly/Annual/Seasonal), and chart display toggles.
   - Centre: Plotly chart with interactive zoom/reset, PNG and CSV exports, stale-result recalculation banner, and expandable virtualised data table.
   - Right: SPEC 8.5 summary metrics (direction chip, rate of change with OLS/Sen's toggle and CI, average value, estimated total change, completeness with denominator, and significance test statistics).

---

## ADR-009: Phase 5 — Change Detection Engine, Georeferenced Differencing, and Diverging Visualization

**Date:** 2026-11-13  
**Status:** Accepted  
**Context:**  
Phase 5 implements Page 4 (Change Detection) per SPEC sections 9, 14.5, and 14.8. Requirements include computing per-cell baseline value $A$ and comparison value $B$ with consistent temporal aggregation, absolute and percentage change calculations, distinct spatial trend metrics, georeferenced GeoTIFF/COG generation via `rioxarray`, transparent PNG map overlays for Leaflet, diverging symmetric colormap legends, area-weighted spatial summaries, and strict adherence to SPEC 9.8 (prohibition of the word "significant" on Page 4).

### Decisions & Architecture

1. **Consistent Temporal Aggregation (`backend/app/services/change.py`):**
   - **Symmetric Rule Application:** Both baseline and comparison periods use identical temporal aggregation routines. For precipitation rate ($\text{mm/day}$), each month is converted to monthly accumulation via exact calendar days (accounting for leap years) and summed to annual totals ($\text{mm/year}$). If any of the 12 calendar months is missing or `NaN`, that cell's annual total for that year evaluates strictly to `NaN`.
   - **Period Temporal Means:** $A(i, j)$ and $B(i, j)$ are computed as the temporal mean across valid years within the respective period. Missing cells remain `NaN` everywhere; zero is never substituted.

2. **Metric Formulations & Stability Guards:**
   - **Absolute Change:** $\Delta(i, j) = B(i, j) - A(i, j)$, matching native units ($\text{mm/year}$).
   - **Percentage Change:** $100 \times (B - A) / |A|$, evaluated strictly where $|A| > \epsilon$ ($\epsilon = 1.0\text{ mm/year}$). Where $|A| \le \epsilon$ or is `NaN`, the result is set to `NaN` and an explicit warning is attached to prevent misleading mathematical explosions in arid or zero-baseline regions (SPEC 14.5, SPEC 9.7).
   - **Spatial Trend:** Computed as the per-cell ordinary least squares regression slope per year across the full span of valid years, distinct from the two-period difference, with units of $\text{units/year}$.

3. **Period Validation & Overlap Constraints:**
   - Baseline default is 1990–2005; comparison default is 2006–2025 (latest complete observation year).
   - Both periods are validated against actual dataset temporal coverage.
   - Overlapping periods are rejected with an explicit error unless the user activates `allow_overlap = True` under explicit confirmation.

4. **Raster Generation & Diverging Visualization:**
   - **GeoTIFF Export:** Uses `rioxarray` to generate georeferenced EPSG:4326 GeoTIFF files under `data/outputs/change_{run_id}.tif` with spatial bounds, coordinate orientation, and nodata tags.
   - **Leaflet Transparent PNG Overlay:** Renders a 32-bit RGBA image (`overlay_{run_id}.png`) using the `RdBu_r` diverging colormap (blue for negative decrease, white/neutral for zero, red for positive increase). Unselected or `NaN` cells are rendered completely transparent ($\alpha = 0$) so the underlying base map and topography show through.
   - **Symmetric Colormap Legend:** Centered at zero $[-M, +M]$ where $M = \max(|v_{\text{valid}}|)$ with threshold tick marks, matching units, and a dedicated gray swatch (`#9ca3af`) for No Data / Unsampled areas so that missing data is visibly distinct from zero change.

5. **Spatial Summary (SPEC 9.6):**
   - Computes area-weighted mean change using geodesic cell areas scaled by $\cos(\text{latitude})$ and fractional polygon overlap weights.
   - Computes valid area shares: increasing ($\Delta > 0$), decreasing ($\Delta < 0$), and stable ($\Delta = 0$).
   - Identifies highest and lowest change extremes with cell latitude and longitude coordinates.
   - Reports no-data / unsampled area ($\text{km}^2$ and $\%$ of study region) strictly separately from the stable/no-change area.

6. **Cell-Inspect Endpoint (`GET/POST /api/analysis/change-map/inspect`):**
   - Allows users to click any location on the map to query the underlying cell coordinates, baseline mean, comparison mean, difference, overlap fraction, and validity status.

7. **SPEC 9.8 Non-Negotiable Compliance:**
   - The word "significant" is strictly forbidden on Page 4 (enforced in unit test `ChangesPage.test.tsx`). Page 4 displays observed spatial differences; formal statistical significance testing and multiple testing corrections (FDR) are deferred to Page 5.

---

## ADR-010: Phase 6a — Inferential Significance Engine, FDR Spatial Multiple-Testing, and Accessible Hypothesis Visualization

**Date:** 2026-11-13  
**Status:** Accepted  
**Context:**  
Phase 6a implements Page 5 (Significance & Reports) per SPEC sections 10.1–10.6, 14.6–14.8, and Scientific Rules 8, 9, 10. Statistical significance must never be inferred from a spatial difference raster; it must evaluate the underlying sequence of historical observations. High spatial test multiplicity requires rigorous False Discovery Rate (FDR) control, accessible 5-class categorization (never color alone), empirical autocorrelation correction, fast caching for parameter reclassification, and plain-language interpretations that avoid common statistical fallacies.

### Decisions & Architecture

1. **Regional Hypothesis Testing (`backend/app/services/significance.py`):**
   - **Seasonal Mann-Kendall vs Mann-Kendall:** Defaults to Seasonal Mann-Kendall (`pymannkendall.seasonal_test`, $\text{period}=12$) for monthly regional series and standard Mann-Kendall for annual series, avoiding confounding seasonality with long-term monotonic trends.
   - **Empirical Lag-1 Autocorrelation & Correction:** Evaluates $r_1 = \sum (y_t - \bar{y})(y_{t+1} - \bar{y}) / \sum (y_t - \bar{y})^2$. If $r_1 > 0.10$, Hamed & Rao (1998) variance correction is applied to eliminate false discovery inflation caused by positive serial persistence.
   - **Analytical Rank-Based Confidence Intervals:** Computes Theil-Sen median slope alongside 95% non-parametric confidence limits based on normal approximation order statistics, rigorously verified by Monte Carlo coverage simulations.
   - **Documented Rationale:** Emits explicit test name, formal null hypothesis in words, test statistic, p-value, sample size $n$, and adjustment documentation.

2. **Vectorised Spatial Grid Testing & Benjamini-Hochberg FDR:**
   - **Sub-Second Vectorisation:** Employs NumPy upper-triangular indexing `np.triu_indices(T, k=1)` on stacked `(T, N)` arrays. Calculates pairwise differences, Kendall $S$ score, variance, and median Sen slopes across all 10,368 grid cells in under 0.3 seconds on CPU.
   - **Minimum-Data Rule:** Requires $\ge 10$ valid annual observations per cell (configurable). Cells with fewer valid points are classified as `Insufficient Data`.
   - **Benjamini-Hochberg FDR (`fdr_bh`):** Runs `statsmodels.stats.multitest.multipletests` strictly over tested cells ($p_{\text{raw}}$ valid), bounding the expected proportion of false positive discoveries at $\alpha = 0.05$.
   - **5 Discrete Spatial Classes (SPEC 10.4):**
     1. `Significant Increase` ($p_{\text{adj}} < \alpha, \text{slope} > 0$): Symbol `+`, blue `#0284c7`.
     2. `Significant Decrease` ($p_{\text{adj}} < \alpha, \text{slope} < 0$): Symbol `−`, orange `#ea580c`.
     3. `Not Significant` ($p_{\text{adj}} \ge \alpha$): Symbol `o`, neutral gray `#94a3b8`.
     4. `Insufficient Data` ($n < \text{threshold}$): Symbol `?`, yellow `#facc15`.
     5. `Not Covered` (outside mask/study area): Symbol `x`, dark transparent `#334155`.
   - **Independent Cache & Fast Reclassification:** Stores raw $p$-values and slopes in `data/outputs/spatial_cache_{run_id}.json`. When the user toggles $\alpha$ or FDR, `reclassify_cached_significance` updates the classification and regenerates the GeoTIFF and PNG overlay in $<50$ms without re-running data extraction or regressions.

3. **Frontend Accessible Interface (`frontend/src/pages/SignificancePage.tsx`):**
   - **Layout (SPEC 10.1):** 3-column architecture (23% / 52% / 25%) with expandable methodology drawer.
   - **Accessible Legend (Rule 11):** Each class features distinct high-contrast symbols (`+`, `−`, `o`, `?`, `x`), patterns, text descriptions, and cell counts, ensuring meaning is never conveyed by color alone.
   - **Multiple-Testing State Badge:** Clearly labels whether the map displays `Benjamini-Hochberg FDR Adjusted` or `Raw (Uncorrected)` p-values.
   - **SPEC 10.5 & 10.6 Plain-Language Interpretations:** Explicitly warns the user that:
     1. A p-value is *not* the probability that the null hypothesis is true.
     2. Statistical significance *does not* equal large environmental importance or magnitude.
     3. An observed statistical trend *does not* prove a causal mechanism.

---

## ADR-012: Phase 7 — Land Surface Temperature Variable Ingestion, MERRA-2 Integration, State Aggregation, and Land/Ocean Masking

**Date:** 2026-11-13  
**Status:** Accepted  
**Context:**  
Phase 7 adds the second scientific variable: Land Surface Temperature, using NASA's MERRA-2 skin temperature `TS` from the monthly single-level assimilation collection (`instM_2d_asm_Nx` / `M2IMNXASM`). Per SPEC sections 6.1–6.4, 14.1–14.4, 15.2, and Scientific Rules 1–11, all metadata must be verified against official sources (with unverified properties remaining null / "Needs validation"), aggregation must adhere to intensive state variable rules (mean, never sum), units must convert from Kelvin to Celsius while keeping native provenance, land-only variables must strictly exclude ocean values, and specific caveats must be presented across Pages 1, 2, and in the scientific audit report.

### Decisions & Architecture

1. **Official Verification & Catalog Registration (`backend/catalog/seed/temperature.yaml`):**
   - **Product Collection:** `M2IMNXASM` / `instM_2d_asm_Nx` (Collection ID: `C1276812823-GES_DISC`).
   - **DOI:** `10.5067/5ESKGQTZG7FO` (verified via NASA CMR UMM-JSON metadata).
   - **Version:** `5.12.4`.
   - **Native Variable:** `TS` (Surface skin temperature).
   - **Units:** `K` (Kelvin).
   - **Fill Value:** `1.0e15` (decoded to NaN upon ingestion; missing is never zero per Rule 3).
   - **Grid:** Regular lat-lon grid, 0.625° lon × 0.5° lat (576 × 361 cells), EPSG:4326.
   - **Time Coverage:** `1980-01-01` to present.
   - **Unverified Field:** `update_latency` remains `null` with status `"Needs validation"`.
   - **Seed & Database:** Seeded in `backend/catalog/seed/temperature.yaml` and loaded into `variables`, `dataset_products`, and `dataset_fields`. `precipitation` is sorted first to ensure backward compatibility for existing tests.

2. **Aggregation Rule for State Variables (SPEC 14.3, Rule 7):**
   - Unlike flux/rate variables (such as precipitation rate in mm/day accumulated by days in month), temperature is an intensive state variable.
   - Monthly values are arithmetic means. Annual and seasonal aggregations are computed as the temporal mean of valid monthly observations (never summed or accumulated).
   - Flagged with `aggregation_semantics: state_mean_time_weighted` in `dataset_fields`.

3. **Unit Conversion Rule (SPEC 14.4):**
   - Native values in Kelvin ($K$) are converted to degrees Celsius ($^\circ\text{C}$) via $T_{^\circ\text{C}} = T_K - 273.15$.
   - Display and analytical outputs present values in $^\circ\text{C}$ (and trends in $^\circ\text{C}/\text{year}$).
   - Provenance records both native units ($K$) and conversion formula ($^\circ\text{C} = K - 273.15$).

4. **Land/Ocean Coverage Enforcement (SPEC 14.2):**
   - `coverage_type: land_only` is enforced across availability, regional extraction, and spatial change analysis.
   - Using Natural Earth land boundaries (`admin_0.geojson` with unary union), ocean cells outside terrestrial land polygons are masked to `NaN` and assigned zero weight in regional integrals. No ocean values are permitted.
   - For study regions over oceans, availability evaluates to `Unavailable` ($0\%$ land coverage). Coastal regions evaluate to `Partial` ($< 99.5\%$ land coverage) with warning chips detailing non-terrestrial exclusion.

5. **Credentials & Backend Ingestion (`backend/app/config.py`, `backend/app/services/ingest.py`):**
   - NASA Earthdata credentials (`EARTHDATA_TOKEN`, `EARTHDATA_USERNAME`, `EARTHDATA_PASSWORD`) reside strictly in backend `.env` (Scientific Rule 11) and are never exposed or logged.
   - Ingestion dispatcher `open_dataset` and `normalize_dataset` dynamically select between GPCP and MERRA-2.
   - Local compressed cache (`data/cache/merra2_ts.mon.mean.nc`) provides deterministic offline support for testing.

6. **Specific Caveats Surfaced Across UI & Reports:**
   - **Caveat Text:** *"This is a reanalysis/model surface skin temperature diagnostic from MERRA-2 assimilation, not MODIS satellite land-surface temperature. Model land-surface diagnostics reflect simulated surface equilibrium rather than direct radiometric measurements."*
   - Displayed prominently in:
     - **Page 1 (Data Explorer):** Variable selection cards and Selection Summary card.
     - **Page 2 (Geographic Explorer):** Primary variable card and Dataset Availability panel.
     - **Report (PDF & Web View):** Section 2 (Dataset and Study Area) dynamic grid resolution (0.625° × 0.5°) and Section 6 (Data Quality & Limitations) caveat callout.


**Date:** 2026-11-13  
**Status:** Accepted  
**Context:**  
Phase 6b implements the multi-page scientific audit report generator and export pipeline (SPEC sections 10.7, 10.8, 15.4, 17.3, Scientific Rules 1, 9, 10). The report must synthesize findings across Page 3 (Trends), Page 4 (Change Detection), and Page 5 (Significance), enforce strict dataset/region/date consistency, guarantee that every numeric finding matches stored runs with zero typed or recomputed numbers, and deliver production-grade PDF and CSV exports alongside citations, DOIs, access dates, and code versions.

### Decisions & Architecture

1. **PDF Engine Selection — ReportLab over WeasyPrint:**
   - **Rationale:** ReportLab 5.1.0 is pure-Python, cross-platform compatible on Windows, and executes in $<1.5$ seconds with zero external GTK/Pango C-library dependencies.
   - **Document Architecture:** Utilizes `reportlab.platypus.SimpleDocTemplate` combined with a two-pass `NumberedCanvas` to calculate total pages dynamically and render running headers and "Page X of Y" footers on every page.
   - **Visual Styling:** Adheres to NASA Earth Science Explorer design language with dark navy section banners (`#0f172a`), slate accents, high-contrast typography, styled tables, callout caution boxes, embedded timeseries plots, and map overlays.

2. **Single Source of Truth & Golden Numbers (Scientific Rule 1):**
   - **Zero Recomputations:** `reports.py` ingests stored run artifacts directly from `OUTPUTS_DIR` and `RESULTS_CACHE_DIR`. It never recomputes or approximates numbers.
   - **Template-Driven Executive Summary:** Paragraphs are assembled using deterministic parameter templates populated with exact stored numbers. Free-written, unsubstantiated assertions are strictly prohibited.
   - **Golden Test Verification:** Unit test `test_golden_report_numbers_equal_api_numbers_for_same_run` and end-to-end Playwright run verify that every number in the PDF (regional mean, Sen's slope, OLS slope, area-weighted mean change, share increasing/decreasing, p-value, sample size) matches the stored API numbers verbatim.

3. **Strict Consistency Enforcement (Incompatible Run Rejection):**
   - `validate_runs_consistency` enforces cross-run compatibility:
     - **Dataset Version:** Refuses to combine runs with conflicting versions (e.g. `v2.3` vs `v3.0`).
     - **Study Area:** Compares geometry hashes and bounding boxes; refuses runs targeting different geographical extents.
     - **Temporal Coverage:** Validates that Page 4 comparison periods do not exceed Page 3 or Page 5 temporal coverage.

4. **Toggleable Modular Sections (SPEC 10.7):**
   - Supports 7 toggleable sections (all enabled by default):
     1. `Executive Summary`
     2. `Dataset and Study Area`
     3. `Historical Trend Analysis`
     4. `Spatial Change Detection`
     5. `Statistical Significance`
     6. `Data Quality & Limitations`
     7. `Methodology & References`

5. **Multi-Asset Export Endpoints (SPEC 10.8):**
   - `POST /api/reports`: Compiles report, builds PDF and CSV, returns download links.
   - `GET /api/reports/{id}`: Retrieves report JSON with live preview data.
   - `GET /api/reports/{id}/pdf`: Downloads compiled PDF (`earth_science_report_{id}.pdf`).
   - `GET /api/reports/{id}/csv`: Downloads structured time series CSV with units and quality flags.
   - `GET /api/reports/{id}/chart.png`: Serves high-resolution rendered timeseries plot.
   - Direct download links to Page 4 and Page 5 GeoTIFFs and transparent PNG overlays.

---

## ADR-013: Phase 7 — Sea Surface Temperature (NOAA OISST v2.1) Onboarding

**Date:** 2026-11-13  
**Status:** Accepted  
**Context:**  
Phase 7 requires adding the Sea Surface Temperature variable using NOAA OISST v2.1 (daily $0.25^\circ$, monthly mean collection). Metadata must be verified from official NOAA sources (THREDDS / PSL / NCEI), missing values decoded to NaN, state variable aggregation semantics applied, ocean-only domain coverage enforced (no land values), and caveats displayed across Page 1, Page 2, and the scientific report.

### Decisions & Architecture

1. **Official Verification & Catalog Registration (`backend/catalog/seed/sea_surface_temperature.yaml`):**
   - **Product Collection:** `noaa.oisst.v2.highres` / `OISSTv2.1`.
   - **Access Points:**
     - OPeNDAP: `https://psl.noaa.gov/thredds/dodsC/Datasets/noaa.oisst.v2.highres/sst.mon.mean.nc`
     - HTTP Download: `https://downloads.psl.noaa.gov/Datasets/noaa.oisst.v2.highres/sst.mon.mean.nc`
   - **DOI:** `10.25921/RE9P-PT57` (Huang et al., 2021).
   - **Version:** `v2.1` (display version `v2.1`, internal `2.1`).
   - **Native Variable:** `sst` (Monthly Mean of Sea Surface Temperature).
   - **Units:** `degC` (maps directly to display `°C` with no additive offset).
   - **Fill Value:** `-9.96921e36` (decoded to NaN upon ingestion per Scientific Rule 3).
   - **Valid Range:** `[-3.0, 45.0]` (actual observations range $-1.8^\circ\text{C}$ to $35^\circ\text{C}$).
   - **Grid:** Regular lat-lon grid, $0.25^\circ \times 0.25^\circ$ ($1440 \times 720$ cells), EPSG:4326.
   - **Time Coverage:** `1981-09-01` to present.
   - **Unverified Field:** `update_latency` remains `null` with status `"Needs validation"`.
   - **Seed & Database:** Registered in `backend/catalog/seed/sea_surface_temperature.yaml`.

2. **Aggregation Rule for State Variables (SPEC 14.3, Rule 7):**
   - Sea surface temperature is an intensive state variable.
   - Monthly values are temporal arithmetic means. Annual and seasonal aggregations are computed as the temporal mean of valid monthly observations (never summed or accumulated).
   - Flagged with `aggregation_semantics: state_mean_time_weighted` in `dataset_fields`.
   - Handled in `backend/app/services/aggregate.py` where `is_temp` includes `["sea_surface_temperature", "noaa_oisst_v21", "sst"]`.

3. **Ocean-Only Coverage Enforcement (SPEC 14.2):**
   - `coverage_type: ocean_only` is enforced across availability, regional extraction, and spatial change analysis.
   - Terrestrial land cells have no observations and are strictly masked to `NaN`. No land values are permitted.
   - For study regions over land (e.g. Chad), availability evaluates to `Unavailable` ($0\%$ ocean coverage). Coastal regions (e.g. Fiji) evaluate to `Partial` ($< 99.5\%$ ocean coverage) with warning chips detailing terrestrial exclusion. Pure ocean bounding boxes evaluate to `Available`.

4. **Specific Caveats Surfaced Across UI & Reports:**
   - **Caveat Text:** *"NOAA OISST v2.1 is an ocean-only blended product; terrestrial land cells have no observations and are strictly masked. Polar ice-covered oceans use a proxy freezing temperature of -1.8°C based on satellite sea-ice concentrations."*
   - Displayed prominently in:
     - **Page 1 (Data Explorer):** Variable selection cards and Selection Summary card.
     - **Page 2 (Geographic Explorer):** Primary variable card and Dataset Availability panel.
     - **Report (PDF & Web View):** Section 2 (Dataset and Study Area) dynamic grid resolution ($0.25^\circ \times 0.25^\circ$) and Section 6 (Data Quality & Limitations) caveat callout.

---

## ADR-015: Phase 7 — Humidity (MERRA-2 2-Meter Specific Humidity QV2M) Onboarding

**Date:** 2026-11-13  
**Status:** Accepted  
**Context:**  
Phase 7 requires adding the Humidity variable using MERRA-2 monthly reanalysis. Per SPEC 6.1, the product and field distinction must be rigorously maintained: specific humidity at 2 meters (`QV2M`), specific humidity at a named pressure level (`QV`), and total column precipitable water vapor (`TQV`) are distinct physical variables. Metadata must be officially verified, fill values decoded to NaN, state variable aggregation semantics applied, unit conversion rule implemented ($1\text{ kg/kg} = 1000\text{ g/kg}$), global atmospheric coverage enforced, and caveats displayed across Page 1, Page 2, and the scientific report.

### Decisions & Architecture

1. **Official Verification & Catalog Registration (`backend/catalog/seed/humidity.yaml`):**
   - **Product Collection:** `M2TMNXSLV` (Version `5.12.4`, Concept ID: `C1276812859-GES_DISC`).
   - **DOI:** `10.5067/AP1B0BA5PD2K` (Global Modeling and Assimilation Office, GMAO, 2015).
   - **Version:** `5.12.4` (consistent with MERRA-2 TS collection).
   - **Native Variable:** `QV2M` (2-meter specific humidity).
   - **Native Units:** `kg kg-1` (mass fraction).
   - **Display Units & Conversion:** `g/kg` ($q_{\text{g/kg}} = q_{\text{kg/kg}} \times 1000.0$, per SPEC 14.4).
   - **Fill Value:** `1.0e+15` (decoded strictly to `NaN` upon ingestion per Scientific Rule 3).
   - **Valid Range:** `[0.0, 0.1]` in native units, `[0.0, 100.0]` in display units ($\text{g/kg}$).
   - **Grid:** Regular lat-lon grid, $0.625^\circ \times 0.5^\circ$ ($576 \times 361$ cells, $-90.0^\circ$ to $90.0^\circ$ lat, $-180.0^\circ$ to $179.375^\circ$ lon), EPSG:4326.
   - **Time Coverage:** `1980-01-01` to present.
   - **Unverified Field:** `update_latency` remains `null` with status `"Needs validation"`.
   - **Seed & Database:** Registered in `backend/catalog/seed/humidity.yaml`.

2. **Aggregation Rule for State Variables (SPEC 14.3, Rule 7):**
   - 2-meter specific humidity is an intensive thermodynamic state variable.
   - Monthly values are temporal arithmetic means. Annual and seasonal aggregations are computed as the temporal mean of valid monthly observations (never summed or accumulated, as mandated by SPEC 14.3).
   - Flagged with `aggregation_semantics: state_mean_time_weighted` in `dataset_fields`.
   - Handled in `backend/app/services/aggregate.py` where `is_humidity` / `QV2M` scales values to `g/kg` and performs temporal mean aggregation.

3. **Global Coverage Enforcement (SPEC 14.2):**
   - `coverage_type: global` is enforced across availability, regional extraction, and spatial change analysis.
   - As an atmospheric reanalysis variable, MERRA-2 `QV2M` is continuous over both land and ocean surfaces.
   - Availability evaluates to `Available` for both terrestrial regions (e.g. Chad) and ocean regions (e.g. South Atlantic), provided adequate spatial cells are present.

4. **Specific Caveats Surfaced Across UI & Reports:**
   - **Caveat Text:** *"MERRA-2 QV2M represents 2-meter specific humidity (water vapor mass fraction in g/kg). It is distinct from total column precipitable water vapor (TQV in kg/m²) and specific humidity at isobaric pressure levels (QV). Values are derived from atmospheric reanalysis assimilation rather than direct in-situ psychrometric measurements."*
   - Displayed prominently in:
     - **Page 1 (Data Explorer):** Variable selection cards and Selection Summary card.
     - **Page 2 (Geographic Explorer):** Primary variable card and Dataset Availability panel.
     - **Report (PDF & Web View):** Section 2 (Dataset and Study Area) dynamic grid resolution ($0.625^\circ \times 0.5^\circ$) and Section 6 (Data Quality & Limitations) caveat callout.


**Date:** 2026-11-13  
**Status:** Accepted  
**Context:**  
Phase 7 requires adding the Soil Moisture variable using NASA GLDAS Noah monthly ($0.25^\circ \times 0.25^\circ$). Metadata must be verified from official NASA GES DISC / CMR sources, missing values decoded to NaN, state variable aggregation semantics applied, land-only domain coverage enforced (no ocean values), and caveats displayed across Page 1, Page 2, and the scientific report.

### Decisions & Architecture

1. **Official Verification & Catalog Registration (`backend/catalog/seed/soil_moisture.yaml`):**
   - **Product Collection:** `GLDAS_NOAH025_M` (Version `2.1`, Concept ID: `C1342986036-GES_DISC`).
   - **DOI:** `10.5067/SXAVCZFAQLNO` (Beaudoing & Rodell, 2020).
   - **Version:** `2.1` (GLDAS-2.1 selected for continuous coverage from 2000 to present; GLDAS-2.0 covers 1948–2014 and uses different meteorological forcing per SPEC 6.1).
   - **Native Variable:** `SoilMoi0_10cm_inst` (Soil moisture content for 0–10 cm underground layer).
   - **Native Units:** `kg m-2` (numerically equivalent to mm equivalent water thickness; $1\text{ kg/m}^2 = 1\text{ mm} = 0.01\text{ m}^3/\text{m}^3$ volumetric soil moisture for the 10 cm layer).
   - **Fill Value:** `-9999.0` (decoded strictly to `NaN` upon ingestion per Scientific Rule 3).
   - **Valid Range:** `[0.0, 100.0]`.
   - **Grid:** Regular lat-lon grid, $0.25^\circ \times 0.25^\circ$ ($1440 \times 600$ cells, $-59.875^\circ$ to $89.875^\circ$ lat, $-179.875^\circ$ to $179.875^\circ$ lon), EPSG:4326.
   - **Time Coverage:** `2000-01-01` to present.
   - **Unverified Field:** `update_latency` remains `null` with status `"Needs validation"`.
   - **Seed & Database:** Registered in `backend/catalog/seed/soil_moisture.yaml`.

2. **Aggregation Rule for State Variables (SPEC 14.3, Rule 7):**
   - Soil moisture is an intensive state variable (storage).
   - Monthly values are arithmetic means / end-of-period states. Annual and seasonal aggregations are computed as the temporal mean of valid monthly observations (never summed or accumulated, as mandated by SPEC 14.3).
   - Flagged with `aggregation_semantics: state_mean_time_weighted` in `dataset_fields`.
   - Handled in `backend/app/services/aggregate.py` where `is_sm` includes `["soil_moisture", "SoilMoi0_10cm_inst", "gldas_noah025_m_v21"]`.

3. **Land-Only Coverage Enforcement (SPEC 14.2):**
   - `coverage_type: land_only` is enforced across availability, regional extraction, and spatial change analysis.
   - Ocean cells have fill values ($-9999.0$) or are outside the terrestrial domain and are strictly masked to `NaN`. No ocean values are permitted.
   - For study regions over oceans (e.g. South Atlantic), availability evaluates to `Unavailable` ($0\%$ land coverage). Coastal regions (e.g. Fiji) evaluate to `Partial` ($< 99.5\%$ land coverage) with warning chips detailing non-terrestrial exclusion. Pure land regions (e.g. Chad) evaluate to `Available`.

4. **Specific Caveats Surfaced Across UI & Reports:**
   - **Caveat Text:** *"GLDAS Noah soil moisture is model-simulated water storage (0–10 cm layer) driven by atmospheric data assimilation, not direct in-situ probe or satellite radiometer measurements. GLDAS-2.0 (1948–2014) and GLDAS-2.1 (2000–present) use different meteorological forcing and must not be stitched without bias correction. Ocean cells are strictly masked."*
   - Displayed prominently in:
     - **Page 1 (Data Explorer):** Variable selection cards and Selection Summary card.
     - **Page 2 (Geographic Explorer):** Primary variable card and Dataset Availability panel.
     - **Report (PDF & Web View):** Section 2 (Dataset and Study Area) dynamic grid resolution ($0.25^\circ \times 0.25^\circ$) and Section 6 (Data Quality & Limitations) caveat callout.



---

## ADR-009: Phase 8 System Hardening, Responsive Layouts, and Verification

**Date:** 2026-11-14  
**Status:** Accepted  
**Context:**  
Phase 8 Hardening requires enforcing system robustness across all pages per SPEC 3.3, 16, and 17.3: honest empty/loading/error states with request IDs, responsive layouts across 1440, 1024, 768, and 390 px viewports, visible accessibility and color-independent legends, display-only downsampling for charts, strict input validation and 2MB geometry caps on endpoints, dynamic dataset version resolution, elimination of hardcoded numbers, and an end-to-end Playwright demonstration path generating a verified PDF audit report.

### Discoveries & Decisions

1. **Request Tracking & Error Observability (SPEC 3.3):**
   - Added `add_request_id_middleware` to FastAPI (`backend/app/main.py`), creating or forwarding `X-Request-ID` on all HTTP responses.
   - Frontend error states across Pages 1–5 append the request/job ID: `(Request/Job ID: ...)`, enabling reproducible audit tracing without logging sensitive variables.

2. **Honest Empty & Degraded States (SPEC 3.3, Rule 1):**
   - Removed all hardcoded fallback bounding boxes and fabricated dummy series from `TrendsPage.tsx`, `ChangesPage.tsx`, and `SignificancePage.tsx`.
   - If user visits Page 3, 4, or 5 directly without configuring a dataset and geometry on Steps 1 and 2, pages display an explicit empty state ("No Dataset or Study Region Configured") with direct navigation links to Steps 1 and 2. Missing data is decoded strictly to `NaN`, never substituted with zero.

3. **Dynamic Clamping & Version Resolution (Rule 4, Rule 5):**
   - Clamped baseline start dates dynamically on `ChangesPage.tsx` based on variable coverage (GLDAS: 2000, OISST: 1981, MERRA-2: 1980, GPCP: 1979).
   - Dynamic version resolver `resolve_dataset_version()` in `backend/app/api/analysis.py` and `backend/app/services/reports.py` matches dataset versions (`5.12.4`, `v2.1`, `2.1`, `v2.3`) without hardcoded version strings.

4. **Security & Payload Caps (SPEC 16.5):**
   - Enforced 2MB payload cap, GeoJSON structure validity, and WGS84 coordinate bounds `[-180, -90, 180, 90]` in `validate_geometry_input()`.
   - No secrets, credentials, or protected S3/GCS tokens exist in the repository or API responses.

5. **Display-Only Downsampling (SPEC 16.3):**
   - `TimeSeriesChart.tsx` applies largest-triangle-three-buckets / stride downsampling strictly for visual SVG rendering when points exceed 1,000, while preserving 100% of points for statistical calculations and CSV downloads.

6. **E2E Playwright Demonstration Test:**
   - Authored `frontend/scripts/playwright_demo_journey.mjs` and registered `"test:e2e"` script in `package.json`.
   - Validates entire demo journey: `Homepage -> Page 1 Data Explorer -> Page 2 Geographic Explorer -> Page 3 Trend Analysis -> Page 4 Change Detection -> Page 5 Significance & Evidence -> PDF Audit Report`.
   - Tests responsive viewports (1440, 1024, 768, 390 px) on each page.
   - Verifies PDF generation (`rep_...`), HTTP 200 binary download, `%PDF-` signature, and file size $> 5\text{ KB}$.

---

## ADR-016: Scientific Honesty Hardening, Fixture Quarantine, Dynamic Date Derivation, and Honest Degradation

**Date:** 2026-11-14  
**Status:** Accepted  
**Context:**  
Following the data volume audit, four datasets (`merra2_monthly_ts`, `noaa_oisst_v21`, `gldas_noah025_m_v21`, `merra2_monthly_qv2m`) were found to have cropped local fixture files placed in `data/cache/` rather than complete global datasets, and nearest-cell fallback allowed disjoint regions to produce artificial numbers. This ADR documents the systematic elimination of placeholder/fixture data from application runtime paths, bounded nearest-cell fallback, replacement of silent exception fallbacks with logged errors and explicit API warnings, dynamic derivation of dates from registry observation dates, and truthful reporting of database-offline states.

### Decisions & Architecture

1. **Quarantine & Storage Hygiene (Rule 1, Rule 12):**
   - Quarantined `merra2_ts.mon.mean.nc`, `merra2_qv2m.mon.mean.nc`, `gldas_noah_sm.mon.mean.nc`, and `oisst_sst.mon.mean.nc` out of `data/cache/` into `backend/tests/fixtures/`.
   - Purged stray `.part` files, `data/cache/subsets/`, `data/outputs/cache/`, and stale cached results for uningested datasets. Application runtime code is strictly prohibited from accessing `tests/fixtures/`.
   - `data/cache/` contains strictly real ingested data (`precip.mon.mean.nc` for GPCP V2.3).
   - Added Rule 12 to `AGENTS.md`: *"If real data cannot be fetched, stop and report. Never create synthetic, cropped or placeholder data files in data/cache. Fixtures live only in tests/fixtures."*

2. **Truthful Status Across Catalogue, UI, and API Endpoints:**
   - Catalog seed YAMLs for the four uningested datasets updated with `status: "Unavailable - real data not yet ingested"` and `latest_observation_date: null`.
   - Removed the catalogue refresh bypass in `backend/app/services/catalogue_refresh.py` that redirected queries to local files. Ingestion stubs raise explicit `RuntimeError("Unavailable - real data not yet ingested")`.
   - Availability endpoint returns `"Unavailable - real data not yet ingested"`, $0$ cell count, and $0.0\%$ coverage for uningested datasets.
   - Analysis endpoints (`/api/analysis/timeseries`, `/api/analysis/change-map`, `/api/analysis/significance`) immediately reject uningested datasets with HTTP 400 `"Unavailable - real data not yet ingested"`.
   - Frontend displays `"Unavailable - real data not yet ingested"` chips on Page 1 cards and Page 2 availability panel, and disables progression buttons.

3. **Strictly Bounded Spatial Region Fallback:**
   - `nearest_cell_fallback` in `backend/app/services/regions.py` and `backend/app/services/change.py` is restricted strictly to geometries located within a 1-grid-cell buffer ($1.5 \times \text{cell\_size}$) of the dataset's actual spatial extent.
   - Any disjoint geometry (e.g., France on a Chad-only bounding box, or bounding boxes outside grid bounds) returns $0$ intersecting cells, empty/null series, a documented warning, and status `"Unavailable"`. Zero or synthetic numbers are never returned for disjoint geometries.

4. **Dynamic Date Derivation (Rule 4, Rule 5):**
   - Removed all hardcoded date literals (`"2026-10-01"`, `[2006, 2025]`, `[1990, 2005]`, `"2025-12-01"`, `"1990-01-01"`).
   - Analysis endpoints and report services derive temporal bounds and baseline/comparison periods dynamically from the dataset's `latest_observation_date` and start date in the registry.

5. **Elimination of Silent Failures & Explicit API Warnings:**
   - Replaced silent `except Exception: pass / return None` patterns across availability, geometry, trends, significance, and reports with logged errors and explicit `warnings` in API responses.
   - In `backend/app/services/significance.py`:
     - If confidence interval evaluation fails, returns `ci_lower = None` and `ci_upper = None` with a warning (never `ci_lower = ci_upper = slope`).
     - If modified Mann-Kendall fails and original Mann-Kendall is used, sets `method_used = "mann_kendall_original"` with the fallback reason logged and documented.
   - In `backend/app/services/reports.py`: missing or unparsable fields log warnings and render truthful indicators (e.g., `"[Start Date Not Specified]"`) instead of silent hardcoded fallbacks.

6. **Database Offline State Handling:**
   - When the PostgreSQL database is unreachable, `_load_catalog_with_fallback()` marks loaded datasets as `"Needs validation"` (preserving `"Unavailable - real data not yet ingested"` for uningested ones).
   - Frontend Page 1 displays an honest warning banner: *"Database is offline. Catalogue is running from local seed files. Datasets require validation."*

7. **Regression Guard Test Suite:**
   - Added `backend/tests/test_data_integrity.py` with:
     - `test_disjoint_region_returns_unavailable`: asserts disjoint geometries return 0 valid cells and status `Unavailable`.
     - `test_four_datasets_return_unavailable_until_real_data_exists`: asserts seed catalog, availability check, and all analysis endpoints return `"Unavailable - real data not yet ingested"`.
     - `test_no_hardcoded_date_strings_grep`: grep test that fails if `"2026-10-01"`, `[2006, 2025]`, or `"2025-12-01"` are reintroduced in `backend/app/`.

---

## ADR-017: Vercel Production Deployment Architecture & Edge API Proxying

**Date:** 2026-11-15  
**Status:** Accepted  
**Context:**  
The user requested deployment readiness for Vercel. Because the application consists of a modern React + TypeScript + Vite SPA on the frontend and a Python 3.11+ FastAPI backend with multi-gigabyte historical NetCDF caches, this ADR documents the decoupled architecture, client URL resolution, and Edge proxy integration.

### Decisions & Architecture

1. **Dual Directory Root Support:**
   - Added root `package.json` with scripts (`build`, `dev`, `lint`, `test`) executing against `frontend/` via `npm --prefix frontend`.
   - Added root `vercel.json` configured with `buildCommand: "npm --prefix frontend run build"`, `outputDirectory: "frontend/dist"`, framework preset `vite`, and SPA fallback rewrites.
   - Added `frontend/vercel.json` so deployments configured with "Root Directory: frontend" in the Vercel dashboard work identically.

2. **Upload Safety (`.vercelignore`):**
   - Configured `.vercelignore` to strictly exclude `data/cache/` (1.5+ GB NetCDF caches), `backend/`, `data/outputs/`, `.pytest_cache/`, and test fixtures, keeping Vercel deployment payloads small and fast.

3. **Universal Vercel Edge API Proxy (`api/[...path].js` & `frontend/api/[...path].js`):**
   - Implemented a lightweight, zero-dependency Vercel Edge Function proxy that intercepts `/api/*` requests on Vercel and forwards them to the environment variable `BACKEND_URL`.
   - Handles query parameters, headers, and request bodies for POST/PUT requests, and streams back binary responses (such as PNG change/significance map overlays and GeoTIFFs).
   - If `BACKEND_URL` is not yet configured, returns a helpful 503 JSON message instructing the user to configure `BACKEND_URL` in their Vercel Project Settings.

4. **Client API URL Resolver (`frontend/src/api/client.ts`):**
   - Introduced `getApiUrl()` and `apiFetch()` across all frontend API clients (`catalog`, `availability`, `regions`, `trends`, `change`, `significance`, `reports`).
   - Supports `VITE_API_BASE_URL` when a direct cross-origin connection is preferred, and falls back to relative `/api/*` paths when using the Vercel Edge proxy or Vite local dev proxy.
   - Normalizes nested overlay and download URLs (`overlay_url`, `geotiff_url`, `pdf_url`, `csv_url`) so that rendered image overlays in Leaflet resolve properly in all deployment topologies.

5. **Production Backend Containerization (`Dockerfile`):**
   - Created a production Python 3.11-slim `Dockerfile` with system dependencies (`libgdal-dev`, `libgeos-dev`, `libproj-dev`, `libpq-dev`), requirements installation, and health checks, ready for one-click deployment to Railway, Render, Fly.io, or Google Cloud Run.

