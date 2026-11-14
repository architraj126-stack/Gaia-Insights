export interface DatasetCatalogItem {
  id: string;
  variable_id: string;
  product_name: string;
  provider: string;
  short_name: string;
  collection_id?: string | null;
  version: string;
  doi?: string | null;
  doi_status: string;
  native_variable_name: string;
  long_name: string;
  var_desc?: string | null;
  units: string;
  displayed_unit_conversion?: string | null;
  valid_range?: [number, number] | null;
  fill_value?: number | null;
  spatial_grid: string;
  crs: string;
  cell_dimensions?: [number, number] | null;
  spatial_coverage: string;
  spatial_resolution: string;
  temporal_resolution: string;
  start_date: string;
  /** ISO date string "YYYY-MM-DD" of the most recent complete monthly observation,
   *  per SPEC 6.3 & 15.3. null means not yet checked / no access URL configured. */
  latest_observation_date?: string | null;
  /** UTC ISO timestamp of when the backend last queried the data source (SPEC 15.3). */
  last_catalogue_check?: string | null;
  update_latency?: string | null;
  update_latency_status: string;
  product_documentation?: string | null;
  citation?: string | null;
  access_url?: string | null;
  opendap_url?: string | null;
  terms_licensing?: string | null;
  known_limitations?: string | null;
  no_data_mask_semantics?: string | null;
  status: string;
}

export interface VariableCatalogItem {
  id: string;
  name: string;
  category: string;
  description: string;
  scientific_question: string;
  default_dataset_id: string;
  status: string;
  datasets: DatasetCatalogItem[];
}

/** Format a "YYYY-MM-DD" or ISO timestamp for display. */
export function formatObservationDate(isoDate: string | null | undefined): string {
  if (!isoDate) return 'Not yet checked';
  // Show just the date portion for observation dates
  const datePart = isoDate.split('T')[0];
  return datePart;
}

/** Format a last_catalogue_check ISO timestamp for display. */
export function formatCatalogueCheck(isoTimestamp: string | null | undefined): string {
  if (!isoTimestamp) return 'Never';
  try {
    const d = new Date(isoTimestamp);
    return d.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      timeZoneName: 'short',
    });
  } catch {
    return isoTimestamp;
  }
}

export async function fetchVariables(): Promise<VariableCatalogItem[]> {
  const response = await fetch('/api/catalog/variables');
  if (!response.ok) {
    throw new Error(`Failed to fetch catalog variables (HTTP ${response.status})`);
  }
  return response.json();
}

export async function fetchDatasets(variableId?: string): Promise<DatasetCatalogItem[]> {
  const url = variableId
    ? `/api/catalog/datasets?variable=${encodeURIComponent(variableId)}`
    : '/api/catalog/datasets';
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch catalog datasets (HTTP ${response.status})`);
  }
  return response.json();
}
