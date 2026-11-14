import React, { useState, useRef, useMemo } from 'react';
import type { TimeSeriesPoint } from '../../api/trends';
import { ChevronDown, ChevronUp, Download, Search } from 'lucide-react';

interface VirtualDataTableProps {
  points: TimeSeriesPoint[];
  units: string;
  variableName: string;
  aggregation: string;
  onExportCSV: () => void;
}

const ROW_HEIGHT = 38;
const CONTAINER_HEIGHT = 280;
const OVERSCAN = 6;

export const VirtualDataTable: React.FC<VirtualDataTableProps> = ({
  points,
  units,
  variableName,
  aggregation,
  onExportCSV,
}) => {
  const [isExpanded, setIsExpanded] = useState<boolean>(false);
  const [filterText, setFilterText] = useState<string>('');
  const [scrollTop, setScrollTop] = useState<number>(0);
  const containerRef = useRef<HTMLDivElement>(null);

  // Filtered rows
  const filteredPoints = useMemo(() => {
    if (!filterText.trim()) return points;
    const lower = filterText.toLowerCase();
    return points.filter(
      (p) =>
        p.date.toLowerCase().includes(lower) ||
        (p.flags && p.flags.some((f) => f.toLowerCase().includes(lower))) ||
        (p.is_missing ? 'missing' : 'valid').includes(lower)
    );
  }, [points, filterText]);

  // Virtual slice calculation
  const totalCount = filteredPoints.length;
  const startIndex = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - OVERSCAN);
  const endIndex = Math.min(
    totalCount,
    Math.ceil((scrollTop + CONTAINER_HEIGHT) / ROW_HEIGHT) + OVERSCAN
  );

  const visiblePoints = filteredPoints.slice(startIndex, endIndex);
  const topPadding = startIndex * ROW_HEIGHT;
  const bottomPadding = Math.max(0, (totalCount - endIndex) * ROW_HEIGHT);

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    setScrollTop(e.currentTarget.scrollTop);
  };

  const missingCount = useMemo(() => points.filter((p) => p.is_missing).length, [points]);
  const validCount = points.length - missingCount;

  return (
    <div className="border border-slate-800 rounded-lg bg-slate-900/90 overflow-hidden shadow-lg">
      {/* Header Bar */}
      <div className="flex items-center justify-between px-4 py-3 bg-slate-900 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex items-center gap-2 text-sm font-semibold text-slate-200 hover:text-cyan-400 transition-colors"
          >
            {isExpanded ? <ChevronUp className="w-4 h-4 text-cyan-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
            <span>Plotted Data Table</span>
            <span className="text-xs font-normal text-slate-400">
              ({points.length} {aggregation} intervals: <span className="text-emerald-400">{validCount} valid</span>, <span className="text-amber-400">{missingCount} missing</span>)
            </span>
          </button>
        </div>

        <div className="flex items-center gap-2">
          {isExpanded && (
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-slate-400" />
              <input
                type="text"
                value={filterText}
                onChange={(e) => {
                  setFilterText(e.target.value);
                  setScrollTop(0);
                }}
                placeholder="Filter date or flag..."
                className="pl-8 pr-3 py-1 bg-slate-950 border border-slate-700 rounded text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 w-44"
              />
            </div>
          )}
          <button
            onClick={onExportCSV}
            className="flex items-center gap-1.5 px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-xs border border-slate-700 transition-colors"
            title="Download CSV matching exact plotted table"
          >
            <Download className="w-3.5 h-3.5 text-cyan-400" />
            <span>Download CSV</span>
          </button>
        </div>
      </div>

      {/* Expandable Virtual Table Content */}
      {isExpanded && (
        <div className="flex flex-col">
          {/* Table Header */}
          <div className="grid grid-cols-12 px-4 py-2 bg-slate-950 border-b border-slate-800 text-xs font-medium text-slate-400">
            <div className="col-span-2">Date / Interval</div>
            <div className="col-span-2 text-right">Value ({units})</div>
            <div className="col-span-2 text-center">Quality Status</div>
            <div className="col-span-2 text-right">Moving Avg</div>
            <div className="col-span-2 text-right">OLS Fit</div>
            <div className="col-span-2 pl-3">Diagnostic Flags</div>
          </div>

          {/* Virtual Body */}
          <div
            ref={containerRef}
            onScroll={handleScroll}
            className="overflow-y-auto divide-y divide-slate-800/40"
            style={{ height: `${CONTAINER_HEIGHT}px` }}
          >
            <div style={{ height: `${topPadding}px` }} />

            {visiblePoints.map((pt, i) => {
              const actualIdx = startIndex + i;
              const isMissing = pt.is_missing || pt.value === null;

              return (
                <div
                  key={pt.date || actualIdx}
                  className={`grid grid-cols-12 px-4 items-center text-xs transition-colors ${
                    isMissing
                      ? 'bg-amber-950/20 hover:bg-amber-950/30 text-amber-200/90'
                      : actualIdx % 2 === 0
                      ? 'bg-slate-900/40 hover:bg-slate-800/60 text-slate-300'
                      : 'bg-slate-900/10 hover:bg-slate-800/60 text-slate-300'
                  }`}
                  style={{ height: `${ROW_HEIGHT}px` }}
                >
                  <div className="col-span-2 font-mono text-[11px] text-slate-300">
                    {pt.date}
                  </div>

                  <div className="col-span-2 text-right font-mono text-[11px]">
                    {pt.value !== null && pt.value !== undefined ? (
                      <span className="font-semibold text-slate-100">{pt.value.toFixed(2)}</span>
                    ) : (
                      <span className="text-amber-400 italic">NaN (gap)</span>
                    )}
                  </div>

                  <div className="col-span-2 text-center">
                    {isMissing ? (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-amber-950/60 text-amber-400 border border-amber-800/60">
                        Missing
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-950/60 text-emerald-400 border border-emerald-800/60">
                        Valid
                      </span>
                    )}
                  </div>

                  <div className="col-span-2 text-right font-mono text-[11px] text-purple-300/80">
                    {pt.moving_avg !== null && pt.moving_avg !== undefined
                      ? pt.moving_avg.toFixed(2)
                      : '—'}
                  </div>

                  <div className="col-span-2 text-right font-mono text-[11px] text-amber-300/80">
                    {pt.fitted_ols !== null && pt.fitted_ols !== undefined
                      ? pt.fitted_ols.toFixed(2)
                      : '—'}
                  </div>

                  <div className="col-span-2 pl-3 text-[11px] truncate text-slate-400" title={pt.flags?.join(', ') || ''}>
                    {pt.flags && pt.flags.length > 0 ? (
                      <span className="text-amber-400/90">{pt.flags.join(', ')}</span>
                    ) : (
                      <span className="text-slate-500">—</span>
                    )}
                  </div>
                </div>
              );
            })}

            <div style={{ height: `${bottomPadding}px` }} />
          </div>

          {/* Table Footer */}
          <div className="px-4 py-2 bg-slate-950 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
            <span>
              Showing {filteredPoints.length} of {points.length} records
            </span>
            <span className="text-slate-500">
              Units: {units} | Variable: {variableName}
            </span>
          </div>
        </div>
      )}
    </div>
  );
};
