/**
 * Significance & Hypothesis Testing API client (SPEC Section 10, 14.6, 14.7, 14.8).
 */

export interface SignificanceClassItem {
  code: number;
  label: string;
  badge_symbol: string;
  pattern: string;
  color: string;
  count: number;
  description: string;
}

export interface SignificanceLegend {
  title: string;
  p_value_mode: string;
  alpha: number;
  classes: SignificanceClassItem[];
}

export interface RegionalSignificanceResult {
  test_name: string;
  null_hypothesis: string;
  test_statistic: number | null;
  raw_p_value: number | null;
  sens_slope: number | null;
  ci_lower: number | null;
  ci_upper: number | null;
  sample_size: number;
  alpha: number;
  ci_level: number;
  lag1_autocorrelation: number | null;
  autocorrelation_handling: string;
  choice_documentation: string;
  interpretation: string;
  is_significant: boolean;
}

export interface SpatialSignificanceResult {
  overlay_url: string;
  geotiff_url: string;
  bounds: [[number, number], [number, number]];
  legend: SignificanceLegend;
  class_counts: {
    significant_increase: number;
    significant_decrease: number;
    not_significant: number;
    insufficient_data: number;
    not_covered: number;
  };
  min_valid_years: number;
  fdr_correction: boolean;
  alpha: number;
}

export interface SignificanceAnalysisResult {
  run_id: string;
  status: string;
  regional?: RegionalSignificanceResult | null;
  spatial?: SpatialSignificanceResult | null;
  provenance: Record<string, any>;
  warnings: string[];
}

export interface SignificanceRequestPayload {
  series_id?: string;
  change_run_id?: string;
  dataset_id: string;
  dataset_version?: string;
  variable: string;
  region_id?: string;
  geometry?: any;
  geometry_crs?: string;
  mode: 'regional' | 'spatial' | 'both';
  alpha: number;
  ci_level?: number;
  autocorrelation_method: 'auto' | 'hamed_rao' | 'pre_whitening' | 'none';
  fdr_correction: boolean;
  start_year?: number;
  end_year?: number;
  reclassify_run_id?: string;
}

/**
 * Executes or reclassifies significance analysis via POST /api/analysis/significance
 */
export async function executeSignificanceAnalysis(
  payload: SignificanceRequestPayload
): Promise<SignificanceAnalysisResult> {
  const resp = await fetch('/api/analysis/significance', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!resp.ok) {
    let errMessage = `Significance analysis request failed (${resp.status})`;
    try {
      const errData = await resp.json();
      if (errData.detail) {
        errMessage = typeof errData.detail === 'string' ? errData.detail : JSON.stringify(errData.detail);
      }
    } catch {
      // ignore
    }
    throw new Error(errMessage);
  }

  return (await resp.json()) as SignificanceAnalysisResult;
}

/**
 * Fast reclassification of an existing spatial significance run when alpha or FDR changes
 */
export async function reclassifySignificance(
  runId: string,
  alpha: number,
  fdrCorrection: boolean
): Promise<SignificanceAnalysisResult> {
  return executeSignificanceAnalysis({
    reclassify_run_id: runId,
    dataset_id: 'gpcp_monthly_v23',
    variable: 'precipitation',
    mode: 'spatial',
    alpha,
    fdr_correction: fdrCorrection,
    autocorrelation_method: 'auto',
  });
}

/**
 * Fetches cached significance result by run_id
 */
export async function fetchSignificanceResult(runId: string): Promise<SignificanceAnalysisResult> {
  const resp = await fetch(`/api/analysis/significance/${runId}`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch significance run '${runId}' (${resp.status})`);
  }
  return (await resp.json()) as SignificanceAnalysisResult;
}
