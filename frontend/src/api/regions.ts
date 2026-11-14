import type { Geometry } from 'geojson';

export interface RegionSearchResult {
  id: string;
  name: string;
  local_name?: string;
  type: string;
  subtype?: string;
  country?: string;
  iso_a3?: string;
  bbox: [number, number, number, number];
}

export interface RegionGeometryResponse {
  id: string;
  name: string;
  local_name?: string;
  type: string;
  subtype?: string;
  country?: string;
  iso_a3?: string;
  crs: string;
  bbox: [number, number, number, number];
  geometry: Geometry;
}

export interface RegionValidateRequest {
  geometry?: Geometry | null;
  crs?: string;
  point?: [number, number];
  radius_km?: number;
  radius_m?: number;
  label?: string;
  type?: string;
}

export interface RegionValidateResponse {
  status: string;
  crs: string;
  geometry: Geometry;
  area_km2: number;
  bbox: [number, number, number, number];
  centroid: [number, number];
  warnings: string[];
}

export async function searchRegions(query: string, limit: number = 20): Promise<RegionSearchResult[]> {
  const url = `/api/regions/search?q=${encodeURIComponent(query)}&limit=${limit}`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to search regions (HTTP ${response.status})`);
  }
  return response.json();
}

export async function fetchRegionGeometry(regionId: string): Promise<RegionGeometryResponse> {
  const response = await fetch(`/api/regions/${encodeURIComponent(regionId)}/geometry`);
  if (!response.ok) {
    throw new Error(`Failed to fetch region geometry (HTTP ${response.status})`);
  }
  return response.json();
}

export async function validateRegion(req: RegionValidateRequest): Promise<RegionValidateResponse> {
  const response = await fetch('/api/regions/validate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Validation failed' }));
    throw new Error(err.detail || `Validation error (HTTP ${response.status})`);
  }
  return response.json();
}
