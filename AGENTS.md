# Earth Science Explorer - agent rules

## Project
A web app for exploring historical Earth-science data: Homepage + 5 pages
(Data Explorer, Geographic Explorer, Trend Analysis, Change Detection,
Significance & Reports). Full spec: docs/SPEC.md. Decisions log: docs/DECISIONS.md.
Read the relevant spec sections before planning any task.

## Stack (do not substitute without asking)
Frontend: React + TypeScript + Tailwind, React Router, Zustand (persist),
Plotly.js, React Leaflet + Leaflet-Geoman.
Backend: Python 3.11+, FastAPI, Xarray, NumPy, Pandas, GeoPandas, Shapely,
rioxarray/Rasterio, PyProj, SciPy, pymannkendall, statsmodels.
Storage: PostgreSQL + PostGIS (Docker Compose); file cache under data/cache.
Tests: pytest, Vitest, Playwright.

## Scientific non-negotiables
1. Never display, return or hard-code placeholder numbers as findings.
   If real data is not loaded, show an honest empty/loading/unavailable state.
2. NASA GIBS is for map imagery only. Never compute from tile colours.
   Numbers come from NetCDF/HDF/Zarr/GeoTIFF files.
3. Decode fill values to NaN. Missing is never zero. Never interpolate silently.
4. Dataset version is part of the dataset ID and of every result. Never merge
   versions in one series.
5. Latest observation date = date of the data, not file or catalogue date.
   Default end date = last COMPLETE period, never today.
6. Area-weight regional means (cos latitude at minimum). Report valid cell count.
7. Aggregate by variable type: rates -> accumulate by days in month;
   temperature and state variables -> mean. Keep native units in provenance.
8. Significance comes from the underlying time samples, not from a difference
   raster. Spatial tests use Benjamini-Hochberg FDR; show raw vs adjusted.
9. Every result stores provenance (spec 15.4) and a request/job ID.
10. Changing dataset, dates, region or aggregation invalidates downstream
    results (spec 13.3).
11. Secrets only in .env (gitignored), backend only. Never log secrets.
12. If real data cannot be fetched, stop and report. Never create synthetic,
    cropped or placeholder data files in data/cache. Fixtures live only in tests/fixtures.

## Working rules
- Work on one phase at a time; do not build screens for later phases.
- Write tests with the code. Use synthetic data with known answers for maths.
- Record each non-obvious choice in docs/DECISIONS.md.
- At the end of a task: list what you ran, what passed, what is not done,
  and anything you could not verify. Do not claim success you did not test.
- UI: dark navy/charcoal, blue/cyan accents, rounded cards, responsive
  (3 columns on desktop, stacked on small screens), keyboard accessible,
  never colour-only meaning. Status chips: Available, Partial, Unavailable,
  Loading, Failed, Needs validation.
