import React, { useState } from 'react';
import {
  FileText,
  Download,
  CheckSquare,
  Square,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  FileSpreadsheet,
  Image as ImageIcon,
  Layers,
  Sparkles,
} from 'lucide-react';
import {
  generateReport,
  type ReportResponse,
  type ReportSectionsConfig,
} from '../../api/reports';

export interface ReportGeneratorProps {
  seriesId?: string;
  changeRunId?: string;
  significanceRunId?: string;
  regionLabel?: string;
  variableName?: string;
  className?: string;
}

const SECTION_DESCRIPTIONS: Record<keyof ReportSectionsConfig, { label: string; description: string }> = {
  executive_summary: {
    label: '1. Executive Summary',
    description: 'Plain-language synthesized summary computed strictly over stored run metrics without free-written claims.',
  },
  dataset_and_study_area: {
    label: '2. Dataset and Study Area',
    description: 'Variables, collection ID, DOI, geographic bounds, CRS, spatial resolution, and temporal coverage.',
  },
  historical_trends: {
    label: '3. Historical Trend Analysis',
    description: 'Rendered timeseries chart, Theil-Sen and OLS slopes, confidence intervals, and completeness statistics.',
  },
  change_detection: {
    label: '4. Spatial Change Detection',
    description: 'Two-period differencing parameters, area-weighted mean change, domain share, and localized extremes.',
  },
  statistical_significance: {
    label: '5. Statistical Significance',
    description: 'Seasonal Mann-Kendall test, lag-1 autocorrelation correction, Benjamini-Hochberg FDR grid classes, and scientific cautions.',
  },
  data_quality: {
    label: '6. Data Quality & Limitations',
    description: 'Missing data fill-value policies (NaNs preserved), boundary cell weighting, and serial dependence.',
  },
  methodology_and_references: {
    label: '7. Methodology & References',
    description: 'Mathematical formulations, NASA/NOAA product citations, access dates, DOI links, and code provenance.',
  },
};

export const ReportGenerator: React.FC<ReportGeneratorProps> = ({
  seriesId,
  changeRunId,
  significanceRunId,
  regionLabel = 'Study Region',
  variableName = 'Precipitation',
  className = '',
}) => {
  const [reportTitle, setReportTitle] = useState<string>(
    `Gaia Insights — ${variableName} Analysis for ${regionLabel}`
  );
  const [sections, setSections] = useState<ReportSectionsConfig>({
    executive_summary: true,
    dataset_and_study_area: true,
    historical_trends: true,
    change_detection: true,
    statistical_significance: true,
    data_quality: true,
    methodology_and_references: true,
  });

  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [showPreview, setShowPreview] = useState(false);

  const toggleSection = (key: keyof ReportSectionsConfig) => {
    setSections((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  const handleGenerate = async () => {
    setError(null);
    setGenerating(true);
    try {
      const res = await generateReport({
        title: reportTitle,
        series_id: seriesId,
        change_run_id: changeRunId,
        significance_run_id: significanceRunId,
        sections,
      });
      setReport(res);
      setShowPreview(true);
    } catch (err: any) {
      setError(err?.message || 'Failed to generate scientific report.');
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div
      className={`bg-slate-900/90 border border-slate-800 rounded-xl overflow-hidden shadow-xl backdrop-blur ${className}`}
      data-testid="report-generator-container"
    >
      {/* Header */}
      <div className="px-5 py-4 bg-slate-900 border-b border-slate-800 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center space-x-2.5">
          <div className="w-8 h-8 rounded-lg bg-blue-600/20 border border-blue-500/40 flex items-center justify-center text-blue-400">
            <FileText className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white flex items-center space-x-2">
              <span>Scientific Audit Report Generator</span>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-blue-950/80 border border-blue-800 text-blue-300">
                SPEC 10.7 & 10.8
              </span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Multi-page export combining Pages 1–5 findings, citations, DOIs, and provenances.
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {report && (
            <button
              type="button"
              onClick={() => setShowPreview(!showPreview)}
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-lg text-xs font-medium transition-colors"
              data-testid="toggle-preview-button"
            >
              <span>{showPreview ? 'Hide Preview' : 'Show Preview'}</span>
              {showPreview ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>
          )}
          <button
            type="button"
            onClick={handleGenerate}
            disabled={generating}
            className="inline-flex items-center space-x-1.5 px-4 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-500 text-white font-semibold rounded-lg text-xs shadow-md transition-colors"
            data-testid="generate-report-button"
          >
            {generating ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                <span>Assembling PDF & Data...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-3.5 h-3.5 text-cyan-300" />
                <span>Compile & Export Report</span>
              </>
            )}
          </button>
        </div>
      </div>

      {error && (
        <div className="mx-5 my-3 p-3 bg-rose-950/40 border border-rose-800 rounded-lg text-rose-300 text-xs flex items-center space-x-2">
          <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Main Form Body */}
      <div className="p-5 space-y-4">
        {/* Title Input */}
        <div>
          <label className="block text-xs font-medium text-slate-300 mb-1">
            Report Document Title
          </label>
          <input
            type="text"
            value={reportTitle}
            onChange={(e) => setReportTitle(e.target.value)}
            className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500 font-medium"
          />
        </div>

        {/* Section Checkboxes (SPEC 10.7) */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
              Choose Report Sections (SPEC 10.7)
            </span>
            <span className="text-[11px] text-slate-400">All enabled by default</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
            {(Object.keys(SECTION_DESCRIPTIONS) as Array<keyof ReportSectionsConfig>).map((key) => {
              const item = SECTION_DESCRIPTIONS[key];
              const isChecked = sections[key];
              return (
                <div
                  key={key}
                  onClick={() => toggleSection(key)}
                  className={`p-2.5 rounded-lg border cursor-pointer transition-all flex items-start space-x-3 select-none ${
                    isChecked
                      ? 'bg-slate-950/80 border-blue-500/40 hover:border-blue-500/60'
                      : 'bg-slate-950/40 border-slate-800 opacity-60 hover:opacity-80'
                  }`}
                  data-testid={`section-toggle-${key}`}
                >
                  <div className="mt-0.5 text-blue-400">
                    {isChecked ? (
                      <CheckSquare className="w-4 h-4 text-blue-400" />
                    ) : (
                      <Square className="w-4 h-4 text-slate-600" />
                    )}
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-slate-200">{item.label}</div>
                    <div className="text-[10.5px] text-slate-400 leading-snug mt-0.5">
                      {item.description}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Download Buttons Bar (Visible once report is compiled) */}
        {report && (
          <div
            className="p-4 rounded-xl bg-slate-950 border border-blue-900/50 shadow-inner space-y-3"
            data-testid="report-downloads-panel"
          >
            <div className="flex flex-wrap items-center justify-between gap-2 pb-2.5 border-b border-slate-800">
              <div className="flex items-center space-x-2 text-xs">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span className="text-slate-200 font-semibold">Report Generated:</span>
                <span className="font-mono text-cyan-300 text-[11px] bg-slate-900 px-2 py-0.5 rounded border border-slate-800">
                  {report.report_id}
                </span>
              </div>
              <span className="text-[11px] text-slate-400">
                Created: {new Date(report.created_at).toLocaleTimeString()} UTC
              </span>
            </div>

            {/* Direct Download Actions (SPEC 10.8) */}
            <div className="flex flex-wrap items-center gap-2">
              <a
                href={report.downloads.pdf_url}
                download
                className="inline-flex items-center space-x-1.5 px-3.5 py-2 bg-rose-600 hover:bg-rose-500 text-white font-semibold rounded-lg text-xs shadow transition-colors"
                data-testid="download-pdf-button"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Download Report PDF</span>
              </a>

              <a
                href={report.downloads.csv_url}
                download
                className="inline-flex items-center space-x-1.5 px-3 py-2 bg-emerald-700 hover:bg-emerald-600 text-white font-semibold rounded-lg text-xs shadow transition-colors"
                data-testid="download-csv-button"
              >
                <FileSpreadsheet className="w-3.5 h-3.5" />
                <span>Export Series CSV</span>
              </a>

              {report.downloads.chart_png_url && (
                <a
                  href={report.downloads.chart_png_url}
                  download={`chart_${report.report_id}.png`}
                  className="inline-flex items-center space-x-1 px-2.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 rounded-lg text-xs font-medium transition-colors"
                >
                  <ImageIcon className="w-3.5 h-3.5 text-blue-400" />
                  <span>Chart PNG</span>
                </a>
              )}

              {report.downloads.change_geotiff_url && (
                <a
                  href={report.downloads.change_geotiff_url}
                  download
                  className="inline-flex items-center space-x-1 px-2.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 rounded-lg text-xs font-medium transition-colors"
                >
                  <Layers className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Difference GeoTIFF</span>
                </a>
              )}

              {report.downloads.significance_geotiff_url && (
                <a
                  href={report.downloads.significance_geotiff_url}
                  download
                  className="inline-flex items-center space-x-1 px-2.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 rounded-lg text-xs font-medium transition-colors"
                >
                  <Layers className="w-3.5 h-3.5 text-purple-400" />
                  <span>Significance GeoTIFF</span>
                </a>
              )}
            </div>
          </div>
        )}

        {/* Live Interactive Preview Drawer */}
        {report && showPreview && (
          <div
            className="p-5 rounded-xl bg-slate-950 border border-slate-800 text-xs space-y-4 font-sans text-slate-300 leading-relaxed shadow-2xl"
            data-testid="report-preview-panel"
          >
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div>
                <h4 className="text-sm font-bold text-white">{report.title}</h4>
                <div className="text-[11px] text-slate-400 flex items-center space-x-2 mt-0.5">
                  <span>DOI: {report.dataset_info.doi}</span>
                  <span>•</span>
                  <span>Provider: {report.dataset_info.provider}</span>
                </div>
              </div>
              <span className="text-[11px] font-mono text-cyan-300 bg-slate-900 px-2 py-0.5 rounded border border-slate-800">
                {report.report_id}
              </span>
            </div>

            {/* Synthesized Executive Summary Preview */}
            {report.sections_enabled.executive_summary && (
              <div className="p-3.5 rounded-lg bg-emerald-950/20 border border-emerald-900/50 space-y-2">
                <span className="text-[11px] font-bold text-emerald-300 uppercase tracking-wider">
                  Executive Summary Findings (Strictly Template-Generated)
                </span>
                {report.executive_summary.paragraphs.map((para, idx) => (
                  <p key={idx} className="text-slate-200 text-xs leading-relaxed">
                    {para}
                  </p>
                ))}
              </div>
            )}

            {/* Scientific Caveat / Limitations Callout */}
            {report.dataset_info?.caveat && (
              <div className="p-3 rounded-lg bg-amber-950/25 border border-amber-800/50 space-y-1 text-xs">
                <div className="flex items-center gap-1.5 font-bold text-amber-400 text-[11px] uppercase font-mono tracking-wider">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  <span>Variable-Specific Scientific Caveat</span>
                </div>
                <p className="text-amber-200/90 text-[11px] leading-relaxed">
                  {report.dataset_info.caveat}
                </p>
              </div>
            )}

            {/* Numbers Table Preview */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
              {report.trends_summary && report.sections_enabled.historical_trends && (
                <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 space-y-1">
                  <div className="text-[10px] uppercase tracking-wider text-slate-400 font-bold">
                    Historical Trend Analysis
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Regional Mean:</span>
                    <span className="font-mono text-white font-semibold">
                      {report.trends_summary.mean?.toFixed(2)} {report.trends_summary.units}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Sen's Slope:</span>
                    <span className="font-mono text-cyan-400 font-semibold">
                      {report.trends_summary.sens_slope > 0 ? '+' : ''}
                      {report.trends_summary.sens_slope?.toFixed(3)}/yr
                    </span>
                  </div>
                </div>
              )}

              {report.change_summary && report.sections_enabled.change_detection && (
                <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 space-y-1">
                  <div className="text-[10px] uppercase tracking-wider text-slate-400 font-bold">
                    Spatial Change Detection
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Area Mean Change:</span>
                    <span className="font-mono text-white font-semibold">
                      {report.change_summary.area_weighted_mean_change > 0 ? '+' : ''}
                      {report.change_summary.area_weighted_mean_change?.toFixed(2)} mm/yr
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Share Increasing:</span>
                    <span className="font-mono text-emerald-400 font-semibold">
                      {report.change_summary.share_increasing_pct?.toFixed(1)}%
                    </span>
                  </div>
                </div>
              )}

              {report.significance_info && report.sections_enabled.statistical_significance && (
                <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 space-y-1">
                  <div className="text-[10px] uppercase tracking-wider text-slate-400 font-bold">
                    Significance Evaluation
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Raw p-value:</span>
                    <span className="font-mono text-cyan-400 font-semibold">
                      {report.significance_info.regional?.raw_p_value?.toFixed(4)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">FDR Sig. Increase:</span>
                    <span className="font-mono text-emerald-400 font-semibold">
                      {report.significance_info.spatial?.class_counts?.significant_increase} cells
                    </span>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
