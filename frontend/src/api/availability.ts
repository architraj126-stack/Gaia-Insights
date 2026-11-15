import type { Geometry } from 'geojson';
import { apiFetch } from './client';

export interface DatasetAvailabilityResponse {
  dataset_id: string;
  variable_id: string;
  product_name: string;
  version: string;
  status: 'Available' | 'Partial' | 'Unavailable' | (string & {});
  spatial_coverage_percent: number;
  temporal_coverage_percent: number;
  cell_count: number;
  spatial_resolution: string;
  temporal_resolution: string;
  area_km2: number;
  valid_date_range: {
    start: string;
    latest_observation_date: string | null;
    last_catalogue_check?: string | null;
  };
  warnings: string[];
  provider: string;
  citation?: string;
}

export interface AvailabilityQueryParams {
  geometry?: Geometry | null;
  bbox?: [number, number, number, number] | null;
  start?: string;
  end?: string;
}

export async function fetchDatasetAvailability(
  datasetId: string,
  params: AvailabilityQueryParams
): Promise<DatasetAvailabilityResponse> {
  // Use POST to avoid URL length issues with complex geometry coordinates
  const response = await apiFetch(`/api/datasets/${encodeURIComponent(datasetId)}/availability`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      geometry: params.geometry,
      bbox: params.bbox,
      start: params.start,
      end: params.end,
    }),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Availability check failed' }));
    throw new Error(err.detail || `Availability check error (HTTP ${response.status})`);
  }
  return response.json();
}
