import React, { useState, useEffect, useCallback, useId } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import type { Geometry } from 'geojson';
import {
  Search,
  MapPin,
  Hexagon,
  Square,
  CircleDot,
  Layers,
  AlertTriangle,
  CheckCircle2,
  ArrowRight,
  RotateCcw,
  Info,
  Globe2,
} from 'lucide-react';

import { useSession, type AnalysisRegion } from '../store/session';
import { formatObservationDate, formatCatalogueCheck } from '../api/catalog';
import { StatusChip } from '../components/StatusChip';
import { GeographicMap } from '../components/map/GeographicMap';
import {
  searchRegions,
  fetchRegionGeometry,
  validateRegion,
  type RegionSearchResult,
  type RegionValidateResponse,
} from '../api/regions';
import {
  fetchDatasetAvailability,
  type DatasetAvailabilityResponse,
} from '../api/availability';

export type RegionSelectionMode = 'admin' | 'polygon' | 'rectangle' | 'point_buffer';

export const RegionPage: React.FC = () => {
  const navigate = useNavigate();
  const searchInputId = useId();
  const selectedVariables = useSession((s) => s.selectedVariables);
  const dateRange = useSession((s) => s.dateRange);
  const frequency = useSession((s) => s.frequency);
  const sessionRegion = useSession((s) => s.region);
  const setSessionRegion = useSession((s) => s.setRegion);

  const primaryVar = selectedVariables[0];

  // UI Mode & Selection State
  const [mode, setMode] = useState<RegionSelectionMode>(
    sessionRegion ? sessionRegion.type : 'admin'
  );

  // Administrative Search
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<RegionSearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [selectedAdminResult, setSelectedAdminResult] = useState<RegionSearchResult | null>(null);

  // Point + Buffer state
  const [pointCenter, setPointCenter] = useState<[number, number]>([0, 20]);
  const [bufferRadiusKm, setBufferRadiusKm] = useState<number>(50);

  // Active / Draft Geometry
  const [draftGeometry, setDraftGeometry] = useState<Geometry | null>(
    sessionRegion ? sessionRegion.geometry : null
  );
  const [draftLabel, setDraftLabel] = useState<string>(
    sessionRegion ? sessionRegion.label : ''
  );

  // Validation & Availability Data
  const [validationResult, setValidationResult] = useState<RegionValidateResponse | null>(null);
  const [isValidating, setIsValidating] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  const [availabilities, setAvailabilities] = useState<Record<string, DatasetAvailabilityResponse>>({});
  const [isLoadingAvailability, setIsLoadingAvailability] = useState(false);

  // Search Debounce Effect
  useEffect(() => {
    if (mode !== 'admin') return;
    if (!searchQuery.trim()) {
      setSearchResults([]);
      return;
    }

    const timer = setTimeout(async () => {
      setIsSearching(true);
      try {
        const results = await searchRegions(searchQuery, 15);
        setSearchResults(results);
      } catch (err) {
        console.error('Region search error:', err);
      } finally {
        setIsSearching(false);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [searchQuery, mode]);

  // Handle Admin Boundary Selection
  const handleSelectAdminBoundary = async (result: RegionSearchResult) => {
    setSelectedAdminResult(result);
    setSearchQuery(result.name);
    setSearchResults([]);
    setValidationError(null);

    try {
      setIsValidating(true);
      const geomData = await fetchRegionGeometry(result.id);
      setDraftGeometry(geomData.geometry);
      setDraftLabel(
        result.country && result.type === 'admin-1'
          ? `${result.name}, ${result.country}`
          : result.name
      );

      // Validate geometry with backend API
      const valRes = await validateRegion({
        geometry: geomData.geometry,
        crs: geomData.crs || 'EPSG:4326',
        label: result.name,
        type: 'admin',
      });
      setValidationResult(valRes);
    } catch (err: any) {
      setValidationError(err.message || 'Failed to load administrative boundary.');
    } finally {
      setIsValidating(false);
    }
  };

  // Handle Hand-drawn Geometry from Map
  const handleGeometryDrawn = async (geom: Geometry) => {
    setDraftGeometry(geom);
    setValidationError(null);
    const label = mode === 'rectangle' ? 'Custom Rectangle' : 'Custom Polygon';
    setDraftLabel(label);

    try {
      setIsValidating(true);
      const valRes = await validateRegion({
        geometry: geom,
        crs: 'EPSG:4326',
        type: mode,
        label,
      });
      setValidationResult(valRes);
    } catch (err: any) {
      setValidationError(err.message || 'Geometry validation failed.');
    } finally {
      setIsValidating(false);
    }
  };

  // Handle Point Clicked on Map for Point + Buffer mode
  const handlePointClicked = async (coords: [number, number]) => {
    setPointCenter(coords);
    if (mode === 'point_buffer') {
      await validateBuffer(coords, bufferRadiusKm);
    }
  };

  const validateBuffer = async (coords: [number, number], radiusKm: number) => {
    setValidationError(null);
    const label = `${radiusKm} km Buffer at (${coords[0].toFixed(2)}°, ${coords[1].toFixed(2)}°)`;
    setDraftLabel(label);

    try {
      setIsValidating(true);
      const valRes = await validateRegion({
        point: coords,
        radius_km: radiusKm,
        crs: 'EPSG:4326',
        type: 'point_buffer',
        label,
      });
      setDraftGeometry(valRes.geometry);
      setValidationResult(valRes);
    } catch (err: any) {
      setValidationError(err.message || 'Failed to generate geodesic buffer.');
    } finally {
      setIsValidating(false);
    }
  };

  // Check Availability for all selected variables
  const checkAvailabilityForRegion = useCallback(
    async (geom: Geometry | null, bbox?: [number, number, number, number]) => {
      if (!selectedVariables.length) return;
      setIsLoadingAvailability(true);
      const newAvails: Record<string, DatasetAvailabilityResponse> = {};

      try {
        for (const v of selectedVariables) {
          const res = await fetchDatasetAvailability(v.datasetId, {
            geometry: geom,
            bbox,
            start: dateRange.start,
            end: dateRange.endMode === 'custom' ? dateRange.end : undefined,
          });
          newAvails[v.datasetId] = res;
        }
        setAvailabilities(newAvails);
      } catch (err) {
        console.error('Availability check error:', err);
      } finally {
        setIsLoadingAvailability(false);
      }
    },
    [selectedVariables, dateRange]
  );

  // When validation result updates, evaluate dataset availability
  useEffect(() => {
    if (validationResult && validationResult.geometry) {
      checkAvailabilityForRegion(validationResult.geometry, validationResult.bbox);
    }
  }, [validationResult, checkAvailabilityForRegion]);

  // If sessionRegion already existed on mount, load its validation info
  useEffect(() => {
    if (sessionRegion && sessionRegion.geometry && !validationResult) {
      validateRegion({
        geometry: sessionRegion.geometry,
        crs: sessionRegion.crs,
        label: sessionRegion.label,
        type: sessionRegion.type,
      })
        .then((res) => {
          setValidationResult(res);
          setDraftGeometry(res.geometry);
        })
        .catch(console.error);
    }
  }, []);

  // Confirm Region Action: Persist in Zustand session store
  const handleConfirmRegion = () => {
    if (!validationResult) return;

    const confirmedRegion: AnalysisRegion = {
      label: draftLabel || 'Selected Region',
      type: mode,
      geometry: validationResult.geometry,
      crs: validationResult.crs,
      areaKm2: validationResult.area_km2,
      bbox: validationResult.bbox,
      centroid: validationResult.centroid,
      warnings: validationResult.warnings,
    };

    setSessionRegion(confirmedRegion);
  };

  // Clear Region
  const handleClearRegion = () => {
    setSessionRegion(null);
    setDraftGeometry(null);
    setValidationResult(null);
    setSelectedAdminResult(null);
    setSearchQuery('');
    setAvailabilities({});
  };

  const isConfirmed =
    sessionRegion &&
    validationResult &&
    sessionRegion.label === draftLabel &&
    sessionRegion.areaKm2 === validationResult.area_km2;

  // Combine warnings from geometry validation and dataset availability
  const combinedWarnings = [
    ...(validationResult?.warnings || []),
    ...Object.values(availabilities).flatMap((a) => a.warnings || []),
  ];
  // Deduplicate warnings
  const uniqueWarnings = Array.from(new Set(combinedWarnings));

  return (
    <div className="space-y-6">
      {/* Header & Page Subtitle */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border-subtle pb-5">
        <div>
          <div className="flex items-center gap-2 text-cyan-400 font-mono text-xs tracking-wider uppercase mb-1">
            <Globe2 className="w-4 h-4" />
            <span>Page 2 / Step 2</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
            Page 2: Geographic Explorer
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Define your spatial region of study via administrative boundaries, custom polygons,
            rectangles, or geodesic buffers.
          </p>
        </div>

        {/* Global Action: Proceed to Trends */}
        <div className="flex items-center gap-3">
          {sessionRegion && (
            <button
              type="button"
              onClick={handleClearRegion}
              className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-slate-400 hover:text-white bg-navy-800 hover:bg-navy-700 border border-border-subtle rounded-lg transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Reset Region
            </button>
          )}

          <button
            type="button"
            disabled={!sessionRegion}
            onClick={() => navigate('/trends')}
            className={`flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-lg shadow-card transition-all ${
              sessionRegion
                ? 'bg-cyan-500 hover:bg-cyan-400 text-navy-950 font-bold'
                : 'bg-navy-800 text-slate-500 border border-border-subtle cursor-not-allowed'
            }`}
          >
            <span>3. Trend Analysis</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Main 3-Column Layout: Left (23%) / Centre (52%) / Right (25%) */}
      <div className="flex flex-col lg:flex-row gap-5 items-start">
        {/* ========================================================================= */}
        {/* LEFT COLUMN: Region Selection & Mode Controls (23% width on desktop)      */}
        {/* ========================================================================= */}
        <div className="w-full lg:w-[23%] shrink-0 space-y-4">
          {/* Mode Selector Card */}
          <div className="bg-navy-850 border border-border-subtle rounded-card p-4 shadow-card space-y-3">
            <h2 className="text-xs font-mono font-bold text-cyan-300 uppercase tracking-wider">
              Selection Mode
            </h2>

            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setMode('admin')}
                className={`flex flex-col items-center justify-center gap-1 p-2.5 rounded-lg border text-xs font-medium transition-all ${
                  mode === 'admin'
                    ? 'bg-cyan-500/15 border-cyan-500/60 text-cyan-300 shadow-sm'
                    : 'bg-navy-800/80 border-border-subtle text-slate-400 hover:bg-navy-800 hover:text-white'
                }`}
              >
                <MapPin className="w-4 h-4 text-cyan-400" />
                <span>Admin Boundary</span>
              </button>

              <button
                type="button"
                onClick={() => setMode('polygon')}
                className={`flex flex-col items-center justify-center gap-1 p-2.5 rounded-lg border text-xs font-medium transition-all ${
                  mode === 'polygon'
                    ? 'bg-cyan-500/15 border-cyan-500/60 text-cyan-300 shadow-sm'
                    : 'bg-navy-800/80 border-border-subtle text-slate-400 hover:bg-navy-800 hover:text-white'
                }`}
              >
                <Hexagon className="w-4 h-4 text-cyan-400" />
                <span>Draw Polygon</span>
              </button>

              <button
                type="button"
                onClick={() => setMode('rectangle')}
                className={`flex flex-col items-center justify-center gap-1 p-2.5 rounded-lg border text-xs font-medium transition-all ${
                  mode === 'rectangle'
                    ? 'bg-cyan-500/15 border-cyan-500/60 text-cyan-300 shadow-sm'
                    : 'bg-navy-800/80 border-border-subtle text-slate-400 hover:bg-navy-800 hover:text-white'
                }`}
              >
                <Square className="w-4 h-4 text-cyan-400" />
                <span>Draw Rectangle</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  setMode('point_buffer');
                  validateBuffer(pointCenter, bufferRadiusKm);
                }}
                className={`flex flex-col items-center justify-center gap-1 p-2.5 rounded-lg border text-xs font-medium transition-all ${
                  mode === 'point_buffer'
                    ? 'bg-cyan-500/15 border-cyan-500/60 text-cyan-300 shadow-sm'
                    : 'bg-navy-800/80 border-border-subtle text-slate-400 hover:bg-navy-800 hover:text-white'
                }`}
              >
                <CircleDot className="w-4 h-4 text-cyan-400" />
                <span>Point + Buffer</span>
              </button>
            </div>
          </div>

          {/* Mode Controls Content */}
          <div className="bg-navy-850 border border-border-subtle rounded-card p-4 shadow-card space-y-4">
            {mode === 'admin' && (
              <div className="space-y-3">
                <label
                  htmlFor={searchInputId}
                  className="text-xs font-semibold text-slate-300 flex items-center gap-1.5"
                >
                  <Search className="w-3.5 h-3.5 text-cyan-400" />
                  Search Countries & States
                </label>
                <div className="relative">
                  <input
                    id={searchInputId}
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search place name (e.g. Fiji, France, California)..."
                    className="w-full bg-navy-900 border border-border-subtle rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400"
                  />
                  {isSearching && (
                    <div className="absolute right-3 top-2.5">
                      <div className="w-3.5 h-3.5 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
                    </div>
                  )}
                </div>

                {/* Dropdown Results */}
                {searchResults.length > 0 && (
                  <div className="bg-navy-900 border border-border-subtle rounded-lg max-h-56 overflow-y-auto divide-y divide-border-subtle/40 shadow-elevated">
                    {searchResults.map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => handleSelectAdminBoundary(item)}
                        className="w-full text-left p-2.5 hover:bg-navy-800 transition-colors flex items-center justify-between text-xs"
                      >
                        <div>
                          <div className="font-semibold text-white">{item.name}</div>
                          <div className="text-[11px] text-slate-400">
                            {item.country && item.type === 'admin-1' ? `${item.country} · ` : ''}
                            {item.subtype || item.type}
                          </div>
                        </div>
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-navy-800 text-slate-400 border border-border-subtle">
                          {item.iso_a3 || item.type}
                        </span>
                      </button>
                    ))}
                  </div>
                )}

                {/* Selected Resolved Feature Preview */}
                {selectedAdminResult && (
                  <div className="bg-navy-900/80 border border-cyan-500/30 rounded-lg p-3 space-y-2 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="text-slate-400 text-[11px]">Resolved Feature:</span>
                      <span className="font-mono text-[10px] text-cyan-300 px-1.5 py-0.2 rounded bg-cyan-950/60 border border-cyan-500/30">
                        {selectedAdminResult.type}
                      </span>
                    </div>
                    <div className="font-bold text-white text-sm">{selectedAdminResult.name}</div>
                    {selectedAdminResult.country && (
                      <div className="text-slate-400 text-xs">
                        Country: <span className="text-slate-200">{selectedAdminResult.country}</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {mode === 'polygon' && (
              <div className="space-y-3 text-xs text-slate-300">
                <div className="p-3 bg-navy-900/80 border border-border-subtle rounded-lg space-y-1.5">
                  <span className="font-bold text-cyan-300 block">Digitize Custom Polygon</span>
                  <p className="text-slate-400 text-[11px] leading-relaxed">
                    Click anywhere on the map to place vertices. Double-click or click the first
                    vertex to close the shape. Use &quot;Edit Vertices&quot; on the map to adjust.
                  </p>
                </div>
                {draftGeometry && (
                  <div className="p-2.5 bg-navy-900 border border-cyan-500/30 rounded-lg text-[11px] font-mono text-cyan-300">
                    Geometry digitized: {draftGeometry.type}
                  </div>
                )}
              </div>
            )}

            {mode === 'rectangle' && (
              <div className="space-y-3 text-xs text-slate-300">
                <div className="p-3 bg-navy-900/80 border border-border-subtle rounded-lg space-y-1.5">
                  <span className="font-bold text-cyan-300 block">Draw Bounding Rectangle</span>
                  <p className="text-slate-400 text-[11px] leading-relaxed">
                    Click and drag across the map to define a bounding box study area.
                  </p>
                </div>
                {draftGeometry && (
                  <div className="p-2.5 bg-navy-900 border border-cyan-500/30 rounded-lg text-[11px] font-mono text-cyan-300">
                    Bounding Box defined
                  </div>
                )}
              </div>
            )}

            {mode === 'point_buffer' && (
              <div className="space-y-3 text-xs text-slate-300">
                <div className="p-3 bg-navy-900/80 border border-border-subtle rounded-lg space-y-1.5">
                  <span className="font-bold text-cyan-300 block">Geodesic Point + Buffer</span>
                  <p className="text-slate-400 text-[11px] leading-relaxed">
                    Click anywhere on the map to set the center point, or type exact coordinates
                    below. The backend generates an accurate geodesic circle on the WGS84 ellipsoid.
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-[11px] text-slate-400 block mb-1">Center Longitude</label>
                    <input
                      type="number"
                      step="0.01"
                      value={pointCenter[0]}
                      onChange={(e) => {
                        const lon = parseFloat(e.target.value) || 0;
                        const newCoords: [number, number] = [lon, pointCenter[1]];
                        setPointCenter(newCoords);
                        validateBuffer(newCoords, bufferRadiusKm);
                      }}
                      className="w-full bg-navy-900 border border-border-subtle rounded px-2.5 py-1.5 text-xs text-white"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] text-slate-400 block mb-1">Center Latitude</label>
                    <input
                      type="number"
                      step="0.01"
                      value={pointCenter[1]}
                      onChange={(e) => {
                        const lat = parseFloat(e.target.value) || 0;
                        const newCoords: [number, number] = [pointCenter[0], lat];
                        setPointCenter(newCoords);
                        validateBuffer(newCoords, bufferRadiusKm);
                      }}
                      className="w-full bg-navy-900 border border-border-subtle rounded px-2.5 py-1.5 text-xs text-white"
                    />
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1">
                    <span>Radius: {bufferRadiusKm} km</span>
                    <span className="font-mono text-cyan-400">
                      ~{(Math.PI * bufferRadiusKm * bufferRadiusKm).toLocaleString(undefined, { maximumFractionDigits: 0 })} km²
                    </span>
                  </div>
                  <input
                    type="range"
                    min="10"
                    max="1000"
                    step="10"
                    value={bufferRadiusKm}
                    onChange={(e) => {
                      const r = parseInt(e.target.value, 10);
                      setBufferRadiusKm(r);
                      validateBuffer(pointCenter, r);
                    }}
                    className="w-full accent-cyan-400"
                  />
                </div>
              </div>
            )}

            {/* Validation Error Message if any */}
            {validationError && (
              <div className="p-2.5 bg-rose-950/40 border border-rose-500/40 rounded-lg text-rose-300 text-xs flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400 mt-0.5" />
                <span>{validationError}</span>
              </div>
            )}

            {/* Confirm Region Action Button */}
            {(() => {
              const hasUnavailableDataset = Object.values(availabilities).some((a) => a.status.startsWith('Unavailable'));
              return (
                <button
                  type="button"
                  disabled={!validationResult || isValidating || hasUnavailableDataset}
                  onClick={handleConfirmRegion}
                  className={`w-full py-2.5 px-3 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-2 ${
                    isConfirmed
                      ? 'bg-emerald-950/60 border border-emerald-500/50 text-emerald-300'
                      : hasUnavailableDataset
                      ? 'bg-navy-800 text-slate-500 border border-border-subtle cursor-not-allowed'
                      : validationResult
                      ? 'bg-cyan-500 hover:bg-cyan-400 text-navy-950 shadow-card'
                      : 'bg-navy-800 text-slate-500 border border-border-subtle cursor-not-allowed'
                  }`}
                >
                  {isConfirmed ? (
                    <>
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      <span>Region Confirmed & Stored</span>
                    </>
                  ) : hasUnavailableDataset ? (
                    <span>Selected Dataset Unavailable</span>
                  ) : isValidating ? (
                    <>
                      <div className="w-3.5 h-3.5 border-2 border-navy-950 border-t-transparent rounded-full animate-spin" />
                      <span>Validating Geometry...</span>
                    </>
                  ) : (
                    <>
                      <MapPin className="w-4 h-4" />
                      <span>Confirm Selected Region</span>
                    </>
                  )}
                </button>
              );
            })()}
          </div>

          {/* Active Selection from Page 1 (SPEC 7.1) */}
          <div className="bg-navy-850 border border-border-subtle rounded-card p-4 shadow-card space-y-2 text-xs">
            <div className="flex items-center justify-between border-b border-border-subtle/60 pb-2">
              <span className="font-mono font-bold text-slate-400 text-[11px] uppercase tracking-wider flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-cyan-400" />
                Persisted Selection from Page 1
              </span>
              <Link
                to="/explore"
                className="text-[11px] text-cyan-400 hover:text-cyan-300 underline"
              >
                Change
              </Link>
            </div>

            {primaryVar ? (
              <div className="space-y-1.5 pt-1">
                <div className="flex justify-between">
                  <span className="text-slate-400">Variable:</span>
                  <span className="font-semibold text-white capitalize">{primaryVar.variableId}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Dataset:</span>
                  <span className="font-mono text-cyan-300">{primaryVar.datasetId}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Version:</span>
                  <span className="font-mono text-slate-300">{primaryVar.datasetVersion}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Baseline Start:</span>
                  <span className="font-mono text-slate-300">{dateRange.start}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Frequency & Units:</span>
                  <span className="font-mono text-slate-300 capitalize">
                    {frequency} ({primaryVar.units})
                  </span>
                </div>

                {primaryVar.caveat && (
                  <div className="mt-2 pt-2 border-t border-border-subtle/50 text-[11px] text-amber-200/90 bg-amber-950/20 p-2 rounded border border-amber-600/30 space-y-1">
                    <div className="flex items-center gap-1 font-semibold text-amber-400 text-[10.5px]">
                      <AlertTriangle className="w-3 h-3 shrink-0" />
                      <span>Scientific Caveat</span>
                    </div>
                    <p className="text-[10px] leading-relaxed text-amber-200/80">
                      {primaryVar.caveat}
                    </p>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-slate-400 italic text-[11px] py-1">
                No variable configured yet. Please select one on Page 1.
              </p>
            )}
          </div>
        </div>

        {/* ========================================================================= */}
        {/* CENTRE COLUMN: Interactive Leaflet Map (52% width on desktop)             */}
        {/* ========================================================================= */}
        <div className="w-full lg:w-[52%] flex-1">
          <GeographicMap
            geometry={draftGeometry}
            drawMode={mode}
            onGeometryDrawn={handleGeometryDrawn}
            onPointClicked={handlePointClicked}
            className="w-full"
          />
        </div>

        {/* ========================================================================= */}
        {/* RIGHT COLUMN: Region Details & Availability Panel (25% width on desktop)  */}
        {/* ========================================================================= */}
        <div className="w-full lg:w-[25%] shrink-0 space-y-4">
          {/* Region Metadata Card */}
          <div className="bg-navy-850 border border-border-subtle rounded-card p-4 shadow-card space-y-3">
            <div className="flex items-center justify-between border-b border-border-subtle/60 pb-2">
              <h2 className="text-xs font-mono font-bold text-cyan-300 uppercase tracking-wider">
                Region Details
              </h2>
              {sessionRegion ? (
                <span className="text-[10px] font-mono font-bold text-emerald-400 bg-emerald-950/60 border border-emerald-500/40 px-2 py-0.5 rounded">
                  Stored
                </span>
              ) : (
                <span className="text-[10px] font-mono text-slate-400 bg-navy-800 border border-border-subtle px-2 py-0.5 rounded">
                  Unsaved
                </span>
              )}
            </div>

            {validationResult ? (
              <div className="space-y-3 text-xs">
                <div>
                  <span className="text-slate-400 block text-[11px]">Region Name</span>
                  <span className="font-bold text-white text-sm">{draftLabel}</span>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div className="p-2 bg-navy-900 border border-border-subtle/60 rounded-lg">
                    <span className="text-slate-500 block text-[10px] uppercase font-mono">Type</span>
                    <span className="font-semibold text-slate-200 capitalize">
                      {mode.replace('_', ' ')}
                    </span>
                  </div>
                  <div className="p-2 bg-navy-900 border border-border-subtle/60 rounded-lg">
                    <span className="text-slate-500 block text-[10px] uppercase font-mono">Geodesic Area</span>
                    <span className="font-mono font-bold text-cyan-300">
                      {validationResult.area_km2.toLocaleString(undefined, {
                        maximumFractionDigits: 1,
                      })}{' '}
                      km²
                    </span>
                  </div>
                </div>

                <div className="space-y-1">
                  <span className="text-slate-400 block text-[11px]">Bounding Box (WGS84)</span>
                  <div className="font-mono text-[11px] text-slate-300 bg-navy-900 p-2 rounded border border-border-subtle/60 break-all">
                    [{validationResult.bbox.join(', ')}]
                  </div>
                </div>

                <div className="space-y-1">
                  <span className="text-slate-400 block text-[11px]">Centroid (Lon, Lat)</span>
                  <div className="font-mono text-[11px] text-slate-300 bg-navy-900 p-2 rounded border border-border-subtle/60">
                    [{validationResult.centroid[0].toFixed(4)}°, {validationResult.centroid[1].toFixed(4)}°]
                  </div>
                </div>
              </div>
            ) : (
              <div className="py-6 text-center text-xs text-slate-500 italic space-y-1">
                <Info className="w-5 h-5 mx-auto text-slate-600 mb-1" />
                <p>No region currently selected or drawn.</p>
                <p className="text-[11px]">Choose an administrative boundary or draw on the map.</p>
              </div>
            )}
          </div>

          {/* Dataset Availability Card per Variable (SPEC 7.4) */}
          <div className="bg-navy-850 border border-border-subtle rounded-card p-4 shadow-card space-y-3">
            <div className="flex items-center justify-between border-b border-border-subtle/60 pb-2">
              <h2 className="text-xs font-mono font-bold text-cyan-300 uppercase tracking-wider">
                Dataset Availability
              </h2>
              {isLoadingAvailability && (
                <div className="w-3.5 h-3.5 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
              )}
            </div>

            {selectedVariables.length > 0 ? (
              <div className="space-y-3">
                {selectedVariables.map((v) => {
                  const avail = availabilities[v.datasetId];
                  return (
                    <div
                      key={v.datasetId}
                      className="p-3 bg-navy-900 border border-border-subtle/80 rounded-lg space-y-2 text-xs"
                    >
                      <div className="flex items-center justify-between">
                        <div className="font-semibold text-white capitalize">{v.variableId}</div>
                        {avail ? (
                          <StatusChip status={avail.status as any} />
                        ) : (
                          <StatusChip status="Loading" />
                        )}
                      </div>

                      <div className="text-[11px] font-mono text-cyan-300">
                        {v.datasetId} (v{v.datasetVersion})
                      </div>

                      {avail && (
                        <div className="space-y-1.5 pt-1 border-t border-border-subtle/40 text-[11px]">
                          <div className="flex justify-between">
                            <span className="text-slate-400">Spatial Grid:</span>
                            <span className="font-mono text-slate-200">{avail.spatial_resolution}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-slate-400">Grid Cell Centres:</span>
                            <span className="font-mono text-cyan-300 font-bold">
                              {avail.cell_count} valid centre{avail.cell_count === 1 ? '' : 's'}
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-slate-400">Date Coverage:</span>
                            <span className="font-mono text-slate-200">
                              {avail.valid_date_range.start} → {avail.valid_date_range.latest_observation_date ? formatObservationDate(avail.valid_date_range.latest_observation_date) : 'Latest complete'}
                            </span>
                          </div>
                          {avail.valid_date_range.last_catalogue_check && (
                            <div className="flex justify-between text-[10px] text-slate-500 pt-0.5">
                              <span>Last catalogue check:</span>
                              <span className="font-mono">{formatCatalogueCheck(avail.valid_date_range.last_catalogue_check)}</span>
                            </div>
                          )}

                          {v.caveat && (
                            <div className="mt-1.5 p-1.5 rounded bg-amber-950/20 border border-amber-600/30 text-[10px] text-amber-200/90 leading-snug">
                              <span className="font-semibold text-amber-400 block mb-0.5">Caveat:</span>
                              <span>{v.caveat}</span>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-xs text-slate-500 italic">No variables selected from Page 1.</p>
            )}
          </div>

          {/* Scientific Warnings Card (SPEC 7.4) */}
          {uniqueWarnings.length > 0 && (
            <div className="bg-amber-950/20 border border-amber-600/40 rounded-card p-4 shadow-card space-y-2">
              <div className="flex items-center gap-1.5 text-amber-400 text-xs font-bold uppercase font-mono tracking-wider">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>Scientific Warnings</span>
              </div>
              <ul className="space-y-1.5 text-xs text-amber-200/90 list-disc list-inside">
                {uniqueWarnings.map((warn, i) => (
                  <li key={i} className="text-[11px] leading-relaxed">
                    {warn}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
