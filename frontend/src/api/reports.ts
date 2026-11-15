/**
 * Scientific Report Generation & Export API client (SPEC 10.7, 10.8, 15.4, 17.3).
 */
import { apiFetch, getApiUrl } from './client';

export interface ReportSectionsConfig {
  executive_summary: boolean;
  dataset_and_study_area: boolean;
  historical_trends: boolean;
  change_detection: boolean;
  statistical_significance: boolean;
  data_quality: boolean;
  methodology_and_references: boolean;
}

export interface ReportDownloads {
  pdf_url: string;
  csv_url: string;
  chart_png_url?: string | null;
  change_overlay_url?: string | null;
  change_geotiff_url?: string | null;
  significance_overlay_url?: string | null;
  significance_geotiff_url?: string | null;
}

export interface ReportExecutiveSummary {
  paragraphs: string[];
  key_metrics: Record<string, string>;
}

export interface ReportResponse {
  report_id: string;
  title: string;
  status: string;
  created_at: string;
  sections_enabled: ReportSectionsConfig;
  executive_summary: ReportExecutiveSummary;
  dataset_info: Record<string, any>;
  study_area: Record<string, any>;
  trends_summary: Record<string, any> | null;
  change_summary: Record<string, any> | null;
  significance_info: Record<string, any> | null;
  downloads: ReportDownloads;
}

export interface CreateReportPayload {
  title?: string;
  series_id?: string;
  change_run_id?: string;
  significance_run_id?: string;
  sections?: Partial<ReportSectionsConfig>;
}

/**
 * Creates and compiles a multi-page report from stored runs via POST /api/reports
 */
function normalizeReportResponse(report: ReportResponse): ReportResponse {
  if (report.downloads) {
    if (report.downloads.pdf_url) report.downloads.pdf_url = getApiUrl(report.downloads.pdf_url);
    if (report.downloads.csv_url) report.downloads.csv_url = getApiUrl(report.downloads.csv_url);
    if (report.downloads.chart_png_url) report.downloads.chart_png_url = getApiUrl(report.downloads.chart_png_url);
    if (report.downloads.change_overlay_url) report.downloads.change_overlay_url = getApiUrl(report.downloads.change_overlay_url);
    if (report.downloads.change_geotiff_url) report.downloads.change_geotiff_url = getApiUrl(report.downloads.change_geotiff_url);
    if (report.downloads.significance_overlay_url) report.downloads.significance_overlay_url = getApiUrl(report.downloads.significance_overlay_url);
    if (report.downloads.significance_geotiff_url) report.downloads.significance_geotiff_url = getApiUrl(report.downloads.significance_geotiff_url);
  }
  return report;
}

export async function generateReport(payload: CreateReportPayload): Promise<ReportResponse> {
  const resp = await apiFetch('/api/reports', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!resp.ok) {
    let errMessage = `Report generation request failed (${resp.status})`;
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

  const data = (await resp.json()) as ReportResponse;
  return normalizeReportResponse(data);
}

/**
 * Fetches an existing report by ID via GET /api/reports/{id}
 */
export async function fetchReport(reportId: string): Promise<ReportResponse> {
  const resp = await apiFetch(`/api/reports/${reportId}`);
  if (!resp.ok) {
    throw new Error(`Report '${reportId}' not found (${resp.status})`);
  }
  const data = (await resp.json()) as ReportResponse;
  return normalizeReportResponse(data);
}
