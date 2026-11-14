import React, { useRef } from 'react';
import createPlotlyComponent from 'react-plotly.js/factory';
import Plotly from 'plotly.js-dist-min';
import type { TimeSeriesPoint } from '../../api/trends';
import { Camera, Download, RotateCcw } from 'lucide-react';

const Plot = createPlotlyComponent(Plotly);

interface TimeSeriesChartProps {
  points: TimeSeriesPoint[];
  variableName: string;
  units: string;
  aggregation: 'monthly' | 'annual' | 'seasonal';
  showTrend: 'none' | 'ols' | 'sens';
  showConfidenceBand: boolean;
  showMovingAverage: boolean;
  showPoints: boolean;
  movingAverageWindow: number;
  onExportCSV: () => void;
}

export const TimeSeriesChart: React.FC<TimeSeriesChartProps> = ({
  points,
  variableName,
  units,
  aggregation,
  showTrend,
  showConfidenceBand,
  showMovingAverage,
  showPoints,
  movingAverageWindow,
  onExportCSV,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);

  // Performance downsampling for chart display only when series exceeds 1000 points (SPEC 16.3).
  // Exports (onExportCSV) and calculation pipelines always retain full series fidelity.
  const chartPoints = React.useMemo(() => {
    if (points.length <= 1000) return points;
    const stride = Math.ceil(points.length / 1000);
    return points.filter((_, idx) => idx % stride === 0 || idx === points.length - 1);
  }, [points]);

  // Separate coordinates
  const xDates = chartPoints.map((p) => p.date);
  const yValues = chartPoints.map((p) => p.value);

  // Custom hover data: [units, status/flag]
  const customData = chartPoints.map((p) => [
    p.units || units,
    p.is_missing ? (p.flags && p.flags.length > 0 ? p.flags.join(', ') : 'Missing data (NaN)') : 'Valid observation',
  ]);

  const traces: Plotly.Data[] = [];

  // 1. Confidence Band for OLS regression (rendered behind data)
  if (showConfidenceBand && showTrend === 'ols') {
    const yUpper = chartPoints.map((p) => p.ols_ci_upper ?? null);
    const yLower = chartPoints.map((p) => p.ols_ci_lower ?? null);

    // Upper line
    traces.push({
      x: xDates,
      y: yUpper,
      type: 'scatter',
      mode: 'lines',
      line: { width: 0, color: 'transparent' },
      showlegend: false,
      hoverinfo: 'skip',
    });

    // Lower line filling to upper line
    traces.push({
      x: xDates,
      y: yLower,
      type: 'scatter',
      mode: 'lines',
      line: { width: 0, color: 'transparent' },
      fill: 'tonexty',
      fillcolor: 'rgba(245, 158, 11, 0.16)', // subtle amber
      name: '95% Regression CI',
      hoverinfo: 'skip',
    });
  }

  // 2. Trend Line
  if (showTrend === 'ols') {
    const yOls = chartPoints.map((p) => p.fitted_ols ?? null);
    traces.push({
      x: xDates,
      y: yOls,
      type: 'scatter',
      mode: 'lines',
      name: 'Linear Fit (OLS)',
      line: { color: '#f59e0b', width: 2.5, dash: 'solid' },
      hovertemplate: '<b>Date:</b> %{x}<br><b>OLS Fit:</b> %{y:.2f} ' + units + '<extra></extra>',
    });
  } else if (showTrend === 'sens') {
    const ySens = chartPoints.map((p) => p.sens_line ?? null);
    traces.push({
      x: xDates,
      y: ySens,
      type: 'scatter',
      mode: 'lines',
      name: "Sen's Robust Slope",
      line: { color: '#10b981', width: 2.5, dash: 'dash' },
      hovertemplate: "<b>Date:</b> %{x}<br><b>Sen's Line:</b> %{y:.2f} " + units + '<extra></extra>',
    });
  }

  // 3. Moving Average
  if (showMovingAverage) {
    const yMa = chartPoints.map((p) => p.moving_avg ?? null);
    const windowLabel =
      aggregation === 'monthly'
        ? `${movingAverageWindow}-Month MA`
        : aggregation === 'seasonal'
        ? `${movingAverageWindow}-Season MA`
        : `${movingAverageWindow}-Year MA`;

    traces.push({
      x: xDates,
      y: yMa,
      type: 'scatter',
      mode: 'lines',
      name: windowLabel,
      line: { color: '#c084fc', width: 2, dash: 'dot' },
      hovertemplate: `<b>Date:</b> %{x}<br><b>${windowLabel}:</b> %{y:.2f} ${units}<extra></extra>`,
    });
  }

  // 4. Observed Time Series Trace (Scientific Rule: connectgaps = false!)
  traces.push({
    x: xDates,
    y: yValues,
    type: 'scatter',
    mode: showPoints ? 'lines+markers' : 'lines',
    name: `Observed (${aggregation})`,
    connectgaps: false, // CRITICAL: NEVER interpolate missing values silently!
    line: { color: '#38bdf8', width: 2 },
    marker: { size: 5, color: '#0284c7' },
    customdata: customData,
    hovertemplate:
      '<b>Date:</b> %{x}<br>' +
      '<b>Value:</b> %{y:.2f} %{customdata[0]}<br>' +
      '<b>Status:</b> %{customdata[1]}<extra></extra>',
  });

  const layout: Partial<Plotly.Layout> = {
    autosize: true,
    paper_bgcolor: 'transparent',
    plot_bgcolor: '#0f172a',
    font: {
      color: '#cbd5e1',
      family: 'ui-sans-serif, system-ui, sans-serif',
      size: 12,
    },
    margin: { l: 65, r: 25, t: 30, b: 60 },
    xaxis: {
      title: { text: 'Observation Date', font: { color: '#94a3b8' } },
      gridcolor: '#1e293b',
      zerolinecolor: '#334155',
      showgrid: true,
      tickfont: { color: '#94a3b8' },
    },
    yaxis: {
      title: { text: `${variableName} (${units})`, font: { color: '#94a3b8' } },
      gridcolor: '#1e293b',
      zerolinecolor: '#334155',
      showgrid: true,
      tickfont: { color: '#94a3b8' },
    },
    legend: {
      orientation: 'h',
      x: 0,
      y: -0.22,
      font: { color: '#cbd5e1', size: 11 },
      bgcolor: 'rgba(15, 23, 42, 0.8)',
    },
    hovermode: 'closest',
  };

  const handleDownloadPNG = () => {
    if (containerRef.current) {
      const plotEl = containerRef.current.querySelector('.js-plotly-plot') as Plotly.PlotlyHTMLElement;
      if (plotEl) {
        Plotly.downloadImage(plotEl, {
          format: 'png',
          width: 1200,
          height: 600,
          filename: `earth_trend_${variableName.toLowerCase()}_${aggregation}`,
        });
      }
    }
  };

  const handleResetZoom = () => {
    if (containerRef.current) {
      const plotEl = containerRef.current.querySelector('.js-plotly-plot') as Plotly.PlotlyHTMLElement;
      if (plotEl) {
        Plotly.relayout(plotEl, {
          'xaxis.autorange': true,
          'yaxis.autorange': true,
        });
      }
    }
  };

  return (
    <div className="flex flex-col h-full w-full" ref={containerRef}>
      {/* Top Chart Toolbar */}
      <div className="flex items-center justify-between px-3 py-2 bg-slate-900/80 border-b border-slate-800 text-xs">
        <div className="flex items-center gap-2 text-slate-400">
          <span className="font-medium text-slate-300">
            {variableName} ({aggregation.charAt(0).toUpperCase() + aggregation.slice(1)})
          </span>
          <span className="text-slate-600">|</span>
          <span className="text-slate-400">{points.length} intervals</span>
          <span className="text-amber-400/90 text-[11px] bg-amber-950/40 px-2 py-0.5 rounded border border-amber-800/40">
            connectgaps: false (no silent interpolation)
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleResetZoom}
            className="flex items-center gap-1 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors border border-slate-700/60"
            title="Reset Zoom"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Reset</span>
          </button>
          <button
            onClick={handleDownloadPNG}
            className="flex items-center gap-1 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors border border-slate-700/60"
            title="Export High-Resolution PNG"
          >
            <Camera className="w-3.5 h-3.5" />
            <span>PNG</span>
          </button>
          <button
            onClick={onExportCSV}
            className="flex items-center gap-1 px-2.5 py-1 rounded bg-cyan-950/60 hover:bg-cyan-900 text-cyan-300 hover:text-cyan-100 transition-colors border border-cyan-800/60"
            title="Download CSV of plotted series"
          >
            <Download className="w-3.5 h-3.5" />
            <span>CSV</span>
          </button>
        </div>
      </div>

      {/* Plot Canvas */}
      <div className="flex-1 w-full min-h-[380px] bg-slate-950">
        <Plot
          data={traces}
          layout={layout}
          config={{
            responsive: true,
            displayModeBar: false,
          }}
          useResizeHandler={true}
          style={{ width: '100%', height: '100%' }}
        />
      </div>
    </div>
  );
};
