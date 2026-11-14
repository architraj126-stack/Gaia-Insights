/**
 * Trend Analysis API client (SPEC Section 8, 12.2, 12.3).
 */

export interface TimeSeriesPoint {
  date: string;
  value: number | null;
  units: string;
  rate_mm_day?: number | null;
  native_units?: string;
  valid_cell_count?: number;
  valid_area_km2?: number;
  is_missing: boolean;
  flags?: string[];
  fitted_ols?: number | null;
  ols_ci_lower?: number | null;
  ols_ci_upper?: number | null;
  sens_line?: number | null;
  moving_avg?: number | null;
  season?: string;
  year?: number;
}

export interface TrendRegressionStats {
  slope_per_year: number | null;
  intercept: number | null;
  p_value: number | null;
  r_squared: number | null;
  std_err: number | null;
  ci_lower_slope: number | null;
  ci_upper_slope: number | null;
  trend_direction: string;
}

export interface TrendSensStats {
  slope_per_year: number | null;
  intercept: number | null;
  ci_lower: number | null;
  ci_upper: number | null;
  confidence_level: number;
  trend_direction: string;
}

export interface MannKendallStats {
  trend: string;
  p_value: number | null;
  z: number | null;
  tau: number | null;
  s: number | null;
  var_s: number | null;
  significant: boolean;
  period?: number;
  method?: string;
}

export interface CompletenessStats {
  valid: number;
  expected: number;
  pct: number;
  denominator_description: string;
}

export interface TrendSummary {
  trend_direction: 'increasing' | 'decreasing' | 'no clear trend' | 'insufficient data' | string;
  slope_method_displayed: string;
  rate_of_change: number | null;
  rate_of_change_units: string;
  mean: number | null;
  estimated_total_change: number | null;
  elapsed_years: number;
  valid_n: number;
  expected_n: number;
  completeness: CompletenessStats;
  ols: TrendRegressionStats;
  sens_slope: TrendSensStats;
  mann_kendall: MannKendallStats;
  seasonal_mann_kendall: MannKendallStats | null;
  modified_mann_kendall: MannKendallStats;
  alpha: number;
  min_data_points: number;
  moving_average_window: number;
}

export interface TimeSeriesResult {
  job_id: string;
  run_id: string;
  series_id: string;
  status: string;
  dataset: {
    id: string;
    version: string;
    units: string;
    source: string;
    variable?: string;
  };
  coverage: {
    requested_start: string;
    actual_start: string;
    actual_end: string;
    valid_steps: number;
    expected_steps: number;
    completeness_pct: number;
  };
  series_url: string;
  points: TimeSeriesPoint[];
  summary: TrendSummary;
  provenance?: Record<string, any>;
  warnings?: string[];
}

export interface TimeSeriesRequestPayload {
  dataset_id: string;
  dataset_version?: string;
  variable: string;
  region_id?: string;
  geometry?: any;
  geometry_crs?: string;
  start_date: string;
  end_date: string;
  aggregation: 'monthly' | 'annual' | 'seasonal';
  options?: {
    area_weighted?: boolean;
    include_missing_flags?: boolean;
    alpha?: number;
    moving_average_window?: number;
  };
}

export async function executeTimeSeriesAnalysis(
  payload: TimeSeriesRequestPayload
): Promise<TimeSeriesResult> {
  const response = await fetch('/api/analysis/timeseries', {
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
    throw new Error(`Time-series analysis failed: ${errorDetail}`);
  }

  const data = await response.json();

  // If points are already included in response, return directly
  if (data.points && Array.isArray(data.points)) {
    return data as TimeSeriesResult;
  }

  // Fallback to series_url fetch if points were not embedded
  if (data.series_url) {
    const seriesRes = await fetch(data.series_url);
    if (!seriesRes.ok) {
      throw new Error(`Failed to load full time-series results (${seriesRes.status})`);
    }
    return seriesRes.json();
  }

  return data as TimeSeriesResult;
}

export async function fetchTimeSeriesResult(seriesId: string): Promise<TimeSeriesResult> {
  const url = seriesId.startsWith('/api/results/series/')
    ? seriesId
    : `/api/results/series/${seriesId}`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch series ${seriesId} (${response.status})`);
  }
  return response.json();
}
