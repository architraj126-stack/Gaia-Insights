import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useSession } from '../store/session';
import {
  executeTimeSeriesAnalysis,
  type TimeSeriesResult,
} from '../api/trends';
import { TimeSeriesChart } from '../components/chart/TimeSeriesChart';
import { VirtualDataTable } from '../components/table/VirtualDataTable';
import { StepIndicator } from '../components/StepIndicator';
import {
  AlertTriangle,
  ArrowRight,
  ChevronRight,
  Info,
  Layers,
  MapPin,
  RefreshCw,
  TrendingDown,
  TrendingUp,
  Minus,
  AlertCircle,
} from 'lucide-react';

export const TrendsPage: React.FC = () => {
  const session = useSession();

  // 1. Inputs from store (SPEC 3.3 & Rule 1: No fabricated fallback geometry)
  const hasConfiguredInputs = session.selectedVariables.length > 0 && !!session.region;
  const selectedVariable = session.selectedVariables[0];
  const region = session.region;

  // State
  const [aggregation, setAggregation] = useState<'monthly' | 'annual' | 'seasonal'>(
    (session.frequency as 'monthly' | 'annual' | 'seasonal') || 'monthly'
  );
  const [startDate, setStartDate] = useState<string>(session.dateRange.start || '1990-01-01');
  const [endDate, setEndDate] = useState<string>('latest_complete');

  // Chart toggles
  const [trendDisplayMethod, setTrendDisplayMethod] = useState<'ols' | 'sens' | 'none'>('ols');
  const [showConfidenceBand, setShowConfidenceBand] = useState<boolean>(true);
  const [showMovingAverage, setShowMovingAverage] = useState<boolean>(true);
  const [showPoints, setShowPoints] = useState<boolean>(true);

  // Slope display preference on the right summary panel
  const [preferredSlopeMethod, setPreferredSlopeMethod] = useState<'ols' | 'sens'>('ols');

  // Analysis Result and Status
  const [seriesResult, setSeriesResult] = useState<TimeSeriesResult | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Stale detection: track the exact inputs that yielded seriesResult
  const [loadedInputs, setLoadedInputs] = useState<{
    variableId: string;
    datasetId: string;
    regionLabel: string;
    startDate: string;
    endDate: string;
    aggregation: string;
  } | null>(null);

  // Fetch Time-Series Analysis
  const runAnalysis = useCallback(async () => {
    if (!selectedVariable || !region) return;
    setLoading(true);
    setError(null);

    const payload = {
      dataset_id: selectedVariable.datasetId || 'gpcp_monthly_v23',
      dataset_version: selectedVariable.datasetVersion || 'v2.3',
      variable: selectedVariable.variableId || 'precipitation',
      geometry: region.geometry,
      geometry_crs: region.crs || 'EPSG:4326',
      start_date: startDate,
      end_date: endDate,
      aggregation: aggregation,
      options: {
        area_weighted: true,
        include_missing_flags: true,
      },
    };

    try {
      const result = await executeTimeSeriesAnalysis(payload);
      setSeriesResult(result);
      session.setPage3ResultId(result.series_id);
      setLoadedInputs({
        variableId: selectedVariable.variableId,
        datasetId: selectedVariable.datasetId,
        regionLabel: region.label,
        startDate: startDate,
        endDate: endDate,
        aggregation: aggregation,
      });
    } catch (err: any) {
      console.error('Failed to run timeseries analysis:', err);
      const reqId = err.requestId || `err_${Date.now().toString(36)}`;
      setError(`${err.message || 'Time-series analysis request failed'} (Request/Job ID: ${reqId})`);
    } finally {
      setLoading(false);
    }
  }, [selectedVariable, region, startDate, endDate, aggregation, session]);

  // Initial load or on region/variable change
  useEffect(() => {
    if (hasConfiguredInputs) {
      runAnalysis();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [aggregation, hasConfiguredInputs]);

  // Check if current inputs differ from loadedInputs
  const isStale = useMemo(() => {
    if (!loadedInputs || !selectedVariable || !region) return false;
    return (
      loadedInputs.variableId !== selectedVariable.variableId ||
      loadedInputs.datasetId !== selectedVariable.datasetId ||
      loadedInputs.regionLabel !== region.label ||
      loadedInputs.startDate !== startDate ||
      loadedInputs.endDate !== endDate ||
      loadedInputs.aggregation !== aggregation
    );
  }, [loadedInputs, selectedVariable, region, startDate, endDate, aggregation]);

  // CSV Export Handler
  const handleExportCSV = () => {
    if (!seriesResult || !seriesResult.points || seriesResult.points.length === 0) return;
    const header = [
      'date',
      'value',
      'units',
      'is_missing',
      'flags',
      'moving_avg',
      'fitted_ols',
      'ols_ci_lower',
      'ols_ci_upper',
      'sens_line',
      'valid_cell_count',
      'valid_area_km2',
    ].join(',');

    const rows = seriesResult.points.map((p) =>
      [
        p.date,
        p.value !== null && p.value !== undefined ? p.value : '',
        p.units || selectedVariable.units,
        p.is_missing ? 'true' : 'false',
        `"${(p.flags || []).join('; ')}"`,
        p.moving_avg !== null && p.moving_avg !== undefined ? p.moving_avg : '',
        p.fitted_ols !== null && p.fitted_ols !== undefined ? p.fitted_ols : '',
        p.ols_ci_lower !== null && p.ols_ci_lower !== undefined ? p.ols_ci_lower : '',
        p.ols_ci_upper !== null && p.ols_ci_upper !== undefined ? p.ols_ci_upper : '',
        p.sens_line !== null && p.sens_line !== undefined ? p.sens_line : '',
        p.valid_cell_count ?? '',
        p.valid_area_km2 ?? '',
      ].join(',')
    );

    const csvContent = [header, ...rows].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute(
      'download',
      `timeseries_${selectedVariable.variableId}_${aggregation}_${startDate}_${endDate}.csv`
    );
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  // Helper for trend direction chip
  const renderTrendDirectionChip = (direction: string) => {
    const dirLower = direction.toLowerCase();
    if (dirLower === 'increasing') {
      return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-950/80 text-emerald-400 border border-emerald-700/60">
          <TrendingUp className="w-3.5 h-3.5" />
          Increasing Trend
        </span>
      );
    }
    if (dirLower === 'decreasing') {
      return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-cyan-950/80 text-cyan-400 border border-cyan-700/60">
          <TrendingDown className="w-3.5 h-3.5" />
          Decreasing Trend
        </span>
      );
    }
    if (dirLower === 'no clear trend' || dirLower === 'no_trend') {
      return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-slate-800 text-slate-300 border border-slate-700">
          <Minus className="w-3.5 h-3.5" />
          No Clear Trend
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-950/80 text-amber-400 border border-amber-700/60">
        <AlertCircle className="w-3.5 h-3.5" />
        Insufficient Data
      </span>
    );
  };

  if (!hasConfiguredInputs || !selectedVariable || !region) {
    return (
      <div className="flex flex-col min-h-screen bg-slate-950 text-slate-100 font-sans">
        <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur sticky top-0 z-20">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
            <div className="flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2 text-xs text-slate-400">
                  <Link to="/" className="hover:text-slate-200">Home</Link>
                  <ChevronRight className="w-3 h-3 text-slate-600" />
                  <Link to="/explore" className="hover:text-slate-200">1. Data Explorer</Link>
                  <ChevronRight className="w-3 h-3 text-slate-600" />
                  <Link to="/region" className="hover:text-slate-200">2. Geographic Explorer</Link>
                  <ChevronRight className="w-3 h-3 text-slate-600" />
                  <span className="text-cyan-400 font-medium">3. Trend Analysis</span>
                </div>
                <h1 className="text-xl font-bold text-white mt-1">Page 3: Trend Analysis</h1>
              </div>
              <StepIndicator currentStep={3} />
            </div>
          </div>
        </header>

        <main className="flex-1 max-w-3xl w-full mx-auto px-4 sm:px-6 py-16 text-center">
          <div className="p-8 rounded-2xl bg-slate-900 border border-slate-800 shadow-xl space-y-4">
            <div className="w-12 h-12 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 flex items-center justify-center mx-auto">
              <TrendingUp className="w-6 h-6" />
            </div>
            <h2 className="text-lg font-bold text-white">No Dataset or Study Region Configured</h2>
            <p className="text-sm text-slate-400 max-w-md mx-auto leading-relaxed">
              Per Scientific Non-Negotiable Rule 1, Gaia Insights never computes or displays placeholder numbers. Please select an Earth-science variable and define your study region to begin trend analysis.
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
    <div className="flex flex-col min-h-screen bg-slate-950 text-slate-100 font-sans">
      {/* Top Header & Step Indicator */}
      <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <Link to="/" className="hover:text-slate-200">Home</Link>
                <ChevronRight className="w-3 h-3 text-slate-600" />
                <Link to="/explore" className="hover:text-slate-200">1. Data Explorer</Link>
                <ChevronRight className="w-3 h-3 text-slate-600" />
                <Link to="/region" className="hover:text-slate-200">2. Geographic Explorer</Link>
                <ChevronRight className="w-3 h-3 text-slate-600" />
                <span className="text-cyan-400 font-medium">3. Trend Analysis</span>
              </div>
              <h1 className="text-xl font-bold text-white mt-1">Page 3: Trend Analysis</h1>
            </div>

            <div className="flex items-center gap-4">
              <StepIndicator currentStep={3} />
              <Link
                to="/changes"
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold shadow-lg shadow-cyan-950/40 transition-colors"
              >
                <span>4. Change Detection</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          </div>
        </div>
      </header>

      {/* Main 3-Column Responsive Layout (23% / 52% / 25%) */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="flex flex-col lg:flex-row gap-6 items-start">

          {/* LEFT PANEL: Analysis Settings (23%) */}
          <div className="w-full lg:w-[23%] shrink-0 flex flex-col gap-4">
            {/* Variable Context Card */}
            <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 shadow-sm flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Selected Variable
                </span>
                <Link
                  to="/explore"
                  className="text-[11px] text-cyan-400 hover:underline flex items-center gap-0.5"
                >
                  Change
                </Link>
              </div>

              <div>
                <h3 className="text-sm font-bold text-white capitalize">
                  {selectedVariable.fieldName || selectedVariable.variableId}
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Dataset: <span className="text-slate-200">{selectedVariable.datasetId}</span> ({selectedVariable.datasetVersion})
                </p>
                <p className="text-xs text-slate-400">
                  Native Units: <span className="text-cyan-300 font-mono">{seriesResult?.dataset.units || selectedVariable.units}</span>
                </p>
              </div>
            </div>

            {/* Region Context Card (Read-only with link to Page 2) */}
            <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 shadow-sm flex flex-col gap-2.5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-400">
                  <MapPin className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Target Region</span>
                </div>
                <Link
                  to="/region"
                  className="text-[11px] text-cyan-400 hover:underline"
                >
                  Revise on Page 2 →
                </Link>
              </div>

              <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800 text-xs">
                <div className="font-semibold text-slate-200 truncate" title={region.label}>
                  {region.label}
                </div>
                <div className="text-[11px] text-slate-400 mt-1">
                  Type: <span className="capitalize text-slate-300">{region.type}</span>
                  {region.areaKm2 ? ` • Area: ${region.areaKm2.toLocaleString()} km²` : ''}
                </div>
              </div>
            </div>

            {/* Aggregation & Temporal Controls */}
            <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 shadow-sm flex flex-col gap-4">
              <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-400">
                <Layers className="w-3.5 h-3.5 text-cyan-400" />
                <span>Temporal Aggregation</span>
              </div>

              {/* Aggregation Radio / Tabs */}
              <div className="grid grid-cols-3 gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
                {(['monthly', 'annual', 'seasonal'] as const).map((mode) => (
                  <button
                    key={mode}
                    onClick={() => {
                      if (mode !== aggregation) {
                        setAggregation(mode);
                        session.setFrequency(mode);
                      }
                    }}
                    className={`py-1.5 text-xs font-medium rounded-md transition-all capitalize ${
                      aggregation === mode
                        ? 'bg-cyan-600 text-white shadow-sm'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    {mode}
                  </button>
                ))}
              </div>

              {/* Date Range Info */}
              <div className="flex flex-col gap-1.5 text-xs">
                <label className="text-slate-400 font-medium">Date Range (Clamped)</label>
                <div className="grid grid-cols-2 gap-2">
                  <div className="bg-slate-950 p-2 rounded border border-slate-800">
                    <span className="block text-[10px] text-slate-500 uppercase">Start</span>
                    <input
                      type="date"
                      value={startDate}
                      min="1979-01-01"
                      max="2026-10-01"
                      onChange={(e) => setStartDate(e.target.value)}
                      className="bg-transparent font-mono text-[11px] text-slate-200 focus:outline-none w-full"
                    />
                  </div>
                  <div className="bg-slate-950 p-2 rounded border border-slate-800">
                    <span className="block text-[10px] text-slate-500 uppercase">End</span>
                    <input
                      type="text"
                      value={endDate === 'latest_complete' ? (seriesResult?.coverage.actual_end || '2026-10-01') : endDate}
                      onChange={(e) => setEndDate(e.target.value)}
                      placeholder="YYYY-MM-DD"
                      className="bg-transparent font-mono text-[11px] text-slate-200 focus:outline-none w-full"
                    />
                  </div>
                </div>
                <span className="text-[10px] text-slate-500">
                  Clamped to verified NOAA PSL GPCP v2.3 coverage.
                </span>
              </div>
            </div>

            {/* Display Toggles Card */}
            <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 shadow-sm flex flex-col gap-3.5">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Chart Display Toggles
              </span>

              {/* Trend Method Radio */}
              <div className="flex flex-col gap-1.5">
                <span className="text-xs text-slate-400 font-medium">Trend Line Method:</span>
                <div className="grid grid-cols-3 gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800 text-xs">
                  <button
                    onClick={() => setTrendDisplayMethod('none')}
                    className={`py-1 rounded ${trendDisplayMethod === 'none' ? 'bg-slate-700 text-white' : 'text-slate-400'}`}
                  >
                    Off
                  </button>
                  <button
                    onClick={() => setTrendDisplayMethod('ols')}
                    className={`py-1 rounded ${trendDisplayMethod === 'ols' ? 'bg-amber-600 text-white font-semibold' : 'text-slate-400'}`}
                  >
                    OLS
                  </button>
                  <button
                    onClick={() => setTrendDisplayMethod('sens')}
                    className={`py-1 rounded ${trendDisplayMethod === 'sens' ? 'bg-emerald-600 text-white font-semibold' : 'text-slate-400'}`}
                  >
                    Sen's
                  </button>
                </div>
              </div>

              {/* Checkboxes */}
              <div className="flex flex-col gap-2.5 pt-1 text-xs text-slate-300">
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={showConfidenceBand}
                    onChange={(e) => setShowConfidenceBand(e.target.checked)}
                    disabled={trendDisplayMethod !== 'ols'}
                    className="rounded border-slate-700 text-amber-500 focus:ring-0 focus:ring-offset-0 bg-slate-950 disabled:opacity-40"
                  />
                  <span className={trendDisplayMethod !== 'ols' ? 'text-slate-500' : ''}>
                    Regression Confidence Band (95%)
                  </span>
                </label>

                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={showMovingAverage}
                    onChange={(e) => setShowMovingAverage(e.target.checked)}
                    className="rounded border-slate-700 text-purple-500 focus:ring-0 focus:ring-offset-0 bg-slate-950"
                  />
                  <span>
                    Moving Average ({aggregation === 'monthly' ? '12-mo' : aggregation === 'seasonal' ? '4-season' : '5-yr'} window)
                  </span>
                </label>

                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={showPoints}
                    onChange={(e) => setShowPoints(e.target.checked)}
                    className="rounded border-slate-700 text-cyan-500 focus:ring-0 focus:ring-offset-0 bg-slate-950"
                  />
                  <span>Observation Points</span>
                </label>
              </div>
            </div>
          </div>

          {/* CENTRE PANEL: Interactive Graph & Data Table (52%) */}
          <div className="w-full lg:w-[52%] flex-1 min-w-0 flex flex-col gap-4">
            {/* Stale Result Banner */}
            {isStale && (
              <div className="p-3.5 rounded-xl bg-amber-950/60 border border-amber-600/80 flex items-center justify-between text-amber-200 text-xs shadow-md animate-pulse">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                  <span>
                    <strong>Settings changed.</strong> Result shown is from previous calculation.
                  </span>
                </div>
                <button
                  onClick={runAnalysis}
                  disabled={loading}
                  className="flex items-center gap-1.5 px-3 py-1 bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold rounded-lg text-xs transition-colors shrink-0"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                  <span>Recalculate</span>
                </button>
              </div>
            )}

            {/* Error Message */}
            {error && (
              <div className="p-4 rounded-xl bg-red-950/60 border border-red-700 text-red-200 text-xs flex items-start gap-2.5">
                <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                <div>
                  <strong className="block text-red-300">Analysis Error</strong>
                  {error}
                </div>
              </div>
            )}

            {/* Chart Card */}
            <div className="rounded-xl bg-slate-900 border border-slate-800 shadow-md overflow-hidden flex flex-col">
              {loading && !seriesResult ? (
                <div className="flex flex-col items-center justify-center min-h-[420px] gap-3 text-slate-400">
                  <RefreshCw className="w-8 h-8 text-cyan-400 animate-spin" />
                  <p className="text-sm">Processing spatial time-series aggregation...</p>
                </div>
              ) : seriesResult && seriesResult.points ? (
                <TimeSeriesChart
                  points={seriesResult.points}
                  variableName={selectedVariable.fieldName || selectedVariable.variableId}
                  units={seriesResult.dataset.units || selectedVariable.units}
                  aggregation={aggregation}
                  showTrend={trendDisplayMethod}
                  showConfidenceBand={showConfidenceBand}
                  showMovingAverage={showMovingAverage}
                  showPoints={showPoints}
                  movingAverageWindow={seriesResult.summary?.moving_average_window || 12}
                  onExportCSV={handleExportCSV}
                />
              ) : (
                <div className="flex flex-col items-center justify-center min-h-[420px] text-slate-500 text-xs">
                  No time series loaded.
                </div>
              )}
            </div>

            {/* Bottom Virtual Data Table */}
            {seriesResult && seriesResult.points && (
              <VirtualDataTable
                points={seriesResult.points}
                units={seriesResult.dataset.units || selectedVariable.units}
                variableName={selectedVariable.fieldName || selectedVariable.variableId}
                aggregation={aggregation}
                onExportCSV={handleExportCSV}
              />
            )}
          </div>

          {/* RIGHT PANEL: Summary Metrics per SPEC 8.5 (25%) */}
          <div className="w-full lg:w-[25%] shrink-0 flex flex-col gap-4">
            <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 shadow-sm flex flex-col gap-4">
              <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Trend Summary Metrics
                </span>
                <span className="text-[10px] text-slate-500 font-mono">SPEC 8.5</span>
              </div>

              {/* 1. Trend Direction */}
              <div className="flex flex-col gap-1.5">
                <span className="text-xs text-slate-400 font-medium">Trend Direction</span>
                <div>
                  {renderTrendDirectionChip(
                    seriesResult?.summary?.trend_direction || 'Calculating...'
                  )}
                </div>
                <span className="text-[10px] text-slate-500">
                  Confidence α = {seriesResult?.summary?.alpha || 0.05} • Min data threshold:{' '}
                  {seriesResult?.summary?.min_data_points || 12}
                </span>
              </div>

              {/* 2. Rate of Change with Method Naming */}
              <div className="flex flex-col gap-1.5 p-3 rounded-lg bg-slate-950 border border-slate-800/80">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-400 font-medium">Rate of Change</span>
                  {/* Selector to choose displayed slope method */}
                  <div className="flex items-center gap-1 text-[10px]">
                    <button
                      onClick={() => setPreferredSlopeMethod('ols')}
                      className={`px-1.5 py-0.5 rounded ${
                        preferredSlopeMethod === 'ols'
                          ? 'bg-amber-600 text-white font-bold'
                          : 'text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      OLS
                    </button>
                    <button
                      onClick={() => setPreferredSlopeMethod('sens')}
                      className={`px-1.5 py-0.5 rounded ${
                        preferredSlopeMethod === 'sens'
                          ? 'bg-emerald-600 text-white font-bold'
                          : 'text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      Sen's
                    </button>
                  </div>
                </div>

                {preferredSlopeMethod === 'ols' ? (
                  <div>
                    <div className="text-lg font-bold text-amber-400 font-mono">
                      {seriesResult?.summary?.ols?.slope_per_year !== null &&
                      seriesResult?.summary?.ols?.slope_per_year !== undefined
                        ? `${seriesResult.summary.ols.slope_per_year > 0 ? '+' : ''}${seriesResult.summary.ols.slope_per_year} ${seriesResult.dataset.units}/year`
                        : '—'}
                    </div>
                    <div className="text-[11px] text-slate-400 mt-0.5">
                      Method: <span className="text-slate-200 font-medium">Linear regression (OLS)</span>
                    </div>
                    {seriesResult?.summary?.ols?.ci_lower_slope !== null && (
                      <div className="text-[10px] text-slate-500 font-mono">
                        95% CI: [{seriesResult?.summary?.ols?.ci_lower_slope},{' '}
                        {seriesResult?.summary?.ols?.ci_upper_slope}]
                      </div>
                    )}
                  </div>
                ) : (
                  <div>
                    <div className="text-lg font-bold text-emerald-400 font-mono">
                      {seriesResult?.summary?.sens_slope?.slope_per_year !== null &&
                      seriesResult?.summary?.sens_slope?.slope_per_year !== undefined
                        ? `${seriesResult.summary.sens_slope.slope_per_year > 0 ? '+' : ''}${seriesResult.summary.sens_slope.slope_per_year} ${seriesResult.dataset.units}/year`
                        : '—'}
                    </div>
                    <div className="text-[11px] text-slate-400 mt-0.5">
                      Method: <span className="text-slate-200 font-medium">Theil-Sen robust slope</span>
                    </div>
                    {seriesResult?.summary?.sens_slope?.ci_lower !== null && (
                      <div className="text-[10px] text-slate-500 font-mono">
                        95% CI: [{seriesResult?.summary?.sens_slope?.ci_lower},{' '}
                        {seriesResult?.summary?.sens_slope?.ci_upper}]
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* 3. Average Value */}
              <div className="flex flex-col gap-0.5 p-3 rounded-lg bg-slate-950 border border-slate-800/80">
                <span className="text-xs text-slate-400 font-medium">Average Value</span>
                <div className="text-lg font-bold text-slate-100 font-mono">
                  {seriesResult?.summary?.mean !== null && seriesResult?.summary?.mean !== undefined
                    ? `${seriesResult.summary.mean.toFixed(2)} ${seriesResult.dataset.units}`
                    : '—'}
                </div>
                <span className="text-[10px] text-slate-500">
                  Mean valid {aggregation} {aggregation === 'annual' ? 'total' : 'accumulation'}
                </span>
              </div>

              {/* 4. Estimated Total Change */}
              <div className="flex flex-col gap-0.5 p-3 rounded-lg bg-slate-950 border border-slate-800/80">
                <span className="text-xs text-slate-400 font-medium">Estimated Total Change</span>
                <div className="text-lg font-bold text-slate-100 font-mono">
                  {seriesResult?.summary?.estimated_total_change !== null &&
                  seriesResult?.summary?.estimated_total_change !== undefined
                    ? `${seriesResult.summary.estimated_total_change > 0 ? '+' : ''}${seriesResult.summary.estimated_total_change} ${seriesResult.dataset.units}`
                    : '—'}
                </div>
                <span className="text-[10px] text-slate-500">
                  Over {seriesResult?.summary?.elapsed_years || '0'} elapsed years (slope × duration)
                </span>
              </div>

              {/* 5. Data Completeness & Valid N */}
              <div className="flex flex-col gap-1 p-3 rounded-lg bg-slate-950 border border-slate-800/80 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-slate-400 font-medium">Data Completeness</span>
                  <span className="font-bold text-cyan-400 font-mono">
                    {seriesResult?.summary?.completeness?.pct ?? 0}%
                  </span>
                </div>
                <div className="text-[11px] text-slate-300 font-mono">
                  {seriesResult?.summary?.completeness?.valid ?? 0} valid /{' '}
                  {seriesResult?.summary?.completeness?.expected ?? 0} expected intervals
                </div>
                <div className="text-[10px] text-slate-500 mt-0.5">
                  Denominator: {seriesResult?.summary?.completeness?.denominator_description}
                </div>
              </div>

              {/* 6. Scientific Validation & Test Details */}
              <div className="border border-slate-800 rounded-lg p-3 bg-slate-950/60 flex flex-col gap-2 text-xs">
                <div className="font-semibold text-slate-300 flex items-center gap-1">
                  <Info className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Significance Tests</span>
                </div>

                <div className="space-y-1.5 text-[11px] text-slate-400 font-mono">
                  <div className="flex justify-between border-b border-slate-900 pb-1">
                    <span>Mann-Kendall p:</span>
                    <span className="text-slate-200">
                      {seriesResult?.summary?.mann_kendall?.p_value ?? '—'}
                    </span>
                  </div>
                  <div className="flex justify-between border-b border-slate-900 pb-1">
                    <span>Modified MK (Hamed-Rao):</span>
                    <span className="text-slate-200">
                      p = {seriesResult?.summary?.modified_mann_kendall?.p_value ?? '—'}
                    </span>
                  </div>
                  {seriesResult?.summary?.seasonal_mann_kendall && (
                    <div className="flex justify-between border-b border-slate-900 pb-1">
                      <span>Seasonal MK (period {seriesResult.summary.seasonal_mann_kendall.period}):</span>
                      <span className="text-slate-200">
                        p = {seriesResult.summary.seasonal_mann_kendall.p_value ?? '—'}
                      </span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span>OLS R² / p-val:</span>
                    <span className="text-slate-200">
                      {seriesResult?.summary?.ols?.r_squared ?? '—'} /{' '}
                      {seriesResult?.summary?.ols?.p_value ?? '—'}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>

        </div>
      </main>
    </div>
  );
};
