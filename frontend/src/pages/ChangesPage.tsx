import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useSession } from '../store/session';
import {
  executeChangeMapAnalysis,
  type ChangeMapResult,
} from '../api/change';
import { ChangeMapViewer } from '../components/map/ChangeMapViewer';
import { StepIndicator } from '../components/StepIndicator';
import { StatusChip } from '../components/StatusChip';
import {
  AlertTriangle,
  ArrowRight,
  Info,
  Layers,
  MapPin,
  RefreshCw,
  TrendingDown,
  TrendingUp,
  AlertCircle,
  FileText,
  Calendar,
  Compass,
  Sliders,
  Sparkles,
} from 'lucide-react';

export const ChangesPage: React.FC = () => {
  const session = useSession();

  // 1. Inherited inputs from session store (SPEC 3.3 & Rule 1: No fabricated fallback geometry)
  const hasConfiguredInputs = session.selectedVariables.length > 0 && !!session.region;
  const selectedVariable = session.selectedVariables[0];
  const region = session.region;

  // 2. Settings state (dynamically clamped to real dataset coverage)
  const variableId = selectedVariable?.variableId || 'precipitation';
  const minCoverageYear = useMemo(() => {
    if (variableId === 'soil_moisture' || selectedVariable?.datasetId?.includes('gldas')) return 2000;
    if (variableId === 'sea_surface_temperature' || selectedVariable?.datasetId?.includes('oisst')) return 1981;
    if (variableId === 'temperature' || selectedVariable?.datasetId?.includes('merra2')) return 1980;
    return 1979;
  }, [variableId, selectedVariable]);

  const maxCoverageYear = 2025; // Latest complete year (Rule 5)

  const defaultBStart = minCoverageYear >= 2000 ? 2000 : 1990;
  const defaultBEnd = minCoverageYear >= 2000 ? 2010 : 2005;
  const defaultCStart = minCoverageYear >= 2000 ? 2011 : 2006;

  const [baselineStartYear, setBaselineStartYear] = useState<number>(defaultBStart);
  const [baselineEndYear, setBaselineEndYear] = useState<number>(defaultBEnd);

  const [comparisonStartYear, setComparisonStartYear] = useState<number>(defaultCStart);
  const [comparisonEndYear, setComparisonEndYear] = useState<number>(2025);

  const [allowOverlap, setAllowOverlap] = useState<boolean>(false);
  const [metric, setMetric] = useState<'absolute' | 'percentage' | 'spatial_trend'>('absolute');
  const [aggregation, setAggregation] = useState<'annual' | 'monthly'>('annual');

  // 3. Results state
  const [result, setResult] = useState<ChangeMapResult | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Stale detection
  const [loadedInputs, setLoadedInputs] = useState<{
    variableId: string;
    regionLabel: string;
    bStart: number;
    bEnd: number;
    cStart: number;
    cEnd: number;
    metric: string;
    aggregation: string;
  } | null>(null);

  // Check period overlap
  const isOverlapping = useMemo(() => {
    return Math.max(baselineStartYear, comparisonStartYear) <= Math.min(baselineEndYear, comparisonEndYear);
  }, [baselineStartYear, baselineEndYear, comparisonStartYear, comparisonEndYear]);

  // Execute Analysis
  const runAnalysis = useCallback(async () => {
    if (!selectedVariable || !region) return;
    if (isOverlapping && !allowOverlap) {
      setError('Baseline and comparison periods overlap. You must explicitly confirm overlap to proceed.');
      return;
    }

    setLoading(true);
    setError(null);

    const payload = {
      dataset_id: selectedVariable.datasetId || 'gpcp_monthly_v23',
      dataset_version: selectedVariable.datasetVersion || 'v2.3',
      variable: selectedVariable.variableId || 'precipitation',
      geometry: region.geometry,
      geometry_crs: region.crs || 'EPSG:4326',
      baseline_period: [baselineStartYear, baselineEndYear] as [number, number],
      comparison_period: [comparisonStartYear, comparisonEndYear] as [number, number],
      metric: metric,
      aggregation: aggregation,
      epsilon: 1.0,
      allow_overlap: allowOverlap,
    };

    try {
      const data = await executeChangeMapAnalysis(payload);
      setResult(data);
      session.setPage4ResultId(data.run_id);
      setLoadedInputs({
        variableId: selectedVariable.variableId,
        regionLabel: region.label,
        bStart: baselineStartYear,
        bEnd: baselineEndYear,
        cStart: comparisonStartYear,
        cEnd: comparisonEndYear,
        metric: metric,
        aggregation: aggregation,
      });
    } catch (err: any) {
      console.error('Change detection analysis error:', err);
      const reqId = err.requestId || `err_${Date.now().toString(36)}`;
      setError(`${err.message || 'Change detection analysis request failed'} (Request/Job ID: ${reqId})`);
    } finally {
      setLoading(false);
    }
  }, [
    selectedVariable,
    region,
    baselineStartYear,
    baselineEndYear,
    comparisonStartYear,
    comparisonEndYear,
    metric,
    aggregation,
    allowOverlap,
    isOverlapping,
    session,
  ]);

  // Initial load
  useEffect(() => {
    if (hasConfiguredInputs) {
      runAnalysis();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasConfiguredInputs]);

  const isStale = useMemo(() => {
    if (!loadedInputs) return false;
    return (
      loadedInputs.variableId !== selectedVariable?.variableId ||
      loadedInputs.regionLabel !== region?.label ||
      loadedInputs.bStart !== baselineStartYear ||
      loadedInputs.bEnd !== baselineEndYear ||
      loadedInputs.cStart !== comparisonStartYear ||
      loadedInputs.cEnd !== comparisonEndYear ||
      loadedInputs.metric !== metric ||
      loadedInputs.aggregation !== aggregation
    );
  }, [
    loadedInputs,
    selectedVariable,
    region,
    baselineStartYear,
    baselineEndYear,
    comparisonStartYear,
    comparisonEndYear,
    metric,
    aggregation,
  ]);

  if (!hasConfiguredInputs || !selectedVariable || !region) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
        <div className="bg-slate-900/60 border-b border-slate-800">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <StepIndicator currentStep={4} />
              <h1 className="text-lg font-bold text-slate-100">Page 4: Change Detection</h1>
            </div>
          </div>
        </div>

        <main className="flex-1 max-w-3xl w-full mx-auto px-4 sm:px-6 py-16 text-center">
          <div className="p-8 rounded-2xl bg-slate-900 border border-slate-800 shadow-xl space-y-4">
            <div className="w-12 h-12 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 flex items-center justify-center mx-auto">
              <Sparkles className="w-6 h-6" />
            </div>
            <h2 className="text-lg font-bold text-white">No Dataset or Study Region Configured</h2>
            <p className="text-sm text-slate-400 max-w-md mx-auto leading-relaxed">
              Per Scientific Non-Negotiable Rule 1, Earth Science Explorer never computes or displays placeholder numbers. Please select an Earth-science variable and define your study region to begin change detection.
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
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Top Workflow Stepper */}
      <div className="bg-slate-900/60 border-b border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <StepIndicator currentStep={4} />
            <div>
              <h1 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                <span>Page 4: Change Detection</span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-cyan-950 text-cyan-400 border border-cyan-800/60">
                  Spatial Difference
                </span>
              </h1>
              <p className="text-xs text-slate-400">
                Where did environmental conditions shift between historical periods?
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 text-xs">
            <Link
              to="/trends"
              className="px-3 py-1.5 rounded-lg border border-slate-700 text-slate-300 hover:text-white hover:bg-slate-800 transition flex items-center gap-1.5"
            >
              <span>&larr; 3. Trend Analysis</span>
            </Link>
            <Link
              to="/significance"
              className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium shadow-md shadow-blue-900/20 transition flex items-center gap-1.5"
            >
              <span>5. Validate & Report &rarr;</span>
            </Link>
          </div>
        </div>
      </div>

      {/* Main 23% / 52% / 25% Grid Layout */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* ========================================================= */}
          {/* LEFT PANEL: Change Settings (Approx. 23% / 3 cols)       */}
          {/* ========================================================= */}
          <aside className="lg:col-span-3 space-y-5 bg-slate-900/80 border border-slate-800/90 rounded-2xl p-5 shadow-xl backdrop-blur-sm">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h2 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                <Sliders className="w-4 h-4 text-cyan-400" />
                <span>Change Settings</span>
              </h2>
              {isStale && (
                <span className="text-[10px] font-medium px-2 py-0.5 rounded bg-amber-950/80 text-amber-300 border border-amber-800/50">
                  Stale Settings
                </span>
              )}
            </div>

            {/* Variable (Inherited) */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-300 flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-blue-400" />
                <span>Variable</span>
              </label>
              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-xl text-xs space-y-1">
                <div className="font-semibold text-slate-200 capitalize">
                  {selectedVariable.variableId}
                </div>
                <div className="text-[11px] text-slate-400">
                  {selectedVariable.datasetId} ({selectedVariable.datasetVersion})
                </div>
                <div className="text-[11px] text-cyan-400 font-mono">
                  Units: {result?.units || selectedVariable.units}
                </div>
              </div>
            </div>

            {/* Region (Read-only with revision link to Page 2) */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-xs font-medium text-slate-300 flex items-center gap-1.5">
                  <Compass className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Study Region</span>
                </label>
                <Link
                  to="/region"
                  className="text-[11px] text-blue-400 hover:text-blue-300 transition"
                  title="Modify in Geographic Explorer"
                >
                  Edit &rarr;
                </Link>
              </div>
              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-xl text-xs space-y-1">
                <div className="font-semibold text-slate-200 truncate" title={region.label}>
                  {region.label}
                </div>
                <div className="text-[11px] text-slate-400 flex items-center justify-between">
                  <span className="capitalize">Type: {region.type}</span>
                  <span className="font-mono text-slate-300">
                    {region.areaKm2 ? `${Math.round(region.areaKm2).toLocaleString()} km²` : 'BBox'}
                  </span>
                </div>
              </div>
            </div>

            {/* Baseline Period Configuration */}
            <div className="space-y-2 pt-2 border-t border-slate-800/80">
              <div className="flex items-center justify-between text-xs">
                <label className="font-medium text-slate-300 flex items-center gap-1.5">
                  <Calendar className="w-3.5 h-3.5 text-slate-400" />
                  <span>Baseline Period (A)</span>
                </label>
                <span className="text-[11px] font-mono text-cyan-400">
                  {baselineStartYear} – {baselineEndYear}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-[10px] text-slate-400">Start Year</span>
                  <input
                    type="number"
                    min={minCoverageYear}
                    max={baselineEndYear}
                    value={baselineStartYear}
                    onChange={(e) => setBaselineStartYear(parseInt(e.target.value) || minCoverageYear)}
                    className="w-full mt-1 bg-slate-950 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-slate-100 font-mono focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div>
                  <span className="text-[10px] text-slate-400">End Year</span>
                  <input
                    type="number"
                    min={baselineStartYear}
                    max={maxCoverageYear}
                    value={baselineEndYear}
                    onChange={(e) => setBaselineEndYear(parseInt(e.target.value) || maxCoverageYear)}
                    className="w-full mt-1 bg-slate-950 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-slate-100 font-mono focus:outline-none focus:border-blue-500"
                  />
                </div>
              </div>
            </div>

            {/* Comparison Period Configuration */}
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <label className="font-medium text-slate-300 flex items-center gap-1.5">
                  <Calendar className="w-3.5 h-3.5 text-slate-400" />
                  <span>Comparison Period (B)</span>
                </label>
                <span className="text-[11px] font-mono text-blue-400">
                  {comparisonStartYear} – {comparisonEndYear}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-[10px] text-slate-400">Start Year</span>
                  <input
                    type="number"
                    min={minCoverageYear}
                    max={comparisonEndYear}
                    value={comparisonStartYear}
                    onChange={(e) => setComparisonStartYear(parseInt(e.target.value) || minCoverageYear)}
                    className="w-full mt-1 bg-slate-950 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-slate-100 font-mono focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div>
                  <span className="text-[10px] text-slate-400">End Year</span>
                  <input
                    type="number"
                    min={comparisonStartYear}
                    max={maxCoverageYear}
                    value={comparisonEndYear}
                    onChange={(e) => setComparisonEndYear(parseInt(e.target.value) || maxCoverageYear)}
                    className="w-full mt-1 bg-slate-950 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-slate-100 font-mono focus:outline-none focus:border-blue-500"
                  />
                </div>
              </div>
              <div className="text-[10px] text-slate-500 italic">
                Product coverage: {minCoverageYear} to {maxCoverageYear} (latest complete year).
              </div>
            </div>

            {/* Period Overlap Alert & Confirmation */}
            {isOverlapping && (
              <div className="p-3 bg-amber-950/40 border border-amber-800/80 rounded-xl text-xs space-y-2 text-amber-200">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold text-amber-300">Overlapping Periods</span>
                    <p className="text-[11px] text-amber-200/80 mt-0.5">
                      Baseline [{baselineStartYear}–{baselineEndYear}] and Comparison [{comparisonStartYear}–{comparisonEndYear}] overlap.
                    </p>
                  </div>
                </div>
                <label className="flex items-center gap-2 pt-1 border-t border-amber-900/40 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={allowOverlap}
                    onChange={(e) => setAllowOverlap(e.target.checked)}
                    className="rounded border-amber-700 bg-amber-950 text-amber-500 focus:ring-0"
                  />
                  <span className="text-[11px] font-medium text-amber-100">
                    Explicitly confirm overlap
                  </span>
                </label>
              </div>
            )}

            {/* Metric Selection */}
            <div className="space-y-1.5 pt-2 border-t border-slate-800/80">
              <label className="text-xs font-medium text-slate-300">Change Metric</label>
              <div className="grid grid-cols-1 gap-1.5 text-xs">
                <button
                  type="button"
                  onClick={() => setMetric('absolute')}
                  className={`p-2.5 rounded-xl text-left border transition ${
                    metric === 'absolute'
                      ? 'bg-blue-950/60 border-blue-500 text-white shadow-md'
                      : 'bg-slate-950 border-slate-800 text-slate-300 hover:bg-slate-800/60'
                  }`}
                >
                  <div className="font-semibold">Absolute Change (B − A)</div>
                  <div className="text-[10px] text-slate-400 mt-0.5">
                    Difference in native units (mm/year). Recommended default.
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => setMetric('percentage')}
                  className={`p-2.5 rounded-xl text-left border transition ${
                    metric === 'percentage'
                      ? 'bg-blue-950/60 border-blue-500 text-white shadow-md'
                      : 'bg-slate-950 border-slate-800 text-slate-300 hover:bg-slate-800/60'
                  }`}
                >
                  <div className="font-semibold">Percentage Change (%)</div>
                  <div className="text-[10px] text-slate-400 mt-0.5">
                    100 × (B − A) / |A|. Suppressed for near-zero baselines.
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => setMetric('spatial_trend')}
                  className={`p-2.5 rounded-xl text-left border transition ${
                    metric === 'spatial_trend'
                      ? 'bg-blue-950/60 border-blue-500 text-white shadow-md'
                      : 'bg-slate-950 border-slate-800 text-slate-300 hover:bg-slate-800/60'
                  }`}
                >
                  <div className="font-semibold">Spatial Trend (Slope/Year)</div>
                  <div className="text-[10px] text-slate-400 mt-0.5">
                    Per-cell linear regression slope per year across the span.
                  </div>
                </button>
              </div>

              {/* Percentage warning (SPEC 14.5 & SPEC 9.7) */}
              {metric === 'percentage' && (
                <div className="p-2.5 bg-cyan-950/40 border border-cyan-800/60 rounded-xl text-[11px] text-cyan-200 flex items-start gap-2">
                  <Info className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
                  <span>
                    Cells with baseline |A| &le; 1.0 mm/year are suppressed to No-Data to prevent undefined or deceptive relative spikes.
                  </span>
                </div>
              )}
            </div>

            {/* Aggregation Selection */}
            <div className="space-y-1.5 pt-2 border-t border-slate-800/80">
              <label className="text-xs font-medium text-slate-300">Aggregation</label>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <button
                  type="button"
                  onClick={() => setAggregation('annual')}
                  className={`py-2 rounded-lg border text-center font-medium transition ${
                    aggregation === 'annual'
                      ? 'bg-blue-600 text-white border-blue-500 shadow'
                      : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Annual Accumulation
                </button>
                <button
                  type="button"
                  onClick={() => setAggregation('monthly')}
                  className={`py-2 rounded-lg border text-center font-medium transition ${
                    aggregation === 'monthly'
                      ? 'bg-blue-600 text-white border-blue-500 shadow'
                      : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Monthly Rate
                </button>
              </div>
            </div>

            {/* Error Display */}
            {error && (
              <div className="p-3 bg-red-950/60 border border-red-800 rounded-xl text-xs text-red-200 flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                <div className="flex-1">{error}</div>
              </div>
            )}

            {/* Action Button */}
            <button
              onClick={runAnalysis}
              disabled={loading || (isOverlapping && !allowOverlap)}
              className="w-full py-2.5 px-4 bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 disabled:opacity-50 text-white text-xs font-semibold rounded-xl shadow-lg shadow-blue-900/30 transition flex items-center justify-center gap-2"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              <span>{loading ? 'Computing Change Map...' : 'Calculate Change Map'}</span>
            </button>
          </aside>

          {/* ========================================================= */}
          {/* CENTRE PANEL: Change Difference Map (Approx. 52% / 6 cols) */}
          {/* ========================================================= */}
          <section className="lg:col-span-6 space-y-4">
            <div className="bg-slate-900/80 border border-slate-800/90 rounded-2xl p-4 shadow-xl backdrop-blur-sm">
              <div className="flex flex-wrap items-center justify-between gap-2 pb-3 mb-3 border-b border-slate-800">
                <div className="flex items-center gap-2">
                  <MapPin className="w-4 h-4 text-cyan-400" />
                  <h2 className="text-sm font-semibold text-slate-200">
                    Difference Map Overlay
                  </h2>
                  {result && (
                    <StatusChip status="Available" />
                  )}
                </div>

                <div className="text-xs text-slate-400 flex items-center gap-2">
                  <span>Click cell to inspect</span>
                  <span className="text-slate-600">•</span>
                  <span className="font-mono text-cyan-400">
                    {result ? `${result.units}` : ''}
                  </span>
                </div>
              </div>

              {/* Map Viewer Component */}
              <div className="h-[520px] w-full">
                <ChangeMapViewer
                  runId={result?.run_id}
                  overlayUrl={result?.overlay_url}
                  geotiffUrl={result?.geotiff_url}
                  bounds={result?.bounds}
                  legend={result?.legend}
                  geometry={region.geometry}
                  units={result?.units}
                  metric={result?.metric}
                />
              </div>

              {/* Warnings banner */}
              {result && result.warnings && result.warnings.length > 0 && (
                <div className="mt-3 p-3 bg-amber-950/30 border border-amber-900/50 rounded-xl text-xs text-amber-300 space-y-1">
                  {result.warnings.map((w, idx) => (
                    <div key={idx} className="flex items-start gap-1.5">
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
                      <span>{w}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>

          {/* ========================================================= */}
          {/* RIGHT PANEL: Spatial Summary (Approx. 25% / 3 cols)       */}
          {/* ========================================================= */}
          <aside className="lg:col-span-3 space-y-5">
            {/* Spatial Summary Card */}
            <div className="bg-slate-900/80 border border-slate-800/90 rounded-2xl p-5 shadow-xl backdrop-blur-sm space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                <h2 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-emerald-400" />
                  <span>Spatial Summary</span>
                </h2>
                <span className="text-[10px] font-mono text-slate-400">SPEC 9.6</span>
              </div>

              {/* Overall Area-Weighted Change */}
              <div className="p-3.5 bg-slate-950/70 border border-slate-800 rounded-xl space-y-1">
                <div className="text-xs text-slate-400 font-medium">Overall Area-Weighted Change</div>
                <div className="text-2xl font-bold font-mono text-slate-100 flex items-baseline gap-1.5">
                  {result?.spatial_summary.area_weighted_mean_change !== null &&
                  result?.spatial_summary.area_weighted_mean_change !== undefined ? (
                    <>
                      <span
                        className={
                          result.spatial_summary.area_weighted_mean_change > 0
                            ? 'text-red-400'
                            : result.spatial_summary.area_weighted_mean_change < 0
                            ? 'text-blue-400'
                            : 'text-slate-300'
                        }
                      >
                        {result.spatial_summary.area_weighted_mean_change > 0 ? '+' : ''}
                        {result.spatial_summary.area_weighted_mean_change}
                      </span>
                      <span className="text-xs font-normal text-slate-400">
                        {result.units}
                      </span>
                    </>
                  ) : (
                    <span className="text-slate-500 text-lg">No Valid Cells</span>
                  )}
                </div>
                <div className="text-[10px] text-slate-500">
                  Calculated over valid region cells with latitude cosine area weights.
                </div>
              </div>

              {/* Area Shares: Increasing vs Decreasing */}
              <div className="space-y-2">
                <div className="text-xs font-medium text-slate-300">Valid Area Shares</div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="p-2.5 bg-red-950/20 border border-red-900/40 rounded-xl">
                    <div className="flex items-center gap-1 text-[11px] text-red-400 font-medium">
                      <TrendingUp className="w-3 h-3" />
                      <span>Increasing</span>
                    </div>
                    <div className="text-lg font-bold font-mono text-red-300 mt-1">
                      {result ? `${result.spatial_summary.share_increasing_pct}%` : '—'}
                    </div>
                  </div>

                  <div className="p-2.5 bg-blue-950/20 border border-blue-900/40 rounded-xl">
                    <div className="flex items-center gap-1 text-[11px] text-blue-400 font-medium">
                      <TrendingDown className="w-3 h-3" />
                      <span>Decreasing</span>
                    </div>
                    <div className="text-lg font-bold font-mono text-blue-300 mt-1">
                      {result ? `${result.spatial_summary.share_decreasing_pct}%` : '—'}
                    </div>
                  </div>
                </div>

                <div className="p-2 bg-slate-950/60 border border-slate-800 rounded-lg flex justify-between text-xs text-slate-400">
                  <span>Stable / No Change:</span>
                  <span className="font-mono text-slate-200">
                    {result ? `${result.spatial_summary.share_no_change_pct}%` : '—'}
                  </span>
                </div>
              </div>

              {/* Highest and Lowest Change Extremes */}
              <div className="space-y-2 pt-2 border-t border-slate-800">
                <div className="text-xs font-medium text-slate-300">Extremes in Region</div>

                <div className="p-2.5 bg-slate-950/70 border border-slate-800 rounded-xl text-xs space-y-1">
                  <div className="flex items-center justify-between text-slate-400 text-[11px]">
                    <span className="flex items-center gap-1 text-red-400 font-medium">
                      Highest Change
                    </span>
                    <span className="font-mono text-slate-500">
                      {result?.spatial_summary.highest_change
                        ? `${result.spatial_summary.highest_change.lat}°, ${result.spatial_summary.highest_change.lon}°`
                        : '—'}
                    </span>
                  </div>
                  <div className="font-mono text-sm font-semibold text-red-300">
                    {result?.spatial_summary.highest_change
                      ? `+${result.spatial_summary.highest_change.value} ${result.units}`
                      : '—'}
                  </div>
                </div>

                <div className="p-2.5 bg-slate-950/70 border border-slate-800 rounded-xl text-xs space-y-1">
                  <div className="flex items-center justify-between text-slate-400 text-[11px]">
                    <span className="flex items-center gap-1 text-blue-400 font-medium">
                      Lowest Change
                    </span>
                    <span className="font-mono text-slate-500">
                      {result?.spatial_summary.lowest_change
                        ? `${result.spatial_summary.lowest_change.lat}°, ${result.spatial_summary.lowest_change.lon}°`
                        : '—'}
                    </span>
                  </div>
                  <div className="font-mono text-sm font-semibold text-blue-300">
                    {result?.spatial_summary.lowest_change
                      ? `${result.spatial_summary.lowest_change.value} ${result.units}`
                      : '—'}
                  </div>
                </div>
              </div>

              {/* No-data Area (Reported SEPARATELY from No-change) */}
              <div className="p-3 bg-slate-950/90 border border-slate-800 rounded-xl text-xs space-y-1.5">
                <div className="flex items-center justify-between text-slate-300 font-medium">
                  <span>No-Data / Unsampled Area:</span>
                  <span className="font-mono text-amber-400">
                    {result ? `${result.spatial_summary.nodata_share_pct}%` : '—'}
                  </span>
                </div>
                <div className="flex justify-between text-[11px] text-slate-400">
                  <span>Missing Area:</span>
                  <span className="font-mono">
                    {result
                      ? `${Math.round(result.spatial_summary.nodata_area_km2).toLocaleString()} km²`
                      : '—'}
                  </span>
                </div>
                <div className="flex justify-between text-[11px] text-slate-400">
                  <span>Valid Analyzed Area:</span>
                  <span className="font-mono text-emerald-400">
                    {result
                      ? `${Math.round(result.spatial_summary.valid_area_km2).toLocaleString()} km²`
                      : '—'}
                  </span>
                </div>
              </div>

              {/* Scientific Non-negotiable Alert (SPEC 9.8) */}
              <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl text-[11px] text-slate-400 space-y-1">
                <div className="font-semibold text-slate-300 flex items-center gap-1.5">
                  <Info className="w-3.5 h-3.5 text-blue-400" />
                  <span>Scientific Rule (SPEC 9.8)</span>
                </div>
                <p className="text-slate-400 leading-relaxed">
                  This page displays estimated spatial differences. A large observed difference does
                  not establish statistical certainty. Hypothesis testing and multiple-testing corrections
                  (FDR) are performed on Page 5.
                </p>
              </div>

              {/* Next CTA to Page 5 */}
              <Link
                to="/significance"
                className="w-full py-2.5 px-4 bg-slate-800 hover:bg-slate-700 text-slate-200 hover:text-white border border-slate-700 rounded-xl text-xs font-semibold shadow transition flex items-center justify-center gap-2"
              >
                <span>Continue to Significance & Reports</span>
                <ArrowRight className="w-3.5 h-3.5 text-cyan-400" />
              </Link>
            </div>

            {/* Provenance Card */}
            {result?.provenance && (
              <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-4 text-xs space-y-2">
                <div className="font-semibold text-slate-300 flex items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5 text-slate-400" />
                  <span>Analysis Provenance</span>
                </div>
                <div className="space-y-1 text-[11px] text-slate-400">
                  <div className="flex justify-between">
                    <span>Formula:</span>
                    <span className="font-mono text-slate-300">{result.provenance.formula}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Mask Method:</span>
                    <span className="capitalize">{result.provenance.mask_method}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Weighting:</span>
                    <span className="capitalize">{result.provenance.area_weighting}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Run ID:</span>
                    <span className="font-mono text-cyan-400 truncate max-w-[140px]">
                      {result.run_id}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </aside>
        </div>
      </main>
    </div>
  );
};
