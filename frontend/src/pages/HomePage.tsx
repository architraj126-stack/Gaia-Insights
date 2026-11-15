import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { 
  ArrowRight, 
  Layers, 
  TrendingUp, 
  Sparkles, 
  FileText, 
  AlertCircle, 
  RefreshCw, 
  Loader2, 
  Database, 
  Info 
} from 'lucide-react';
import heroImage from '../assets/hero.png';
import { fetchVariables, type VariableCatalogItem } from '../api/catalog';
import { StatusChip } from '../components/StatusChip';
import { useSession } from '../store/session';

export const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const setSelectedVariables = useSession((s) => s.setSelectedVariables);

  const [variables, setVariables] = useState<VariableCatalogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadVariables = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchVariables();
      setVariables(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to connect to catalog API';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadVariables();
  }, []);

  const handleSelectVariable = (v: VariableCatalogItem) => {
    const defaultDs = v.datasets.find((d) => d.id === v.default_dataset_id) || v.datasets[0];
    if (defaultDs) {
      setSelectedVariables([
        {
          variableId: v.id,
          datasetId: defaultDs.id,
          datasetVersion: defaultDs.version,
          fieldName: defaultDs.native_variable_name,
          units: defaultDs.units,
          spatialCoverage: defaultDs.spatial_coverage,
          citation: defaultDs.citation || undefined,
        },
      ]);
    }
    navigate(`/explore?variable=${v.id}`);
  };

  return (
    <div className="space-y-16 lg:space-y-24 pb-16">
      {/* 4.2 Hero Section */}
      <section className="relative overflow-hidden pt-8 pb-12 sm:pt-16 sm:pb-20 border-b border-border-subtle bg-gradient-to-b from-navy-950 via-background to-background">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-center">
            {/* Left copy */}
            <div className="lg:col-span-7 space-y-6 text-left">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-accent-blue/10 border border-accent-blue/30 text-xs font-mono text-cyan-300">
                <span className="w-2 h-2 rounded-full bg-accent-cyan animate-pulse" />
                <span>Historical Observational Data • NASA & NOAA Records</span>
              </div>

              <h1 className="text-3xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-white leading-tight break-words">
                Understand Our <span className="text-transparent bg-clip-text bg-gradient-to-r from-accent-blue via-cyan-400 to-accent-cyan">Changing Earth.</span>
              </h1>

              <p className="text-base sm:text-lg text-slate-300 max-w-2xl leading-relaxed">
                Explore decades of Earth-science data, visualize environmental changes and discover how our planet is evolving through historical observations and scientific analysis.
              </p>

              <div className="flex flex-wrap items-center gap-4 pt-2">
                <Link
                  to="/explore"
                  className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-gradient-to-r from-accent-blue to-accent-cyan text-navy-950 font-bold text-sm hover:opacity-95 shadow-lg shadow-accent-blue/25 transition-all transform hover:-translate-y-0.5"
                >
                  <span>Start Exploring</span>
                  <ArrowRight className="w-4 h-4" />
                </Link>

                <a
                  href="#how-it-works"
                  className="inline-flex items-center gap-2 px-5 py-3 rounded-lg bg-navy-800/80 border border-slate-700 text-slate-200 text-sm font-medium hover:bg-navy-700 hover:text-white transition-colors"
                >
                  Learn More
                </a>
              </div>
            </div>

            {/* Right Earth visual (Desktop right, mobile stacked) */}
            <div className="lg:col-span-5 flex justify-center items-center">
              <div className="relative w-full max-w-md aspect-square rounded-full p-2 bg-gradient-to-tr from-accent-blue/30 via-cyan-500/10 to-transparent shadow-2xl shadow-cyan-950/40">
                <div className="w-full h-full rounded-full overflow-hidden relative border border-cyan-500/30 bg-navy-950 flex items-center justify-center group">
                  {/* Local Earth visual */}
                  <img
                    src={heroImage}
                    alt="Earth from space"
                    className="w-full h-full object-cover object-center filter brightness-95 contrast-105 transform group-hover:scale-105 transition-transform duration-700"
                  />
                  {/* Dark gradient overlay for readability */}
                  <div className="absolute inset-0 bg-gradient-to-t from-navy-950/70 via-transparent to-navy-950/30 pointer-events-none" />
                  <div className="absolute bottom-4 left-4 right-4 text-center">
                    <span className="text-[11px] font-mono tracking-wider text-cyan-200 bg-navy-900/80 px-2.5 py-1 rounded-md border border-cyan-500/30">
                      Global Gridded Climate Observations
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 4.3 What You Can Do Cards */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto space-y-3 mb-10">
          <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
            What You Can Do
          </h2>
          <p className="text-sm sm:text-base text-slate-400">
            A comprehensive, scientifically sound toolkit for investigating historical climate data.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {/* Card 1: Explore Data */}
          <Link
            to="/explore"
            className="group bg-navy-800/60 hover:bg-navy-800 border border-border-subtle hover:border-accent-blue/50 rounded-card p-6 space-y-4 transition-all duration-200 shadow-md flex flex-col justify-between"
          >
            <div className="space-y-3">
              <div className="w-10 h-10 rounded-lg bg-accent-blue/15 text-cyan-400 flex items-center justify-center group-hover:scale-110 transition-transform">
                <Layers className="w-5 h-5" />
              </div>
              <h3 className="text-lg font-bold text-slate-100 group-hover:text-cyan-300 transition-colors">
                Explore Data
              </h3>
              <p className="text-sm text-slate-300 leading-relaxed">
                Access historical environmental datasets from NASA and authoritative sources.
              </p>
            </div>
            <div className="flex items-center gap-1.5 text-xs font-semibold text-cyan-400 pt-2">
              <span>Open Data Explorer</span>
              <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
            </div>
          </Link>

          {/* Card 2: Analyse Trends */}
          <Link
            to="/explore"
            className="group bg-navy-800/60 hover:bg-navy-800 border border-border-subtle hover:border-accent-blue/50 rounded-card p-6 space-y-4 transition-all duration-200 shadow-md flex flex-col justify-between"
          >
            <div className="space-y-3">
              <div className="w-10 h-10 rounded-lg bg-accent-blue/15 text-cyan-400 flex items-center justify-center group-hover:scale-110 transition-transform">
                <TrendingUp className="w-5 h-5" />
              </div>
              <h3 className="text-lg font-bold text-slate-100 group-hover:text-cyan-300 transition-colors">
                Analyse Trends
              </h3>
              <p className="text-sm text-slate-300 leading-relaxed">
                Understand how environmental variables change over time.
              </p>
            </div>
            <div className="flex items-center gap-1.5 text-xs font-semibold text-cyan-400 pt-2">
              <span>Start Analysis</span>
              <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
            </div>
          </Link>

          {/* Card 3: Detect Changes */}
          <Link
            to="/explore"
            className="group bg-navy-800/60 hover:bg-navy-800 border border-border-subtle hover:border-accent-blue/50 rounded-card p-6 space-y-4 transition-all duration-200 shadow-md flex flex-col justify-between"
          >
            <div className="space-y-3">
              <div className="w-10 h-10 rounded-lg bg-accent-blue/15 text-cyan-400 flex items-center justify-center group-hover:scale-110 transition-transform">
                <Sparkles className="w-5 h-5" />
              </div>
              <h3 className="text-lg font-bold text-slate-100 group-hover:text-cyan-300 transition-colors">
                Detect Changes
              </h3>
              <p className="text-sm text-slate-300 leading-relaxed">
                Find geographical areas experiencing environmental changes.
              </p>
            </div>
            <div className="flex items-center gap-1.5 text-xs font-semibold text-cyan-400 pt-2">
              <span>Locate Shifts</span>
              <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
            </div>
          </Link>

          {/* Card 4: Generate Reports */}
          <Link
            to="/explore"
            className="group bg-navy-800/60 hover:bg-navy-800 border border-border-subtle hover:border-accent-blue/50 rounded-card p-6 space-y-4 transition-all duration-200 shadow-md flex flex-col justify-between"
          >
            <div className="space-y-3">
              <div className="w-10 h-10 rounded-lg bg-accent-blue/15 text-cyan-400 flex items-center justify-center group-hover:scale-110 transition-transform">
                <FileText className="w-5 h-5" />
              </div>
              <h3 className="text-lg font-bold text-slate-100 group-hover:text-cyan-300 transition-colors">
                Generate Reports
              </h3>
              <p className="text-sm text-slate-300 leading-relaxed">
                Validate findings and export research-ready reports.
              </p>
            </div>
            <div className="flex items-center gap-1.5 text-xs font-semibold text-cyan-400 pt-2">
              <span>Configure & Export</span>
              <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
            </div>
          </Link>
        </div>
      </section>

      {/* 4.4 How It Works Section (SPEC 4.4: 5-step horizontal workflow, vertical on mobile) */}
      <section id="how-it-works" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 scroll-mt-20">
        <div className="border border-border-subtle bg-navy-850/70 rounded-2xl p-6 sm:p-10 space-y-8">
          <div className="text-center max-w-2xl mx-auto space-y-2">
            <span className="text-xs font-mono uppercase tracking-wider text-cyan-400">Step-by-Step Methodology</span>
            <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">How It Works</h2>
            <p className="text-xs sm:text-sm text-slate-400">
              A disciplined, reproducible journey from raw observations to verified findings.
            </p>
          </div>

          {/* Desktop: Horizontal 5 steps */}
          <div className="hidden lg:grid grid-cols-5 gap-4 relative">
            {/* Connecting line */}
            <div className="absolute top-5 left-10 right-10 h-0.5 bg-gradient-to-r from-accent-blue/40 via-cyan-500/40 to-accent-blue/40 -z-0" />

            {/* Step 1 */}
            <div className="relative z-10 flex flex-col items-center text-center space-y-3">
              <div className="w-10 h-10 rounded-full bg-navy-950 border-2 border-accent-cyan text-cyan-300 font-bold text-sm flex items-center justify-center shadow-lg shadow-cyan-950">
                1
              </div>
              <h3 className="font-semibold text-slate-100 text-sm">Explore Data</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Select variable, inspect product metadata, and verify observation coverage.
              </p>
            </div>

            {/* Step 2 */}
            <div className="relative z-10 flex flex-col items-center text-center space-y-3">
              <div className="w-10 h-10 rounded-full bg-navy-950 border-2 border-accent-blue text-cyan-300 font-bold text-sm flex items-center justify-center shadow-lg shadow-cyan-950">
                2
              </div>
              <h3 className="font-semibold text-slate-100 text-sm">Select Geography</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Define regional boundaries using admin polygons, bounding boxes, or custom shapes.
              </p>
            </div>

            {/* Step 3 */}
            <div className="relative z-10 flex flex-col items-center text-center space-y-3">
              <div className="w-10 h-10 rounded-full bg-navy-950 border-2 border-accent-blue text-cyan-300 font-bold text-sm flex items-center justify-center shadow-lg shadow-cyan-950">
                3
              </div>
              <h3 className="font-semibold text-slate-100 text-sm">Analyse Trends</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Compute cosine-latitude area-weighted averages, Mann-Kendall tests, and Sen's slope.
              </p>
            </div>

            {/* Step 4 */}
            <div className="relative z-10 flex flex-col items-center text-center space-y-3">
              <div className="w-10 h-10 rounded-full bg-navy-950 border-2 border-accent-blue text-cyan-300 font-bold text-sm flex items-center justify-center shadow-lg shadow-cyan-950">
                4
              </div>
              <h3 className="font-semibold text-slate-100 text-sm">Detect Changes</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Generate spatial difference rasters comparing baseline vs recent observation epochs.
              </p>
            </div>

            {/* Step 5 */}
            <div className="relative z-10 flex flex-col items-center text-center space-y-3">
              <div className="w-10 h-10 rounded-full bg-navy-950 border-2 border-accent-blue text-cyan-300 font-bold text-sm flex items-center justify-center shadow-lg shadow-cyan-950">
                5
              </div>
              <h3 className="font-semibold text-slate-100 text-sm">Validate & Report</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Assess Benjamini-Hochberg FDR significance and compile a reproducible scientific report.
              </p>
            </div>
          </div>

          {/* Mobile: Vertical timeline */}
          <div className="lg:hidden space-y-6 relative pl-6 border-l-2 border-cyan-500/30 ml-2">
            <div className="relative space-y-1">
              <div className="absolute -left-[31px] top-0 w-6 h-6 rounded-full bg-navy-950 border-2 border-accent-cyan text-cyan-300 font-bold text-xs flex items-center justify-center">
                1
              </div>
              <h3 className="font-semibold text-slate-100 text-sm">1. Explore Data</h3>
              <p className="text-xs text-slate-400">
                Select variable, inspect product metadata, and verify observation coverage.
              </p>
            </div>

            <div className="relative space-y-1">
              <div className="absolute -left-[31px] top-0 w-6 h-6 rounded-full bg-navy-950 border-2 border-accent-blue text-cyan-300 font-bold text-xs flex items-center justify-center">
                2
              </div>
              <h3 className="font-semibold text-slate-100 text-sm">2. Select Geography</h3>
              <p className="text-xs text-slate-400">
                Define regional boundaries using admin polygons, bounding boxes, or custom shapes.
              </p>
            </div>

            <div className="relative space-y-1">
              <div className="absolute -left-[31px] top-0 w-6 h-6 rounded-full bg-navy-950 border-2 border-accent-blue text-cyan-300 font-bold text-xs flex items-center justify-center">
                3
              </div>
              <h3 className="font-semibold text-slate-100 text-sm">3. Analyse Trends</h3>
              <p className="text-xs text-slate-400">
                Compute cosine-latitude area-weighted averages, Mann-Kendall tests, and Sen's slope.
              </p>
            </div>

            <div className="relative space-y-1">
              <div className="absolute -left-[31px] top-0 w-6 h-6 rounded-full bg-navy-950 border-2 border-accent-blue text-cyan-300 font-bold text-xs flex items-center justify-center">
                4
              </div>
              <h3 className="font-semibold text-slate-100 text-sm">4. Detect Changes</h3>
              <p className="text-xs text-slate-400">
                Generate spatial difference rasters comparing baseline vs recent observation epochs.
              </p>
            </div>

            <div className="relative space-y-1">
              <div className="absolute -left-[31px] top-0 w-6 h-6 rounded-full bg-navy-950 border-2 border-accent-blue text-cyan-300 font-bold text-xs flex items-center justify-center">
                5
              </div>
              <h3 className="font-semibold text-slate-100 text-sm">5. Validate & Report</h3>
              <p className="text-xs text-slate-400">
                Assess Benjamini-Hochberg FDR significance and compile a reproducible scientific report.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* 4.5 Explore Earth-science Variables (SPEC: Shows ONLY variables returned by API) */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-8">
          <div>
            <div className="inline-flex items-center gap-1.5 text-xs font-mono text-cyan-400 uppercase tracking-wider mb-1">
              <Database className="w-3.5 h-3.5" />
              <span>Configured Observational Records</span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
              Curated Earth-Science Variables
            </h2>
          </div>
          <p className="text-xs sm:text-sm text-slate-400 max-w-md">
            Showing only variables validated and configured in the active application catalog.
          </p>
        </div>

        {/* Loading state */}
        {loading && (
          <div className="bg-navy-800/40 border border-border-subtle rounded-card p-12 text-center space-y-3">
            <Loader2 className="w-8 h-8 text-cyan-400 animate-spin mx-auto" />
            <p className="text-sm text-slate-300 font-medium">Loading variable catalog from server...</p>
            <p className="text-xs text-slate-500">Checking verified seed configurations</p>
          </div>
        )}

        {/* Error state */}
        {!loading && error && (
          <div className="bg-red-950/30 border border-red-800/40 rounded-card p-8 text-center space-y-4">
            <AlertCircle className="w-8 h-8 text-rose-400 mx-auto" />
            <div className="space-y-1">
              <h3 className="text-base font-bold text-rose-200">Unable to load catalog</h3>
              <p className="text-xs text-rose-300/80 font-mono">{error}</p>
            </div>
            <button
              type="button"
              onClick={loadVariables}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-md bg-navy-800 border border-slate-700 text-slate-200 text-xs font-medium hover:bg-navy-700"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Retry</span>
            </button>
          </div>
        )}

        {/* Empty state */}
        {!loading && !error && variables.length === 0 && (
          <div className="bg-navy-800/40 border border-border-subtle rounded-card p-10 text-center space-y-3">
            <Info className="w-8 h-8 text-slate-400 mx-auto" />
            <h3 className="text-base font-bold text-slate-200">No variables currently configured</h3>
            <p className="text-xs text-slate-400 max-w-sm mx-auto">
              The catalog does not contain any active variables yet.
            </p>
          </div>
        )}

        {/* Variables Cards Grid */}
        {!loading && !error && variables.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {variables.map((v) => {
              const defaultDs = v.datasets.find((d) => d.id === v.default_dataset_id) || v.datasets[0];
              return (
                <div
                  key={v.id}
                  className="bg-navy-850 border border-border-subtle hover:border-accent-blue/50 rounded-card p-6 space-y-5 transition-all shadow-md flex flex-col justify-between"
                >
                  <div className="space-y-4">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[11px] font-mono px-2.5 py-0.5 rounded-full bg-accent-blue/15 text-cyan-300 border border-accent-blue/30">
                        {v.category}
                      </span>
                      <StatusChip status="Available" />
                    </div>

                    <div>
                      <h3 className="text-xl font-bold text-white tracking-tight">{v.name}</h3>
                      <p className="text-xs text-slate-300 mt-1 line-clamp-2 leading-relaxed">
                        {v.description}
                      </p>
                    </div>

                    {defaultDs && (
                      <div className="bg-navy-900/80 rounded-lg p-3 border border-border-subtle/80 space-y-2 text-xs">
                        <div className="flex justify-between text-slate-400">
                          <span>Primary Product:</span>
                          <span className="text-slate-200 font-semibold">{defaultDs.version}</span>
                        </div>
                        <div className="text-[11px] text-slate-400 truncate">
                          {defaultDs.product_name}
                        </div>
                        <div className="grid grid-cols-2 gap-2 pt-1 border-t border-border-subtle/50 text-[11px] text-slate-400">
                          <div>
                            <span className="text-slate-500">Native Units: </span>
                            <span className="font-mono text-cyan-300">{defaultDs.units}</span>
                          </div>
                          <div>
                            <span className="text-slate-500">Grid: </span>
                            <span className="font-mono text-slate-300">{defaultDs.spatial_resolution}</span>
                          </div>
                        </div>
                      </div>
                    )}

                    <div className="space-y-1">
                      <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                        What can we discover?
                      </span>
                      <p className="text-xs text-slate-300 italic bg-navy-900/40 p-2.5 rounded border border-border-subtle/60">
                        "{v.scientific_question}"
                      </p>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => handleSelectVariable(v)}
                    className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-navy-800 hover:bg-accent-blue/20 hover:border-accent-blue/40 border border-slate-700 text-cyan-300 text-xs font-semibold transition-all cursor-pointer"
                  >
                    <span>Configure in Data Explorer</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* 4.6 Final CTA */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-navy-900 via-navy-850 to-navy-900 border border-accent-blue/30 p-8 sm:p-12 text-center space-y-6 shadow-xl">
          <div className="max-w-2xl mx-auto space-y-3">
            <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
              Discover the Story Behind Earth's Data.
            </h2>
            <p className="text-sm sm:text-base text-slate-300">
              Start by choosing an Earth-science variable, specifying your historical time window, and selecting your target region.
            </p>
          </div>

          <Link
            to="/explore"
            className="inline-flex items-center gap-2 px-7 py-3.5 rounded-lg bg-gradient-to-r from-accent-blue to-accent-cyan text-navy-950 font-bold text-sm hover:opacity-95 shadow-lg shadow-accent-blue/25 transition-all transform hover:-translate-y-0.5"
          >
            <span>Begin Your Analysis</span>
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </section>

      {/* 4.6 Footer */}
      <footer className="border-t border-border-subtle bg-navy-950/80 pt-12 pb-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8" id="about">
            <div className="md:col-span-2 space-y-3">
              <div className="text-lg font-bold text-white tracking-tight">Gaia Insights</div>
              <p className="text-xs text-slate-400 leading-relaxed max-w-sm">
                A scientific platform dedicated to historical climate exploration, trend detection, and rigorous area-weighted statistical analysis.
              </p>
              <div className="text-[11px] text-cyan-400 font-mono">
                Gaia Insights • NASA & NOAA Observational Records
              </div>
            </div>

            <div className="space-y-2" id="data-sources">
              <h4 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">Data Sources</h4>
              <ul className="text-xs text-slate-400 space-y-1.5">
                <li>NOAA PSL (Physical Sciences Laboratory)</li>
                <li>NASA Earth Science Division</li>
                <li>Global Precipitation Climatology Project (GPCP)</li>
              </ul>
            </div>

            <div className="space-y-2">
              <h4 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">Methodology</h4>
              <ul className="text-xs text-slate-400 space-y-1.5">
                <li>Cosine Latitude Area Weighting</li>
                <li>Mann-Kendall Trend Testing</li>
                <li>Benjamini-Hochberg FDR Control</li>
              </ul>
            </div>
          </div>

          {/* Attribution and coverage-limitations note */}
          <div className="border-t border-border-subtle/60 pt-6 space-y-2 text-xs text-slate-400">
            <p>
              <span className="font-semibold text-slate-300">Data Attribution: </span>
              Data provided by NOAA Physical Sciences Laboratory, Boulder, Colorado, USA (psl.noaa.gov).
            </p>
            <p className="text-[11px] text-slate-500 leading-relaxed">
              <span className="font-semibold text-slate-400">Notice & Limitations: </span>
              Analysis is subject to dataset coverage and limitations. Historical satellite and observational records have varying spatial resolution, sensor calibration changes, and observation latency. Unchecked or incomplete observational windows are not fabricated or filled silently.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
};
