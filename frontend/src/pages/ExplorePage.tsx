import React, { useEffect, useState, useMemo } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { 
  Search, 
  Layers, 
  Calendar, 
  Maximize2, 
  ExternalLink, 
  X, 
  ArrowRight, 
  AlertCircle, 
  RefreshCw, 
  Loader2, 
  Info,
  Sliders,
  HelpCircle
} from 'lucide-react';
import { fetchVariables, type VariableCatalogItem, type DatasetCatalogItem, formatObservationDate, formatCatalogueCheck } from '../api/catalog';
import { StatusChip } from '../components/StatusChip';
import { StepIndicator } from '../components/StepIndicator';
import { useSession, type AnalysisFrequency } from '../store/session';
import { clampStartDate, getDefaultStartDate, PROJECT_DEFAULT_START_DATE } from '../utils/dateClamp';

export const ExplorePage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  // Zustand Store
  const setSelectedVariablesInStore = useSession((s) => s.setSelectedVariables);
  const setDateRangeInStore = useSession((s) => s.setDateRange);
  const setFrequencyInStore = useSession((s) => s.setFrequency);

  // Catalog Data
  const [variables, setVariables] = useState<VariableCatalogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<'All' | 'Atmosphere' | 'Land' | 'Ocean'>('All');

  // Selected State on Page 1
  const [selectedVarId, setSelectedVarId] = useState<string>('');
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>('');
  const [startDate, setStartDate] = useState<string>(PROJECT_DEFAULT_START_DATE);
  const [endMode, setEndMode] = useState<'latest_complete' | 'custom'>('latest_complete');
  const [customEndDate, setCustomEndDate] = useState<string>('');
  const [frequency, setFrequency] = useState<AnalysisFrequency>('monthly');

  // Details Drawer State
  const [drawerDataset, setDrawerDataset] = useState<DatasetCatalogItem | null>(null);

  // Fetch catalog on mount
  const loadCatalog = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchVariables();
      setVariables(data);

      if (data.length > 0) {
        // Preselection from query param if available
        const paramVar = searchParams.get('variable');
        const initialVar = data.find((v) => v.id === paramVar) || data[0];
        setSelectedVarId(initialVar.id);

        const initialDs = initialVar.datasets.find((d) => d.id === initialVar.default_dataset_id) || initialVar.datasets[0];
        if (initialDs) {
          setSelectedDatasetId(initialDs.id);
          setStartDate(getDefaultStartDate(initialDs.start_date));
        }
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load variables';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCatalog();
  }, []);

  // Update selected dataset and clamp dates when selected variable changes
  const activeVariable = useMemo(() => {
    return variables.find((v) => v.id === selectedVarId) || null;
  }, [variables, selectedVarId]);

  const activeDataset = useMemo(() => {
    if (!activeVariable) return null;
    return activeVariable.datasets.find((d) => d.id === selectedDatasetId) || activeVariable.datasets[0] || null;
  }, [activeVariable, selectedDatasetId]);

  // Handle changing variable card selection
  const handleSelectVariable = (varItem: VariableCatalogItem) => {
    setSelectedVarId(varItem.id);
    const defaultDs = varItem.datasets.find((d) => d.id === varItem.default_dataset_id) || varItem.datasets[0];
    if (defaultDs) {
      setSelectedDatasetId(defaultDs.id);
      setStartDate(getDefaultStartDate(defaultDs.start_date));
    }
  };

  // Handle start date input with clamping
  const handleStartDateChange = (val: string) => {
    if (!activeDataset) {
      setStartDate(val);
      return;
    }
    const clamped = clampStartDate(val, activeDataset.start_date);
    setStartDate(clamped);
  };

  // Filtered variables list
  const filteredVariables = useMemo(() => {
    return variables.filter((v) => {
      const matchesCategory = selectedCategory === 'All' || v.category.toLowerCase() === selectedCategory.toLowerCase();
      const query = searchQuery.trim().toLowerCase();
      const matchesQuery = 
        query === '' ||
        v.name.toLowerCase().includes(query) ||
        v.description.toLowerCase().includes(query) ||
        v.datasets.some((d) => d.product_name.toLowerCase().includes(query) || d.id.toLowerCase().includes(query));
      return matchesCategory && matchesQuery;
    });
  }, [variables, selectedCategory, searchQuery]);

  // Handle Continue to Page 2 (/region)
  const handleContinue = () => {
    if (!activeVariable || !activeDataset) return;

    // Save selection to Zustand session store (SPEC 5.5)
    setSelectedVariablesInStore([
      {
        variableId: activeVariable.id,
        datasetId: activeDataset.id,
        datasetVersion: activeDataset.version,
        fieldName: activeDataset.native_variable_name,
        units: activeDataset.units,
        spatialCoverage: activeDataset.spatial_coverage,
        citation: activeDataset.citation || undefined,
        caveat: activeDataset.known_limitations || undefined,
      },
    ]);

    setDateRangeInStore({
      start: startDate,
      endMode: endMode,
      end: endMode === 'custom' ? customEndDate : undefined,
    });

    setFrequencyInStore(frequency);

    // Navigate to Page 2: Geographic Explorer
    navigate('/region');
  };

  return (
    <div className="min-h-screen bg-background pb-20">
      {/* Step Indicator */}
      <StepIndicator currentStep={1} />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-8 space-y-8">
        {/* 5.1 Header */}
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-xs font-mono text-cyan-400">
            <Layers className="w-3.5 h-3.5" />
            <span>Step 1 • Variable & Dataset Discovery</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
            Data Explorer
          </h1>
          <p className="text-sm text-slate-300 max-w-3xl leading-relaxed">
            Select an Earth-science variable, choose an authoritative dataset product, and define your temporal analysis baseline.
          </p>
        </div>

        {/* 5.1 Search & Category Filters */}
        <div className="flex flex-col md:flex-row gap-4 items-stretch md:items-center justify-between bg-navy-850 border border-border-subtle p-4 rounded-card shadow-sm">
          {/* Search bar */}
          <div className="relative flex-1 max-w-md">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search variable or dataset name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-navy-900 border border-slate-700 rounded-md text-xs text-slate-100 placeholder-slate-400 focus:outline-none focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Category filter pills */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-slate-400 mr-1 hidden sm:inline">Category:</span>
            {(['All', 'Atmosphere', 'Land', 'Ocean'] as const).map((cat) => (
              <button
                key={cat}
                type="button"
                onClick={() => setSelectedCategory(cat)}
                className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors cursor-pointer ${
                  selectedCategory === cat
                    ? 'bg-accent-blue text-navy-950 font-bold shadow-sm'
                    : 'bg-navy-800 text-slate-300 hover:bg-navy-700 hover:text-white border border-slate-700/60'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        {/* API Loading, Error & Empty States */}
        {loading && (
          <div className="bg-navy-800/40 border border-border-subtle rounded-card p-16 text-center space-y-3">
            <Loader2 className="w-8 h-8 text-cyan-400 animate-spin mx-auto" />
            <p className="text-sm font-semibold text-slate-200">Loading catalog variables...</p>
            <p className="text-xs text-slate-400">Connecting to FastAPI catalog service at /api/catalog/variables</p>
          </div>
        )}

        {!loading && error && (
          <div className="bg-red-950/30 border border-red-800/40 rounded-card p-8 text-center space-y-4">
            <AlertCircle className="w-8 h-8 text-rose-400 mx-auto" />
            <div className="space-y-1">
              <h3 className="text-base font-bold text-rose-200">Failed to load variable catalog</h3>
              <p className="text-xs text-rose-300/80 font-mono">{error}</p>
            </div>
            <button
              type="button"
              onClick={loadCatalog}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-md bg-navy-800 border border-slate-700 text-slate-200 text-xs font-medium hover:bg-navy-700"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Retry</span>
            </button>
          </div>
        )}

        {!loading && !error && filteredVariables.length === 0 && (
          <div className="bg-navy-800/40 border border-border-subtle rounded-card p-12 text-center space-y-3">
            <Info className="w-8 h-8 text-slate-400 mx-auto" />
            <h3 className="text-base font-bold text-slate-200">No matching variables found</h3>
            <p className="text-xs text-slate-400 max-w-sm mx-auto">
              No configured variables matched your search criteria. Try clearing filters.
            </p>
            <button
              type="button"
              onClick={() => { setSearchQuery(''); setSelectedCategory('All'); }}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-navy-800 text-xs text-cyan-300 border border-slate-700 hover:bg-navy-700"
            >
              Reset Filters
            </button>
          </div>
        )}

        {/* Database Offline Seed Fallback Banner (SPEC 3.2 / Requirement 6) */}
        {!loading && !error && variables.some((v) => v.status === 'Needs validation') && (
          <div className="bg-purple-950/40 border border-purple-600/50 rounded-card p-4 flex items-center gap-3 text-purple-200 text-sm shadow-card">
            <HelpCircle className="w-5 h-5 text-purple-400 shrink-0" />
            <div>
              <span className="font-semibold text-purple-100">Database is offline.</span> Catalogue is running from local seed files. Datasets require validation.
            </div>
          </div>
        )}

        {/* 5.1 Main Layout: 3 Columns on desktop (Cards list + Config panel) */}
        {!loading && !error && filteredVariables.length > 0 && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
            {/* Left 7 cols: Variable Catalogue Cards */}
            <div className="lg:col-span-7 space-y-4">
              <div className="flex items-center justify-between text-xs text-slate-400 px-1">
                <span>Select a variable below to configure:</span>
                <span className="font-mono">{filteredVariables.length} available</span>
              </div>

              <div className="space-y-4">
                {filteredVariables.map((v) => {
                  const isSelected = v.id === selectedVarId;
                  const defaultDs = v.datasets.find((d) => d.id === v.default_dataset_id) || v.datasets[0];

                  return (
                    <div
                      key={v.id}
                      onClick={() => handleSelectVariable(v)}
                      className={`relative bg-navy-850 border rounded-card p-5 space-y-4 transition-all cursor-pointer ${
                        isSelected
                          ? 'border-cyan-400 ring-2 ring-cyan-400/20 shadow-lg shadow-cyan-950/50'
                          : 'border-border-subtle hover:border-accent-blue/50'
                      }`}
                    >
                      {/* Top Header of Card */}
                      <div className="flex items-start justify-between gap-3">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-accent-blue/15 text-cyan-300 border border-accent-blue/30">
                              {v.category}
                            </span>
                            <StatusChip status={v.status as any} />
                          </div>
                          <h3 className="text-xl font-bold text-white tracking-tight pt-1">
                            {v.name}
                          </h3>
                        </div>

                        {/* Details Drawer Button */}
                        {defaultDs && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setDrawerDataset(defaultDs);
                            }}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-navy-800 hover:bg-navy-700 border border-slate-700 text-slate-300 hover:text-white text-xs font-medium transition-colors"
                            title="Inspect complete metadata in drawer"
                          >
                            <Maximize2 className="w-3 h-3 text-cyan-400" />
                            <span>Details</span>
                          </button>
                        )}
                      </div>

                      {/* Description & Scientific Question */}
                      <p className="text-xs text-slate-300 leading-relaxed">
                        {v.description}
                      </p>

                      {/* Scientific Caveat if known */}
                      {defaultDs?.known_limitations && (
                        <div className="flex items-start gap-2 p-2.5 rounded bg-amber-950/25 border border-amber-800/40 text-[11px] text-amber-200/90 leading-snug">
                          <AlertCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                          <div>
                            <span className="font-semibold text-amber-400 block mb-0.5">Scientific Caveat</span>
                            <span>{defaultDs.known_limitations}</span>
                          </div>
                        </div>
                      )}

                      <div className="bg-navy-900/60 rounded p-2.5 border border-border-subtle text-xs space-y-1">
                        <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">
                          What can we discover?
                        </span>
                        <p className="text-xs text-cyan-200/90 italic">
                          "{v.scientific_question}"
                        </p>
                      </div>

                      {/* Product details summary */}
                      {defaultDs && (
                        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 pt-2 border-t border-border-subtle/80 text-[11px]">
                          <div>
                            <span className="text-slate-500 block">Product</span>
                            <span className="text-slate-200 font-medium truncate block">{defaultDs.short_name} ({defaultDs.version})</span>
                          </div>
                          <div>
                            <span className="text-slate-500 block">Native Units</span>
                            <span className="text-cyan-300 font-mono block">{defaultDs.units}</span>
                          </div>
                          <div>
                            <span className="text-slate-500 block">Resolution</span>
                            <span className="text-slate-200 font-mono block">{defaultDs.spatial_resolution}</span>
                          </div>
                          <div>
                            <span className="text-slate-500 block">Start Date</span>
                            <span className="text-slate-200 font-mono block">{defaultDs.start_date}</span>
                          </div>
                          <div>
                            <span className="text-slate-500 block">Latest Obs.</span>
                            <span className="text-cyan-300 font-mono block">
                              {defaultDs.latest_observation_date
                                ? formatObservationDate(defaultDs.latest_observation_date)
                                : 'Pending'}
                            </span>
                          </div>
                        </div>
                      )}

                      {/* SPEC 5.4 Preview Graph Rule: No numerical placeholder graph */}
                      <div className="bg-navy-900/40 rounded-md p-3 border border-dashed border-slate-700/80 text-center">
                        <span className="text-xs text-slate-400 italic">
                          Preview available once data is loaded (Phase 3a)
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Right 5 cols: 5.1 Configuration Area & 5.5 Selection Summary */}
            <div className="lg:col-span-5 space-y-6 lg:sticky lg:top-24">
              {/* Configuration Card */}
              <div className="bg-navy-850 border border-border-subtle rounded-card p-6 space-y-5 shadow-md">
                <div className="flex items-center gap-2 border-b border-border-subtle pb-3">
                  <Sliders className="w-4 h-4 text-cyan-400" />
                  <h2 className="text-base font-bold text-white tracking-tight">
                    Dataset Configuration
                  </h2>
                </div>

                {activeVariable && activeDataset ? (
                  <div className="space-y-5">
                    {/* Dataset / Version Selector */}
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-slate-300 block">
                        Dataset & Pinned Version
                      </label>
                      <select
                        value={selectedDatasetId}
                        onChange={(e) => {
                          setSelectedDatasetId(e.target.value);
                          const ds = activeVariable.datasets.find((d) => d.id === e.target.value);
                          if (ds) {
                            setStartDate(getDefaultStartDate(ds.start_date));
                          }
                        }}
                        className="w-full bg-navy-900 border border-slate-700 rounded-md px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-cyan-400"
                      >
                        {activeVariable.datasets.map((d) => (
                          <option key={d.id} value={d.id}>
                            {d.product_name} ({d.version})
                          </option>
                        ))}
                      </select>
                      <span className="text-[11px] text-slate-400 block">
                        Provider: {activeDataset.provider}
                      </span>
                    </div>

                    {/* Start Date Control (Clamped to product start date per SPEC 5.3) */}
                    <div className="space-y-1.5">
                      <div className="flex justify-between items-center text-xs">
                        <label className="font-semibold text-slate-300">
                          Analysis Start Date
                        </label>
                        <span className="text-[11px] text-slate-500 font-mono">
                          Product start: {activeDataset.start_date}
                        </span>
                      </div>
                      <div className="relative">
                        <Calendar className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                        <input
                          type="date"
                          value={startDate}
                          min={activeDataset.start_date}
                          onChange={(e) => handleStartDateChange(e.target.value)}
                          className="w-full pl-9 pr-3 py-2 bg-navy-900 border border-slate-700 rounded-md text-xs text-slate-100 focus:outline-none focus:border-cyan-400"
                        />
                      </div>
                      <span className="text-[11px] text-slate-400 block">
                        Project default: 1990-01-01 (clamped to product start date if later).
                      </span>
                    </div>

                    {/* End Date Control (SPEC 5.3: Latest Complete Mode) */}
                    <div className="space-y-2">
                      <label className="text-xs font-semibold text-slate-300 block">
                        Analysis End Date
                      </label>
                      <div className="grid grid-cols-2 gap-2">
                        <button
                          type="button"
                          onClick={() => setEndMode('latest_complete')}
                          className={`px-3 py-2 rounded text-xs font-medium border text-left cursor-pointer transition-colors ${
                            endMode === 'latest_complete'
                              ? 'bg-accent-blue/15 border-cyan-400 text-cyan-300'
                              : 'bg-navy-900 border-slate-700 text-slate-400 hover:text-slate-200'
                          }`}
                        >
                          <span className="font-semibold block">Latest complete</span>
                          <span className="text-[10px] text-slate-400 block">Recommended</span>
                        </button>

                        <button
                          type="button"
                          onClick={() => setEndMode('custom')}
                          className={`px-3 py-2 rounded text-xs font-medium border text-left cursor-pointer transition-colors ${
                            endMode === 'custom'
                              ? 'bg-accent-blue/15 border-cyan-400 text-cyan-300'
                              : 'bg-navy-900 border-slate-700 text-slate-400 hover:text-slate-200'
                          }`}
                        >
                          <span className="font-semibold block">Custom date</span>
                          <span className="text-[10px] text-slate-400 block">Specific cut-off</span>
                        </button>
                      </div>

                      {endMode === 'latest_complete' ? (
                        <div className="bg-navy-900/60 p-2.5 rounded border border-slate-700/60 text-xs text-slate-300 space-y-1">
                          <div className="flex items-center justify-between">
                            <span>Latest verified observation:</span>
                            {activeDataset?.latest_observation_date ? (
                              <span className="font-mono text-cyan-300 font-semibold">
                                {formatObservationDate(activeDataset.latest_observation_date)}
                              </span>
                            ) : (
                              <StatusChip status="Needs validation" customLabel="Checking…" />
                            )}
                          </div>
                          {activeDataset?.last_catalogue_check && (
                            <div className="flex items-center justify-between text-[11px] text-slate-500">
                              <span>Last catalogue check:</span>
                              <span className="font-mono">{formatCatalogueCheck(activeDataset.last_catalogue_check)}</span>
                            </div>
                          )}
                        </div>
                      ) : (
                        <input
                          type="date"
                          value={customEndDate}
                          min={startDate}
                          onChange={(e) => setCustomEndDate(e.target.value)}
                          className="w-full px-3 py-2 bg-navy-900 border border-slate-700 rounded-md text-xs text-slate-100 focus:outline-none focus:border-cyan-400"
                        />
                      )}
                    </div>

                    {/* Temporal Frequency Selector */}
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-slate-300 block">
                        Analysis Frequency
                      </label>
                      <div className="grid grid-cols-3 gap-2">
                        {(['monthly', 'annual', 'seasonal'] as const).map((freq) => (
                          <button
                            key={freq}
                            type="button"
                            onClick={() => setFrequency(freq)}
                            className={`py-1.5 px-2 rounded text-xs capitalize text-center font-medium border transition-colors cursor-pointer ${
                              frequency === freq
                                ? 'bg-accent-blue/20 border-cyan-400 text-cyan-300'
                                : 'bg-navy-900 border-slate-700 text-slate-400 hover:text-slate-200'
                            }`}
                          >
                            {freq}
                          </button>
                        ))}
                      </div>
                      <span className="text-[11px] text-slate-500 block">
                        Native grid is monthly; annual/seasonal aggregated per Scientific Rule 7.
                      </span>
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-slate-400">Select a variable to configure.</p>
                )}
              </div>

              {/* 5.1 & 5.5 Selection Summary Card */}
              {activeVariable && activeDataset && (
                <div className="bg-navy-900/80 border border-cyan-500/30 rounded-card p-5 space-y-4 shadow-lg">
                  <h3 className="text-xs font-mono uppercase tracking-wider text-cyan-300 font-bold">
                    Selection Summary
                  </h3>

                  <div className="space-y-2 text-xs divide-y divide-border-subtle/50">
                    <div className="flex justify-between pt-1">
                      <span className="text-slate-400">Variable:</span>
                      <span className="font-semibold text-white">{activeVariable.name}</span>
                    </div>
                    <div className="flex justify-between pt-1.5">
                      <span className="text-slate-400">Dataset & Version:</span>
                      <span className="font-mono text-cyan-300">{activeDataset.short_name} ({activeDataset.version})</span>
                    </div>
                    <div className="flex justify-between pt-1.5">
                      <span className="text-slate-400">Native Units:</span>
                      <span className="font-mono text-slate-200">{activeDataset.units}</span>
                    </div>
                    <div className="flex justify-between pt-1.5">
                      <span className="text-slate-400">Date Range:</span>
                      <span className="font-mono text-slate-200">
                        {startDate} → {endMode === 'latest_complete' ? 'Latest complete' : customEndDate || 'Unspecified'}
                      </span>
                    </div>
                    <div className="flex justify-between pt-1.5">
                      <span className="text-slate-400">Frequency:</span>
                      <span className="capitalize text-slate-200">{frequency}</span>
                    </div>
                    <div className="flex justify-between items-center pt-1.5">
                      <span className="text-slate-400">Coverage Status:</span>
                      <StatusChip status={activeDataset.status as any} />
                    </div>
                  </div>

                  {/* Active Dataset Caveat */}
                  {activeDataset.known_limitations && (
                    <div className="bg-amber-950/30 border border-amber-600/40 rounded p-2.5 text-xs text-amber-200/90 space-y-1">
                      <div className="flex items-center gap-1.5 font-semibold text-amber-400 text-[11px]">
                        <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                        <span>Variable Caveat</span>
                      </div>
                      <p className="text-[10.5px] leading-relaxed text-amber-200/80">
                        {activeDataset.known_limitations}
                      </p>
                    </div>
                  )}

                  {/* Continue Button */}
                  {(() => {
                    const isUnavailable = activeDataset.status.startsWith('Unavailable');
                    return (
                      <button
                        type="button"
                        disabled={isUnavailable}
                        onClick={handleContinue}
                        className={`w-full inline-flex items-center justify-center gap-2 py-3 px-4 rounded-lg font-bold text-sm shadow-md transition-all ${
                          isUnavailable
                            ? 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700'
                            : 'bg-gradient-to-r from-accent-blue to-accent-cyan text-navy-950 hover:opacity-95 shadow-accent-blue/20 cursor-pointer transform hover:-translate-y-0.5'
                        }`}
                      >
                        <span>{isUnavailable ? activeDataset.status : 'Continue to Geographic Explorer'}</span>
                        {!isUnavailable && <ArrowRight className="w-4 h-4" />}
                      </button>
                    );
                  })()}
                </div>
              )}
            </div>
          </div>
        )}
      </main>

      {/* 5.1 Details Drawer */}
      {drawerDataset && (
        <div className="fixed inset-0 z-50 overflow-hidden bg-black/60 backdrop-blur-sm flex justify-end animate-fadeIn">
          <div className="w-full max-w-xl bg-navy-900 border-l border-border-subtle h-full overflow-y-auto p-6 space-y-6 shadow-2xl flex flex-col justify-between">
            <div className="space-y-6">
              {/* Header */}
              <div className="flex items-start justify-between border-b border-border-subtle pb-4">
                <div>
                  <span className="text-xs font-mono text-cyan-400 uppercase tracking-wider">
                    Dataset Specifications & Provenance
                  </span>
                  <h2 className="text-xl font-bold text-white mt-1">
                    {drawerDataset.product_name}
                  </h2>
                </div>
                <button
                  type="button"
                  onClick={() => setDrawerDataset(null)}
                  className="p-1 rounded text-slate-400 hover:text-white hover:bg-navy-800"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Verified Product Metadata */}
              <div className="space-y-3">
                <h3 className="text-xs font-mono font-bold text-slate-300 uppercase">Core Properties</h3>
                <div className="bg-navy-850 rounded-lg p-4 border border-border-subtle space-y-2 text-xs">
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <span className="text-slate-500 block">Pinned Version:</span>
                      <span className="font-mono text-cyan-300 font-semibold">{drawerDataset.version}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block">Native Variable:</span>
                      <span className="font-mono text-slate-200">{drawerDataset.native_variable_name}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block">Spatial Resolution:</span>
                      <span className="font-mono text-slate-200">{drawerDataset.spatial_resolution}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block">Temporal Resolution:</span>
                      <span className="font-mono text-slate-200">{drawerDataset.temporal_resolution}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block">Coordinate System (CRS):</span>
                      <span className="font-mono text-slate-200">{drawerDataset.crs}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block">Record Start:</span>
                      <span className="font-mono text-slate-200">{drawerDataset.start_date}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Status of Verification / Scientific Gating */}
              <div className="space-y-3">
                <h3 className="text-xs font-mono font-bold text-slate-300 uppercase">Verification Audit</h3>
                <div className="bg-navy-850 rounded-lg p-4 border border-border-subtle space-y-3 text-xs">
                  {/* Latest Observation Date — real value from DB (SPEC 6.3 & 15.3) */}
                  <div className="flex justify-between items-center">
                    <span className="text-slate-300">Latest Observation Date:</span>
                    {drawerDataset.latest_observation_date ? (
                      <span className="font-mono text-cyan-300 font-semibold">
                        {formatObservationDate(drawerDataset.latest_observation_date)}
                      </span>
                    ) : (
                      <StatusChip status="Needs validation" customLabel="Not yet checked" />
                    )}
                  </div>
                  {/* Last Catalogue Check — separate timestamp per SPEC 15.3 */}
                  <div className="flex justify-between items-center">
                    <span className="text-slate-300">Last Catalogue Check:</span>
                    {drawerDataset.last_catalogue_check ? (
                      <span className="font-mono text-slate-300 text-[11px]">
                        {formatCatalogueCheck(drawerDataset.last_catalogue_check)}
                      </span>
                    ) : (
                      <StatusChip status="Needs validation" customLabel="Never" />
                    )}
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-300">DOI / Identifier:</span>
                    <StatusChip status="Needs validation" customLabel={drawerDataset.doi || "Needs validation"} />
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-300">Update Latency:</span>
                    <StatusChip status="Needs validation" customLabel="Needs validation" />
                  </div>
                </div>
              </div>

              {/* Missing Data Policy & Limitations */}
              <div className="space-y-3">
                <h3 className="text-xs font-mono font-bold text-slate-300 uppercase">Scientific Decisions & Limitations</h3>
                <div className="bg-navy-850 rounded-lg p-4 border border-border-subtle space-y-3 text-xs leading-relaxed text-slate-300">
                  <div>
                    <span className="font-semibold text-slate-200 block mb-1">No-Data Mask Semantics (Rule 3):</span>
                    <p className="text-slate-400 bg-navy-900 p-2 rounded font-mono text-[11px]">
                      {drawerDataset.no_data_mask_semantics || "Values <= -9.0e36 or outside valid range [0, 100] decoded to NaN. Missing is never zero."}
                    </p>
                  </div>
                  <div>
                    <span className="font-semibold text-slate-200 block mb-1">Known Reprocessing / Caveats (SPEC 6.1):</span>
                    <p className="text-slate-400">
                      {drawerDataset.known_limitations}
                    </p>
                  </div>
                </div>
              </div>

              {/* Documentation & Citation */}
              <div className="space-y-2 text-xs">
                <span className="font-semibold text-slate-300 block">Citation:</span>
                <p className="text-slate-400 italic bg-navy-850 p-3 rounded border border-border-subtle">
                  {drawerDataset.citation}
                </p>
                {drawerDataset.product_documentation && (
                  <div className="pt-2">
                    <a
                      href={drawerDataset.product_documentation}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1.5 text-cyan-400 hover:text-cyan-300 text-xs font-medium"
                    >
                      <span>Official Product Documentation</span>
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  </div>
                )}
              </div>
            </div>

            {/* Footer of Drawer */}
            <div className="pt-4 border-t border-border-subtle">
              <button
                type="button"
                onClick={() => setDrawerDataset(null)}
                className="w-full py-2.5 px-4 rounded bg-navy-800 hover:bg-navy-700 text-slate-200 text-xs font-semibold"
              >
                Close Drawer
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
