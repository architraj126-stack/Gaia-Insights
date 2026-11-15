# Gaia Insights

> Web application for exploring historical Earth-science observational records across a guided 5-step analysis journey: **Data Explorer**, **Geographic Explorer**, **Trend Analysis**, **Change Detection**, and **Significance & Reports**.

[![Phase 0: Foundation](https://img.shields.io/badge/Phase-0%20Foundation-blue.svg)](docs/SPEC.md)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![React 19](https://img.shields.io/badge/react-19-cyan.svg)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com/)

---

## 1. Monorepo Structure

```text
earth science explorer/
├── frontend/                     # React 19 + TypeScript + Vite + Tailwind CSS
│   ├── src/
│   │   ├── components/           # Reusable UI elements (TopNav, StepIndicator, StatusChip)
│   │   ├── pages/                # Routes: /, /explore, /region, /trends, /changes, /significance
│   │   ├── store/                # Zustand useSession store + localStorage persistence
│   │   ├── App.tsx               # Route definitions
│   │   └── main.tsx              # Root entrypoint
│   └── package.json
├── backend/                      # Python 3.11+ FastAPI service
│   ├── app/
│   │   ├── api/                  # Endpoints: /health, /api/catalog/variables
│   │   ├── config.py             # Pydantic-settings configuration (.env)
│   │   ├── logging.py            # Structured JSON logger with secret redaction
│   │   └── main.py               # Application entrypoint & CORS middleware
│   ├── scripts/
│   │   ├── spike_gpcp.py         # GPCP V2.3 NetCDF data-access spike
│   │   └── verify_servers.py     # Live socket server verification
│   ├── tests/                    # Pytest test suite
│   ├── .env.example              # Environment variables template
│   └── requirements.txt
├── data/
│   └── cache/                    # File cache for downloaded NetCDF/GeoTIFF files
├── docs/
│   ├── SPEC.md                   # Complete architectural and scientific specification
│   └── DECISIONS.md              # ADRs and scientific findings log
├── docker-compose.yml            # PostgreSQL 16 + PostGIS 3.4
└── AGENTS.md                     # Agent and scientific non-negotiable rules
```

---

## 2. Scientific Non-Negotiables (AGENTS.md)

1. **No Fake Findings:** Never display, return, or hard-code placeholder numbers as scientific findings. Show honest empty, loading, or unavailable states.
2. **Imagery vs Data:** NASA GIBS tiles are for visualization only. Numerical analytics always use NetCDF/HDF/Zarr/GeoTIFF arrays.
3. **Fill Values to NaN:** Missing data is never zero. Decode fill values (`-9.96921e+36` / `NC_FILL_FLOAT`) strictly to `NaN`. Never interpolate silently.
4. **Dataset Versioning:** Dataset version is part of the dataset ID (e.g. `gpcp:V2.3`). Never merge different versions in a single time series.
5. **Observation Dates:** Latest observation date represents observational coverage (e.g. `2026-10-01`), not catalogue download date.
6. **Area Weighting:** Regional means are always area-weighted (cosine of latitude).
7. **Rate Aggregation:** Rates (`mm/day`) accumulate by days in month; temperature and state variables take means.
8. **Underlying Samples for Significance:** Statistical significance comes from underlying time samples, not difference rasters. Spatial tests use Benjamini-Hochberg FDR.
9. **Provenance:** Every result retains full provenance and job metadata.
10. **State Invalidation:** Modifying dataset, date range, frequency, or region immediately invalidates all downstream results (SPEC 13.3).
11. **Secret Safety:** Secrets only in `.env` (gitignored). Structured logging scrubs all passwords, tokens, and keys.

---

## 3. Quick Start

### Prerequisites
- **Python**: 3.11+ (installed with `pip`)
- **Node.js**: 18+ (with `npm`)
- **Docker**: (Optional for local PostgreSQL + PostGIS container)

---

### One-Command Setup

#### Option A: Quick Script (Windows)
Run the root startup script or run frontend and backend independently:

```bash
# Setup backend
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env

# Setup frontend
cd frontend
npm install
cd ..
```

---

### Running the Services

#### 1. Start Storage (PostgreSQL + PostGIS)
```bash
docker compose up -d
```

#### 2. Start Backend API (FastAPI)
```bash
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```
- API Base: `http://127.0.0.1:8000`
- Health Check: `http://127.0.0.1:8000/health`
- Catalog Variables: `http://127.0.0.1:8000/api/catalog/variables`
- Interactive Docs: `http://127.0.0.1:8000/docs`

#### 3. Start Frontend (Vite + React)
```bash
cd frontend
npm run dev
```
- Web Application: `http://localhost:5173`

---

## 4. Frontend Routes & Guided Journey

| Step | Route | Page | Purpose |
| :---: | :--- | :--- | :--- |
| **0** | `/` | Homepage | Product overview, workflow description, and StatusChip showcase |
| **1** | `/explore` | Data Explorer | Select variable, product, time coverage, frequency |
| **2** | `/region` | Geographic Explorer | Boundary selection, polygon drawing, GeoJSON storage |
| **3** | `/trends` | Trend Analysis | Area-weighted time series, Sen's slope, Mann-Kendall test |
| **4** | `/changes` | Change Detection | Period comparison difference rasters |
| **5** | `/significance` | Significance & Reports | FDR hypothesis testing and report generation |

All analysis pages (`/explore` to `/significance`) render a persistent 5-step indicator and honest placeholders (`Not built yet`) with no mock numbers.

---

## 5. Running Tests

### Frontend Unit Tests (Vitest)
Verifies Zustand store, SPEC 13.3 downstream invalidation rules, reusable `StatusChip` components, and all 6 routes:
```bash
cd frontend
npm run test
```

### Backend Unit Tests (Pytest)
Verifies health endpoint, catalog endpoint, pydantic-settings, and secret redaction filter:
```bash
python -m pytest backend/tests
```

### End-to-End Server Verification
Tests live socket bindings for both FastAPI and Vite servers:
```bash
python backend/scripts/verify_servers.py
```

---

## 6. NOAA PSL GPCP V2.3 Data-Access Spike

Phase 0 includes an authoritative data spike that accesses NOAA PSL's GPCP V2.3 monthly precipitation NetCDF without guessing URLs:

```bash
python backend/scripts/spike_gpcp.py
```

### Spike Findings (Documented in `docs/DECISIONS.md`)
- **Metadata Discovery:** Programmatically located from `https://www.psl.noaa.gov/data/gridded/data.gpcp.html` -> `datasetID = 44` -> variable `1631` -> `precip.mon.mean.nc`.
- **Endpoints:**
  - OPeNDAP: `https://psl.noaa.gov/thredds/dodsC/Datasets/gpcp/precip.mon.mean.nc`
  - Download: `https://downloads.psl.noaa.gov/Datasets/gpcp/precip.mon.mean.nc`
- **Grid Dimensions:** `time: 574, nv: 2, lat: 72, lon: 144` ($2.5^\circ \times 2.5^\circ$ global grid).
- **Time Coverage:** `1979-01-01` to `2026-10-01` (574 monthly timesteps).
- **Variable & Units:** `precip` in `mm/day`.
- **NetCDF Quirk Resolved:** Auxiliary `time_bnds` contains unmasked fill values and malformed units (`days since 1800-01-01 00:00:00 0:00`). Resolved by opening with `decode_times=False` and decoding `time` explicitly with `cftime.num2date`.
- **Missing-Value Convention:** Encoded as `-9.96921e+36`, strictly decoded to `NaN` in accordance with Rule 3.
