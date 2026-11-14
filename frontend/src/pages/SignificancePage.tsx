import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useSession } from '../store/session';
import {
  executeSignificanceAnalysis,
  reclassifySignificance,
  fetchSignificanceResult,
  type SignificanceAnalysisResult,
  type RegionalSignificanceResult,
  type SpatialSignificanceResult,
} from '../api/significance';
import { SignificanceMapViewer } from '../components/map/SignificanceMapViewer';
import { ReportGenerator } from '../components/report/ReportGenerator';
import { StepIndicator } from '../components/StepIndicator';
import {
  AlertTriangle,
  ArrowLeft,
  ChevronDown,
  ChevronUp,
  FileCheck,
  Info,
  Layers,
  Minus,
  RefreshCw,
  Scale,
  ShieldCheck,
  CheckCircle2,
} from 'lucide-react';

export const SignificancePage: React.FC = () => {
  const session = useSession();

  // Inputs from session store (SPEC 3.3 & Rule 1: No fabricated fallback geometry)
  const hasConfiguredInputs = session.selectedVariables.length > 0 && !!session.region;
  const selectedVariable = session.selectedVariables[0];
  const region = session.region;

  // State
  const [analysisMode, setAnalysisMode] = useState<'regional' | 'spatial' | 'both'>('both');
  const [activeView, setActiveView] = useState<'regional' | 'spatial'>('spatial');
  const [alpha, setAlpha] = useState<number>(0.05);
  const confidenceLevel = useMemo(() => 1 - alpha, [alpha]);
  const [autocorrelationMethod, setAutocorrelationMethod] = useState<
    'auto' | 'hamed_rao' | 'pre_whitening' | 'none'
  >('auto');
  const [fdrCorrection, setFdrCorrection] = useState<boolean>(true);

  const [loading, setLoading] = useState<boolean>(false);
  const [reclassifying, setReclassifying] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SignificanceAnalysisResult | null>(null);
  const [showMethodology, setShowMethodology] = useState<boolean>(false);

  // Recommended method rationale
  const recommendedMethodRationale = useMemo(() => {
    return 'Seasonal Mann-Kendall with Hamed-Rao correction: robust non-parametric test accounting for 12-month seasonality and lag-1 serial autocorrelation without assuming normal distributions.';
  }, []);

  // Run or load analysis
  const handleRunAnalysis = useCallback(
    async (isReclassifyOnly: boolean = false) => {
      setError(null);
      if (!selectedVariable || !region) return;
      if (isReclassifyOnly && result?.run_id) {
        setReclassifying(true);
        try {
          const reclassRes = await reclassifySignificance(result.run_id, alpha, fdrCorrection);
          setResult(reclassRes);
          session.setPage5ResultId(reclassRes.run_id);
        } catch (err: any) {
          const reqId = err?.requestId || `err_${Date.now().toString(36)}`;
          setError(`${err?.message || 'Failed to reclassify spatial significance.'} (Request/Job ID: ${reqId})`);
        } finally {
          setReclassifying(false);
        }
        return;
      }

      setLoading(true);
      try {
        const payload = {
          series_id: session.page3ResultId,
          change_run_id: session.page4ResultId,
          dataset_id: selectedVariable.datasetId || 'gpcp_monthly_v23',
          dataset_version: selectedVariable.datasetVersion || 'v2.3',
          variable: selectedVariable.variableId || 'precipitation',
          geometry: region.geometry,
          mode: 'both' as const,
          alpha,
          ci_level: confidenceLevel,
          autocorrelation_method: autocorrelationMethod,
          fdr_correction: fdrCorrection,
          start_year: 1990,
          end_year: 2025,
        };

        const res = await executeSignificanceAnalysis(payload);
        setResult(res);
        session.setPage5ResultId(res.run_id);
      } catch (err: any) {
        const reqId = err?.requestId || `err_${Date.now().toString(36)}`;
        setError(`${err?.message || 'Significance analysis failed.'} (Request/Job ID: ${reqId})`);
      } finally {
        setLoading(false);
      }
    },
    [
      result?.run_id,
      alpha,
      fdrCorrection,
      session.page3ResultId,
      session.page4ResultId,
      selectedVariable,
      region,
      confidenceLevel,
      autocorrelationMethod,
    ]
  );

  // Initial load: restore cached run or compute
  useEffect(() => {
    let isMounted = true;
    const loadInitial = async () => {
      if (!hasConfiguredInputs) return;
      if (session.page5ResultId) {
        try {
          const cached = await fetchSignificanceResult(session.page5ResultId);
          if (isMounted) {
            setResult(cached);
            return;
          }
        } catch {
          // If cached run is unavailable, compute fresh
        }
      }
      handleRunAnalysis(false);
    };

    loadInitial();
    return () => {
      isMounted = false;
    };
  }, [hasConfiguredInputs]);

  // Handle alpha or FDR toggle change: triggers fast reclassification if run exists
  const handleAlphaChange = (newAlpha: number) => {
    setAlpha(newAlpha);
    if (result?.run_id) {
      setReclassifying(true);
      reclassifySignificance(result.run_id, newAlpha, fdrCorrection)
        .then((reclassRes) => setResult(reclassRes))
        .catch((err) => setError(err?.message))
        .finally(() => setReclassifying(false));
    }
  };

  const handleFdrToggle = (newFdr: boolean) => {
    setFdrCorrection(newFdr);
    if (result?.run_id) {
      setReclassifying(true);
      reclassifySignificance(result.run_id, alpha, newFdr)
        .then((reclassRes) => setResult(reclassRes))
        .catch((err) => setError(err?.message))
        .finally(() => setReclassifying(false));
    }
  };

  const regional: RegionalSignificanceResult | undefined = result?.regional || undefined;
  const spatial: SpatialSignificanceResult | undefined = result?.spatial || undefined;

  if (!hasConfiguredInputs || !selectedVariable || !region) {
    return (
      <div className="flex flex-col min-h-screen bg-slate-950 text-slate-100 font-sans">
        <div className="bg-slate-900/60 border-b border-slate-800">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <StepIndicator currentStep={5} />
              <h1 className="text-lg font-bold text-slate-100">
                Page 5: Significance & Evidence Evaluation
              </h1>
            </div>
          </div>
        </div>

        <main className="flex-1 max-w-3xl w-full mx-auto px-4 sm:px-6 py-16 text-center">
          <div className="p-8 rounded-2xl bg-slate-900 border border-slate-800 shadow-xl space-y-4">
            <div className="w-12 h-12 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 flex items-center justify-center mx-auto">
              <FileCheck className="w-6 h-6" />
            </div>
            <h2 className="text-lg font-bold text-white">No Dataset or Study Region Configured</h2>
            <p className="text-sm text-slate-400 max-w-md mx-auto leading-relaxed">
              Per Scientific Non-Negotiable Rule 1, Earth Science Explorer never computes or displays placeholder numbers. Please select an Earth-science variable and define your study region to begin significance evaluation.
            </p>
            <div className="flex justify-center gap-3 pt-3">
              <Link
                to="/explore"
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-cyan-300 text-xs font-semibold rounded-lg transition-colors"
              >
                1. Select Variable
              </Link>
              <Link
                to="/region"
                className="px-4 py-2 bg-gradient-to-r from-accent-blue to-accent-cyan text-navy-950 font-bold text-xs rounded-lg transition-colors"
              >
                2. Select Geography
              </Link>
            </div>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen bg-slate-950 text-slate-100">
      {/* Top Breadcrumb & Step Navigation */}
      <div className="border-b border-slate-800 bg-slate-900/60 px-6 py-3">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4">
          <div>
            <StepIndicator currentStep={5} />
            <h1 className="text-xl font-bold text-white mt-1">
              Significance & Evidence Evaluation
            </h1>
            <p className="text-xs text-slate-400">
              Inferential hypothesis testing on underlying historical time samples (SPEC Section 10).
            </p>
          </div>
          <div className="flex items-center space-x-3 text-xs">
            <Link
              to="/changes"
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded border border-slate-700 transition-colors"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>4. Change Detection</span>
            </Link>
            {result?.run_id && (
              <span
                className="font-mono text-[11px] px-2 py-1 rounded bg-slate-800/80 border border-slate-700 text-cyan-300"
                data-testid="significance-run-id"
              >
                run: {result.run_id}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Main 3-Column Content (23% / 52% / 25%) */}
      <div className="max-w-7xl mx-auto w-full px-4 sm:px-6 py-6 flex-1 flex flex-col gap-6">
        {error && (
          <div
            className="p-3 bg-rose-950/40 border border-rose-800 rounded-lg text-rose-300 text-xs flex items-center space-x-2"
            role="alert"
          >
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* ========================================================= */}
          {/* LEFT PANEL: Analysis Settings (SPEC 10.1, 10.2)            */}
          {/* ========================================================= */}
          <div className="lg:col-span-3 space-y-4 bg-slate-900/80 border border-slate-800/80 rounded-xl p-4 shadow-lg backdrop-blur">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800">
              <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center space-x-1.5">
                <Scale className="w-3.5 h-3.5 text-cyan-400" />
                <span>Test Settings</span>
              </span>
              {(loading || reclassifying) && (
                <RefreshCw className="w-3.5 h-3.5 text-blue-400 animate-spin" />
              )}
            </div>

            {/* Recommended Method Banner */}
            <div className="p-2.5 rounded-lg bg-blue-950/40 border border-blue-900/60 text-[11px] text-blue-300 space-y-1">
              <div className="flex items-center space-x-1 font-semibold text-blue-200">
                <ShieldCheck className="w-3.5 h-3.5 text-blue-400" />
                <span>Recommended Method</span>
              </div>
              <p className="text-slate-300 leading-relaxed text-[11px]">
                {recommendedMethodRationale}
              </p>
            </div>

            {/* Scope / Mode Toggle */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-300">Analysis Mode</label>
              <div className="grid grid-cols-2 gap-1 p-1 bg-slate-950 rounded-lg border border-slate-800">
                <button
                  type="button"
                  onClick={() => {
                    setAnalysisMode('regional');
                    setActiveView('regional');
                  }}
                  className={`py-1 text-xs font-medium rounded transition-colors ${
                    analysisMode === 'regional'
                      ? 'bg-blue-600 text-white'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Regional
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setAnalysisMode('spatial');
                    setActiveView('spatial');
                  }}
                  className={`py-1 text-xs font-medium rounded transition-colors ${
                    analysisMode === 'spatial' || analysisMode === 'both'
                      ? 'bg-blue-600 text-white'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Spatial Grid
                </button>
              </div>
            </div>

            {/* Significance Threshold (Alpha) */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-xs font-medium text-slate-300">
                  Threshold (α)
                </label>
                <span className="text-[11px] font-mono text-cyan-300 bg-cyan-950/60 px-1.5 py-0.5 rounded border border-cyan-800">
                  {alpha}
                </span>
              </div>
              <div className="grid grid-cols-3 gap-1">
                {[0.01, 0.05, 0.1].map((val) => (
                  <button
                    key={val}
                    type="button"
                    onClick={() => handleAlphaChange(val)}
                    className={`py-1 text-xs font-mono rounded border transition-colors ${
                      alpha === val
                        ? 'bg-blue-600/30 border-blue-500 text-blue-200 font-bold'
                        : 'bg-slate-800/60 border-slate-700 text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    α = {val}
                  </button>
                ))}
              </div>
              <p className="text-[10px] text-slate-400">
                α = 0.05 corresponds to 95% confidence level.
              </p>
            </div>

            {/* Autocorrelation Option */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-300 flex items-center justify-between">
                <span>Autocorrelation Handling</span>
                <span className="text-[10px] text-slate-400">SPEC 10.6</span>
              </label>
              <select
                value={autocorrelationMethod}
                onChange={(e) =>
                  setAutocorrelationMethod(e.target.value as any)
                }
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
              >
                <option value="auto">Auto (Hamed-Rao if r₁ &gt; 0.10)</option>
                <option value="hamed_rao">Hamed-Rao Variance Correction</option>
                <option value="pre_whitening">Pre-Whitening (TFPW)</option>
                <option value="none">None (Standard MK)</option>
              </select>
            </div>

            {/* Multiple-Testing Option (Benjamini-Hochberg FDR) */}
            <div className="pt-2 border-t border-slate-800 space-y-2">
              <div className="flex items-start space-x-2">
                <input
                  type="checkbox"
                  id="fdrCheckbox"
                  checked={fdrCorrection}
                  onChange={(e) => handleFdrToggle(e.target.checked)}
                  className="mt-0.5 rounded border-slate-700 bg-slate-950 text-blue-600 focus:ring-blue-500 focus:ring-offset-slate-900"
                />
                <label htmlFor="fdrCheckbox" className="text-xs text-slate-200 font-medium">
                  Benjamini-Hochberg FDR
                </label>
              </div>
              <p className="text-[11px] text-slate-400 leading-normal pl-5">
                Controls False Discovery Rate across thousands of grid tests to suppress
                spurious spatial false positives.
              </p>
            </div>

            {/* Run Button */}
            <button
              type="button"
              disabled={loading || reclassifying}
              onClick={() => handleRunAnalysis(false)}
              className="w-full mt-2 py-2 px-3 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-500 text-white rounded-lg font-medium text-xs shadow-md transition-colors flex items-center justify-center space-x-1.5"
            >
              {loading ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>Computing Significance...</span>
                </>
              ) : (
                <>
                  <Scale className="w-3.5 h-3.5" />
                  <span>Re-evaluate Significance</span>
                </>
              )}
            </button>

            {/* Upstream Data Provenance Card */}
            <div className="pt-2 border-t border-slate-800 text-[11px] text-slate-400 space-y-1">
              <div className="flex items-center justify-between">
                <span>Dataset:</span>
                <span className="font-mono text-slate-200">
                  {selectedVariable.datasetId} ({selectedVariable.datasetVersion})
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span>Region:</span>
                <span className="text-slate-200 truncate max-w-[130px]">
                  {region.label}
                </span>
              </div>
            </div>
          </div>

          {/* ========================================================= */}
          {/* CENTRE PANEL: Significance Visualisation (SPEC 10.1, 10.4)  */}
          {/* ========================================================= */}
          <div className="lg:col-span-6 space-y-4">
            {/* View Switcher Header */}
            <div className="flex items-center justify-between bg-slate-900/80 p-2 rounded-xl border border-slate-800">
              <div className="flex items-center space-x-1.5">
                <button
                  type="button"
                  onClick={() => setActiveView('spatial')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors flex items-center space-x-1.5 ${
                    activeView === 'spatial'
                      ? 'bg-blue-600 text-white shadow'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                  }`}
                  data-testid="view-spatial-button"
                >
                  <Layers className="w-3.5 h-3.5" />
                  <span>Spatial Significance Map</span>
                </button>
                <button
                  type="button"
                  onClick={() => setActiveView('regional')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors flex items-center space-x-1.5 ${
                    activeView === 'regional'
                      ? 'bg-blue-600 text-white shadow'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                  }`}
                  data-testid="view-regional-button"
                >
                  <FileCheck className="w-3.5 h-3.5" />
                  <span>Regional Trend Test</span>
                </button>
              </div>

              {/* Status Indicator */}
              <div className="text-[11px] text-slate-400">
                {activeView === 'spatial' && spatial?.legend && (
                  <span className="text-cyan-300 font-mono text-[11px]">
                    {spatial.legend.p_value_mode}
                  </span>
                )}
              </div>
            </div>

            {/* View Canvas */}
            {activeView === 'spatial' ? (
              <div className="space-y-3">
                <SignificanceMapViewer
                  runId={spatial ? result?.run_id : undefined}
                  overlayUrl={spatial?.overlay_url}
                  geotiffUrl={spatial?.geotiff_url}
                  bounds={spatial?.bounds}
                  legend={spatial?.legend}
                  geometry={region.geometry}
                  className="min-h-[460px]"
                />
              </div>
            ) : (
              <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                  <div>
                    <h3 className="text-sm font-bold text-white flex items-center space-x-2">
                      <span>Regional Non-Parametric Trend Assessment</span>
                      {regional?.is_significant ? (
                        <span className="px-2 py-0.5 rounded text-[11px] bg-emerald-950/80 border border-emerald-800 text-emerald-300 font-semibold">
                          Reject H₀ (p &lt; {alpha})
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded text-[11px] bg-amber-950/80 border border-amber-800 text-amber-300 font-semibold">
                          Fail to Reject H₀
                        </span>
                      )}
                    </h3>
                    <p className="text-xs text-slate-400 mt-0.5">
                      {regional?.test_name || 'Mann-Kendall Trend Test'}
                    </p>
                  </div>
                </div>

                {/* Null Hypothesis Card */}
                <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs space-y-1">
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                    Null Hypothesis (H₀)
                  </span>
                  <p className="text-slate-200 italic">
                    "{regional?.null_hypothesis}"
                  </p>
                </div>

                {/* Regional Test Key Numbers Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="p-3 rounded-lg bg-slate-950/70 border border-slate-800/80">
                    <span className="text-[10px] text-slate-400 uppercase tracking-wider">
                      p-value
                    </span>
                    <div
                      className="text-base font-bold font-mono text-cyan-400 mt-0.5"
                      data-testid="regional-p-value"
                    >
                      {regional?.raw_p_value !== null && regional?.raw_p_value !== undefined
                        ? regional.raw_p_value < 0.0001
                          ? '< 0.0001'
                          : regional.raw_p_value.toFixed(4)
                        : '—'}
                    </div>
                  </div>

                  <div className="p-3 rounded-lg bg-slate-950/70 border border-slate-800/80">
                    <span className="text-[10px] text-slate-400 uppercase tracking-wider">
                      Sen's Slope
                    </span>
                    <div className="text-base font-bold font-mono text-white mt-0.5">
                      {regional?.sens_slope !== null && regional?.sens_slope !== undefined
                        ? `${regional.sens_slope > 0 ? '+' : ''}${regional.sens_slope.toFixed(3)} ${selectedVariable.units}/yr`
                        : '—'}
                    </div>
                  </div>

                  <div className="p-3 rounded-lg bg-slate-950/70 border border-slate-800/80">
                    <span className="text-[10px] text-slate-400 uppercase tracking-wider">
                      95% Conf. Interval
                    </span>
                    <div className="text-xs font-bold font-mono text-slate-200 mt-1">
                      {regional?.ci_lower !== null && regional?.ci_upper !== null
                        ? `[${regional?.ci_lower}, ${regional?.ci_upper}]`
                        : '—'}
                    </div>
                  </div>

                  <div className="p-3 rounded-lg bg-slate-950/70 border border-slate-800/80">
                    <span className="text-[10px] text-slate-400 uppercase tracking-wider">
                      Sample Size (n)
                    </span>
                    <div className="text-base font-bold font-mono text-slate-200 mt-0.5">
                      {regional?.sample_size || '—'}
                    </div>
                  </div>
                </div>

                {/* Autocorrelation & Correction Applied */}
                <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs space-y-1">
                  <div className="flex items-center justify-between text-slate-300">
                    <span className="font-medium">Lag-1 Autocorrelation (r₁):</span>
                    <span className="font-mono text-cyan-300">
                      {regional?.lag1_autocorrelation !== null && regional?.lag1_autocorrelation !== undefined
                        ? regional.lag1_autocorrelation.toFixed(3)
                        : '—'}
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-400">
                    <span className="font-semibold text-slate-300">Adjustment: </span>
                    {regional?.choice_documentation}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* ========================================================= */}
          {/* RIGHT PANEL: Statistical Results & Interpretations (10.5)  */}
          {/* ========================================================= */}
          <div className="lg:col-span-3 space-y-4 bg-slate-900/80 border border-slate-800/80 rounded-xl p-4 shadow-lg backdrop-blur">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800">
              <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center space-x-1.5">
                <FileCheck className="w-3.5 h-3.5 text-blue-400" />
                <span>Statistical Findings</span>
              </span>
              <span className="text-[10px] font-mono text-slate-400">SPEC 10.5</span>
            </div>

            {/* Key Summary Cards */}
            <div className="space-y-2">
              <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 flex items-center justify-between">
                <div>
                  <div className="text-[10px] uppercase tracking-wider text-slate-400">
                    Significance Status
                  </div>
                  <div className="text-sm font-bold text-white mt-0.5">
                    {regional?.is_significant ? (
                      <span className="text-emerald-400 flex items-center space-x-1">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>Significant Trend</span>
                      </span>
                    ) : (
                      <span className="text-slate-300 flex items-center space-x-1">
                        <Minus className="w-3.5 h-3.5 text-slate-400" />
                        <span>No Significant Trend</span>
                      </span>
                    )}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-[10px] uppercase tracking-wider text-slate-400">
                    p-value
                  </div>
                  <div className="font-mono text-sm font-bold text-cyan-300">
                    {regional?.raw_p_value !== null && regional?.raw_p_value !== undefined
                      ? regional.raw_p_value < 0.0001
                        ? '< 0.0001'
                        : regional.raw_p_value.toFixed(4)
                      : '—'}
                  </div>
                </div>
              </div>

              {/* Spatial Class Breakdown (if spatial results available) */}
              {spatial?.class_counts && (
                <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 space-y-1.5">
                  <div className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">
                    Spatial Grid Classes ({spatial.fdr_correction ? 'FDR Adjusted' : 'Raw'})
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="text-cyan-400 font-medium">Increase (+):</span>
                      <span className="font-mono text-white">
                        {spatial.class_counts.significant_increase}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-orange-400 font-medium">Decrease (−):</span>
                      <span className="font-mono text-white">
                        {spatial.class_counts.significant_decrease}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-slate-400">Not Sig (o):</span>
                      <span className="font-mono text-slate-300">
                        {spatial.class_counts.not_significant}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-amber-400">Low Data (?):</span>
                      <span className="font-mono text-slate-300">
                        {spatial.class_counts.insufficient_data}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Plain-Language Interpretation (SPEC 10.5 & 10.6) */}
            <div className="space-y-2 pt-2 border-t border-slate-800">
              <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center space-x-1.5">
                <Info className="w-3.5 h-3.5 text-cyan-400" />
                <span>Plain-Language Reading</span>
              </span>

              <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 text-[11px] text-slate-300 leading-relaxed space-y-2">
                <p>{regional?.interpretation}</p>
              </div>

              {/* Strict Scientific Non-Negotiables & Cautions (SPEC 10.6) */}
              <div className="p-2.5 rounded-lg bg-amber-950/30 border border-amber-900/60 text-[11px] text-amber-200/90 space-y-1.5">
                <div className="flex items-center space-x-1 font-semibold text-amber-300">
                  <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                  <span>Interpretation Cautions (SPEC 10.6)</span>
                </div>
                <ul className="list-disc pl-4 space-y-1 text-slate-300 text-[10.5px]">
                  <li>
                    A <strong>p-value is not</strong> the probability that the null hypothesis is true.
                  </li>
                  <li>
                    Statistical significance <strong>does not equal</strong> large environmental importance.
                  </li>
                  <li>
                    An observed trend <strong>does not establish</strong> a causal mechanism.
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </div>

        {/* ========================================================= */}
        {/* BOTTOM PANEL: Expandable Data Quality & Methodology (10.1) */}
        {/* ========================================================= */}
        <div className="bg-slate-900/80 border border-slate-800/80 rounded-xl overflow-hidden shadow-lg backdrop-blur">
          <button
            type="button"
            onClick={() => setShowMethodology(!showMethodology)}
            className="w-full px-5 py-3.5 flex items-center justify-between text-left hover:bg-slate-800/50 transition-colors"
            data-testid="toggle-methodology-button"
          >
            <div className="flex items-center space-x-2">
              <Scale className="w-4 h-4 text-cyan-400" />
              <span className="text-xs font-bold text-white uppercase tracking-wider">
                Data Quality, Methodology & Limitations (SPEC 10.1, 14.6 - 14.8)
              </span>
            </div>
            {showMethodology ? (
              <ChevronUp className="w-4 h-4 text-slate-400" />
            ) : (
              <ChevronDown className="w-4 h-4 text-slate-400" />
            )}
          </button>

          {showMethodology && (
            <div className="p-5 border-t border-slate-800 grid grid-cols-1 md:grid-cols-3 gap-6 text-xs text-slate-300">
              <div className="space-y-2">
                <h4 className="font-semibold text-white flex items-center space-x-1.5">
                  <Info className="w-3.5 h-3.5 text-blue-400" />
                  <span>Dataset & Coverage Rules</span>
                </h4>
                <ul className="space-y-1 text-slate-400 text-[11.5px]">
                  <li>
                    • <strong>Collection:</strong> {selectedVariable.datasetId} ({selectedVariable.datasetVersion})
                  </li>
                  <li>
                    • <strong>Resolution:</strong> 2.5° × 2.5° equal-angle grid, Monthly
                  </li>
                  <li>
                    • <strong>Missing Data:</strong> Decoded to NaN; never silently zeroed
                  </li>
                  <li>
                    • <strong>Minimum Sample:</strong> ≥ 10 valid annual points required per cell
                  </li>
                </ul>
              </div>

              <div className="space-y-2">
                <h4 className="font-semibold text-white flex items-center space-x-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Autocorrelation & Serial Dependence</span>
                </h4>
                <p className="text-[11.5px] text-slate-400 leading-relaxed">
                  Monthly climate observations exhibit strong serial dependence. Uncorrected Mann-Kendall tests
                  underestimate p-values in presence of positive autocorrelation. The Hamed-Rao variance inflation
                  factor adjusts the test statistic variance using empirical autocorrelation coefficients.
                </p>
              </div>

              <div className="space-y-2">
                <h4 className="font-semibold text-white flex items-center space-x-1.5">
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                  <span>Spatial Multiple-Testing Limitations</span>
                </h4>
                <p className="text-[11.5px] text-slate-400 leading-relaxed">
                  Testing thousands of grid cells simultaneously inflates family-wise error. Benjamini-Hochberg
                  controls the False Discovery Rate (FDR). However, spatial autocorrelation among adjacent grid cells
                  means test statistics are not strictly independent, which may slightly alter effective error rates.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* ========================================================= */}
        {/* REPORT GENERATOR & EXPORTS CENTER (SPEC 10.7, 10.8)       */}
        {/* ========================================================= */}
        <ReportGenerator
          seriesId={session.page3ResultId}
          changeRunId={session.page4ResultId}
          significanceRunId={result?.run_id || session.page5ResultId}
          regionLabel={region.label}
          variableName={selectedVariable.variableId}
        />
      </div>
    </div>
  );
};
