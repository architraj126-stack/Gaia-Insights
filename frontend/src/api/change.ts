/**
 * Change Detection API client (SPEC Section 9, 14.5, 14.8).
 */
import { apiFetch, getApiUrl } from './client';

export interface ChangeMapLegend {
  colormap: string;
  symmetric_zero: number;
  min_val: number;
  max_val: number;
  units: string;
  thresholds: number[];
  colors: string[];
  no_data_swatch: {
    color: string;
    label: string;
  };
}

export interface SpatialSummary {
  area_weighted_mean_change: number | null;
  share_increasing_pct: number;
  share_decreasing_pct: number;
  share_no_change_pct: number;
  highest_change: {
    value: number;
    lat: number;
    lon: number;
  } | null;
  lowest_change: {
    value: number;
    lat: number;
    lon: number;
  } | null;
  valid_area_km2: number;
  total_region_area_km2: number;
  nodata_area_km2: number;
  nodata_share_pct: number;
  valid_cell_count: number;
  intersecting_cell_count: number;
}

export interface ChangeMapResult {
  job_id: string;
  run_id: string;
  status: string;
  overlay_url: string;
  geotiff_url: string;
  bounds: [[number, number], [number, number]];
  legend: ChangeMapLegend;
  spatial_summary: SpatialSummary;
  provenance: Record<string, any>;
  warnings: string[];
  units: string;
  metric: 'absolute' | 'percentage' | 'spatial_trend';
}

export interface ChangeMapRequestPayload {
  dataset_id: string;
  dataset_version?: string;
  variable: string;
  region_id?: string;
  geometry?: any;
  geometry_crs?: string;
  baseline_period: [number, number];
  comparison_period: [number, number];
  metric: 'absolute' | 'percentage' | 'spatial_trend';
  aggregation: 'annual' | 'monthly';
  epsilon?: number;
  allow_overlap?: boolean;
}

export interface CellInspectResult {
  run_id: string;
  requested_lat: number;
  requested_lon: number;
  cell_lat: number;
  cell_lon: number;
  baseline_mean: number | null;
  comparison_mean: number | null;
  difference: number | null;
  overlap_fraction: number;
  is_valid: boolean;
  units: string;
  metric: string;
}

export async function executeChangeMapAnalysis(
  payload: ChangeMapRequestPayload
): Promise<ChangeMapResult> {
  const response = await apiFetch('/api/analysis/change-map', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let errorDetail = `HTTP ${response.status}`;
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errorDetail;
    } catch {
      // ignore
    }
    throw new Error(errorDetail);
  }

  const data: ChangeMapResult = await response.json();
  if (data.overlay_url) data.overlay_url = getApiUrl(data.overlay_url);
  if (data.geotiff_url) data.geotiff_url = getApiUrl(data.geotiff_url);
  return data;
}

export async function fetchChangeMapResult(runId: string): Promise<ChangeMapResult> {
  const response = await apiFetch(`/api/analysis/change-map/${runId}`);
  if (!response.ok) {
    throw new Error(`Failed to load change map result (${response.status})`);
  }
  const data: ChangeMapResult = await response.json();
  if (data.overlay_url) data.overlay_url = getApiUrl(data.overlay_url);
  if (data.geotiff_url) data.geotiff_url = getApiUrl(data.geotiff_url);
  return data;
}

export async function inspectChangeCell(
  runId: string,
  lat: number,
  lon: number
): Promise<CellInspectResult> {
  const response = await apiFetch(
    `/api/analysis/change-map/${runId}/inspect?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}`
  );
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {}
    throw new Error(`Inspect failed: ${detail}`);
  }
  return response.json();
}
