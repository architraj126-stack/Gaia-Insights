# Gaia Insights - Deployment Guide

This guide describes how to deploy the Gaia Insights web application to **Vercel** (frontend & serverless proxy) and a cloud container host (FastAPI backend).

---

## Architecture Overview

```
+-----------------------------------------------------------+
|                     VERCEL HOSTING                        |
|                                                           |
|  +---------------------------+  +----------------------+  |
|  |  React + Vite SPA         |  |  Edge API Proxy      |  |
|  |  (HTML / JS / CSS Assets) |  |  (/api/* -> backend) |  |
|  +---------------------------+  +----------------------+  |
+--------------------------------------------|--------------+
                                             | BACKEND_URL
                                             v
+-----------------------------------------------------------+
|                 BACKEND CONTAINER HOST                    |
|             (Railway / Render / Fly.io / Cloud Run)       |
|                                                           |
|  FastAPI (Python 3.11) + Xarray + GDAL/Rasterio           |
|  + NetCDF Cache (data/cache/) + PostgreSQL/PostGIS        |
+-----------------------------------------------------------+
```

---

## 1. Deploying Frontend to Vercel

### Option A: Import via Vercel Web Dashboard (Recommended)

1. Push your repository to **GitHub / GitLab / Bitbucket**.
2. Go to [Vercel Dashboard](https://vercel.com/new) and click **"Add New..." > "Project"**.
3. Select your repository.
4. Configure Project Settings:
   - **Framework Preset**: `Vite` (detected automatically).
   - **Root Directory**:
     - Leave as `.` (root) — the root `package.json` and `vercel.json` will build `frontend/dist`.
     - *OR* set to `frontend` — the `frontend/vercel.json` will handle rewrites.
   - **Build Command**: `npm --prefix frontend run build` (or `npm run build` if Root Directory is `frontend`).
   - **Output Directory**: `frontend/dist` (or `dist` if Root Directory is `frontend`).
5. **Environment Variables**:
   Add the following environment variable in the Vercel dashboard:
   - `BACKEND_URL`: The HTTPS URL of your deployed FastAPI backend (e.g. `https://earth-science-backend.railway.app` or `https://earth-science-backend.onrender.com`).
6. Click **Deploy**.

### Option B: Deploy via Vercel CLI

```bash
# Install Vercel CLI if needed
npm install -g vercel

# From the repository root
vercel

# Deploy to production
vercel --prod
```

---

## 2. Deploying Backend (FastAPI + NetCDF Cache)

Because Earth Science Explorer processes large multi-gigabyte historical Earth-science NetCDF files using Xarray, NumPy, and Rasterio/GDAL, the backend runs in a container.

### Option A: Railway (One-Click Dockerfile)
1. In Railway, click **New Project** > **Deploy from GitHub repo**.
2. Railway detects the root `Dockerfile` and builds the Python 3.11 image with all required system libraries (`libgdal-dev`, `libgeos-dev`, `libproj-dev`).
3. Add a PostgreSQL + PostGIS database service.
4. Set Environment Variables:
   - `DATABASE_URL`: Connection string from PostgreSQL service.
   - `EARTHDATA_TOKEN`: NASA Earthdata Bearer Token.
   - `CORS_ORIGINS`: Your Vercel frontend URL (e.g. `https://your-app.vercel.app,http://localhost:5173`).
5. Copy the Railway public service URL and paste it as `BACKEND_URL` in Vercel.

### Option B: Render
1. Create a **New Web Service** connected to your repo.
2. Select **Docker** as the runtime.
3. Add a **PostgreSQL** database with PostGIS extension enabled.
4. Set environment variables (`DATABASE_URL`, `EARTHDATA_TOKEN`, `CORS_ORIGINS`).
5. Copy the service URL to `BACKEND_URL` in Vercel.

---

## 3. Environment Variables Reference

### Frontend (Vercel Project Settings)
| Variable | Description | Example |
| :--- | :--- | :--- |
| `BACKEND_URL` | Destination URL for Vercel Edge API proxy | `https://api.earthscience.example.com` |
| `VITE_API_BASE_URL` | Optional: direct frontend-to-backend URL | `https://api.earthscience.example.com` |

### Backend (Railway / Render / Docker)
| Variable | Required | Description | Example |
| :--- | :---: | :--- | :--- |
| `DATABASE_URL` | Yes | PostgreSQL connection string | `postgresql+asyncpg://user:pass@host:5432/db` |
| `EARTHDATA_TOKEN`| Yes | NASA Earthdata bearer token | `secret_token` |
| `CORS_ORIGINS` | Yes | Allowed frontend origins | `https://your-app.vercel.app,http://localhost:5173` |
| `LOG_LEVEL` | No | Logging verbosity | `INFO` |

---

## 4. Verification Checklist

- [ ] Vercel build succeeds (`vite build`).
- [ ] Direct navigation to `/region`, `/trends`, `/changes`, `/significance` works on page refresh (no 404s).
- [ ] Edge proxy `/api/health` returns `{"status": "ok"}` when backend is connected.
- [ ] Change detection and significance overlays render without CORS or path errors.
