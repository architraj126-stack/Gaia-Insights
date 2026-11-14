import React, { useEffect, useRef, useState, useCallback } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { Geometry } from 'geojson';
import {
  Download,
  Eye,
  FileImage,
  Maximize2,
  Minimize2,
  RotateCcw,
  ZoomIn,
  ZoomOut,
  MapPin,
  X,
  AlertCircle,
  CheckCircle2,
} from 'lucide-react';
import {
  inspectChangeCell,
  type CellInspectResult,
  type ChangeMapLegend,
} from '../../api/change';

export type BaseMapType = 'street' | 'satellite' | 'terrain';

const BASE_MAPS: Record<BaseMapType, { name: string; url: string; attribution: string }> = {
  street: {
    name: 'Street',
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  },
  satellite: {
    name: 'Satellite',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Tiles &copy; Esri, Earthstar Geographics',
  },
  terrain: {
    name: 'Terrain',
    url: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
    attribution: 'Map &copy; OpenTopoMap contributors',
  },
};

export interface ChangeMapViewerProps {
  runId?: string;
  overlayUrl?: string;
  geotiffUrl?: string;
  bounds?: [[number, number], [number, number]];
  legend?: ChangeMapLegend;
  geometry?: Geometry | null;
  units?: string;
  metric?: string;
  className?: string;
}

export const ChangeMapViewer: React.FC<ChangeMapViewerProps> = ({
  runId,
  overlayUrl,
  geotiffUrl,
  bounds,
  legend,
  geometry,
  className = '',
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const baseTileLayerRef = useRef<L.TileLayer | null>(null);
  const geojsonLayerRef = useRef<L.GeoJSON | null>(null);
  const imageOverlayRef = useRef<L.ImageOverlay | null>(null);
  const inspectMarkerRef = useRef<L.CircleMarker | null>(null);
  const runIdRef = useRef<string | undefined>(runId);
  runIdRef.current = runId;

  const [baseMap, setBaseMap] = useState<BaseMapType>('street');
  const [opacity, setOpacity] = useState<number>(0.85);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [inspectData, setInspectData] = useState<CellInspectResult | null>(null);
  const [inspecting, setInspecting] = useState(false);
  const [inspectError, setInspectError] = useState<string | null>(null);

  // Initialize Map
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = L.map(containerRef.current, {
      center: [20, 0],
      zoom: 2,
      minZoom: 1,
      maxZoom: 18,
      zoomControl: false,
      attributionControl: false,
    });

    const baseConfig = BASE_MAPS[baseMap];
    const tileLayer = L.tileLayer(baseConfig.url, {
      attribution: baseConfig.attribution,
      maxZoom: 18,
    }).addTo(map);
    baseTileLayerRef.current = tileLayer;

    // Click handler for cell inspect
    map.on('click', async (e: L.LeafletMouseEvent) => {
      const currentRunId = runIdRef.current;
      if (!currentRunId) return;

      const lat = e.latlng.lat;
      const lon = e.latlng.lng;

      // Add or move inspect marker
      if (inspectMarkerRef.current) {
        inspectMarkerRef.current.setLatLng(e.latlng);
      } else {
        inspectMarkerRef.current = L.circleMarker(e.latlng, {
          radius: 7,
          color: '#38bdf8',
          fillColor: '#0284c7',
          fillOpacity: 0.9,
          weight: 2,
        }).addTo(map);
      }

      setInspecting(true);
      setInspectError(null);

      try {
        const result = await inspectChangeCell(currentRunId, lat, lon);
        setInspectData(result);
      } catch (err: any) {
        setInspectError(err.message || 'Cell inspection failed');
      } finally {
        setInspecting(false);
      }
    });

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Update base map layer
  useEffect(() => {
    if (!mapRef.current || !baseTileLayerRef.current) return;
    mapRef.current.removeLayer(baseTileLayerRef.current);
    const baseConfig = BASE_MAPS[baseMap];
    const newLayer = L.tileLayer(baseConfig.url, {
      attribution: baseConfig.attribution,
      maxZoom: 18,
    }).addTo(mapRef.current);
    baseTileLayerRef.current = newLayer;
  }, [baseMap]);

  // Update GeoJSON region outline
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (geojsonLayerRef.current) {
      map.removeLayer(geojsonLayerRef.current);
      geojsonLayerRef.current = null;
    }

    if (!geometry) return;

    try {
      const geoLayer = L.geoJSON(geometry as any, {
        style: {
          color: '#06b6d4',
          weight: 2.5,
          opacity: 0.95,
          fillColor: '#06b6d4',
          fillOpacity: 0.08,
          dashArray: '4, 4',
        },
      }).addTo(map);

      geojsonLayerRef.current = geoLayer;

      if (!bounds) {
        const b = geoLayer.getBounds();
        if (b.isValid()) {
          map.fitBounds(b, { padding: [30, 30], maxZoom: 12 });
        }
      }
    } catch (err) {
      console.error('Failed to render region boundary:', err);
    }
  }, [geometry, bounds]);

  // Update Image Overlay (Difference raster PNG)
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (imageOverlayRef.current) {
      map.removeLayer(imageOverlayRef.current);
      imageOverlayRef.current = null;
    }

    if (!overlayUrl || !bounds) return;

    try {
      const imageLayer = L.imageOverlay(overlayUrl, bounds, {
        opacity: opacity,
        interactive: false,
      }).addTo(map);

      imageOverlayRef.current = imageLayer;

      // Fit bounds with padding
      const leafletBounds = L.latLngBounds(bounds[0], bounds[1]);
      if (leafletBounds.isValid()) {
        map.fitBounds(leafletBounds, { padding: [30, 30], maxZoom: 10 });
      }
    } catch (err) {
      console.error('Failed to attach image overlay:', err);
    }
  }, [overlayUrl, bounds]);

  // Update overlay opacity
  useEffect(() => {
    if (imageOverlayRef.current) {
      imageOverlayRef.current.setOpacity(opacity);
    }
  }, [opacity]);

  // Controls
  const handleZoomIn = () => mapRef.current?.zoomIn();
  const handleZoomOut = () => mapRef.current?.zoomOut();

  const handleResetView = useCallback(() => {
    if (!mapRef.current) return;
    if (bounds) {
      mapRef.current.fitBounds(L.latLngBounds(bounds[0], bounds[1]), { padding: [30, 30] });
    } else if (geojsonLayerRef.current) {
      mapRef.current.fitBounds(geojsonLayerRef.current.getBounds(), { padding: [30, 30] });
    } else {
      mapRef.current.setView([20, 0], 2);
    }
  }, [bounds]);

  const toggleFullscreen = () => {
    if (!containerRef.current) return;
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen().catch(() => {});
      setIsFullscreen(true);
    } else {
      document.exitFullscreen().catch(() => {});
      setIsFullscreen(false);
    }
  };

  const handleDownloadPNG = () => {
    if (!overlayUrl) return;
    const a = document.createElement('a');
    a.href = overlayUrl;
    a.download = `change_map_${runId || 'raster'}.png`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  const closeInspect = () => {
    setInspectData(null);
    if (inspectMarkerRef.current && mapRef.current) {
      mapRef.current.removeLayer(inspectMarkerRef.current);
      inspectMarkerRef.current = null;
    }
  };

  return (
    <div
      ref={containerRef}
      className={`relative w-full h-full min-h-[460px] bg-slate-950 overflow-hidden rounded-xl border border-slate-800 ${className}`}
    >
      {/* Top Left: Controls & Basemap */}
      <div className="absolute top-3 left-3 z-[1000] flex flex-col gap-2">
        <div className="flex items-center gap-1 bg-slate-900/90 backdrop-blur-md p-1.5 rounded-lg border border-slate-700/80 shadow-xl">
          <button
            onClick={handleZoomIn}
            className="p-1.5 text-slate-300 hover:text-white hover:bg-slate-800 rounded transition"
            title="Zoom In"
            aria-label="Zoom In"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <button
            onClick={handleZoomOut}
            className="p-1.5 text-slate-300 hover:text-white hover:bg-slate-800 rounded transition"
            title="Zoom Out"
            aria-label="Zoom Out"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <div className="w-[1px] h-4 bg-slate-700 mx-0.5" />
          <button
            onClick={handleResetView}
            className="p-1.5 text-slate-300 hover:text-white hover:bg-slate-800 rounded transition"
            title="Reset View"
            aria-label="Reset View"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
          <button
            onClick={toggleFullscreen}
            className="p-1.5 text-slate-300 hover:text-white hover:bg-slate-800 rounded transition"
            title="Toggle Fullscreen"
            aria-label="Toggle Fullscreen"
          >
            {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
        </div>

        {/* Basemap Picker */}
        <div className="flex items-center gap-1 bg-slate-900/90 backdrop-blur-md p-1 rounded-lg border border-slate-700/80 shadow-xl text-xs">
          {(['street', 'satellite', 'terrain'] as BaseMapType[]).map((type) => (
            <button
              key={type}
              onClick={() => setBaseMap(type)}
              className={`px-2 py-1 rounded font-medium capitalize transition ${
                baseMap === type
                  ? 'bg-blue-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
              }`}
            >
              {type}
            </button>
          ))}
        </div>
      </div>

      {/* Top Right: Export & Opacity Toolbar */}
      <div className="absolute top-3 right-3 z-[1000] flex flex-col items-end gap-2">
        {/* Opacity slider */}
        <div className="flex items-center gap-2 bg-slate-900/90 backdrop-blur-md px-3 py-1.5 rounded-lg border border-slate-700/80 shadow-xl">
          <Eye className="w-3.5 h-3.5 text-slate-400" />
          <span className="text-xs text-slate-300 font-medium">Opacity:</span>
          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={opacity}
            onChange={(e) => setOpacity(parseFloat(e.target.value))}
            className="w-20 h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
            title={`Opacity ${Math.round(opacity * 100)}%`}
          />
          <span className="text-xs font-mono text-cyan-400 w-8 text-right">
            {Math.round(opacity * 100)}%
          </span>
        </div>

        {/* Downloads */}
        <div className="flex items-center gap-1.5 bg-slate-900/90 backdrop-blur-md p-1.5 rounded-lg border border-slate-700/80 shadow-xl">
          {overlayUrl && (
            <button
              onClick={handleDownloadPNG}
              className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-slate-200 hover:text-white bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded transition"
              title="Download Difference Map PNG"
            >
              <FileImage className="w-3.5 h-3.5 text-cyan-400" />
              <span>Export PNG</span>
            </button>
          )}

          {geotiffUrl && (
            <a
              href={geotiffUrl}
              download={`change_${runId || 'raster'}.tif`}
              className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-slate-200 hover:text-white bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded transition"
              title="Download Georeferenced GeoTIFF"
            >
              <Download className="w-3.5 h-3.5 text-blue-400" />
              <span>GeoTIFF</span>
            </a>
          )}
        </div>
      </div>

      {/* Center Bottom: Diverging Colormap Legend (SPEC 9.5) */}
      {legend && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-[1000] bg-slate-900/95 backdrop-blur-md px-4 py-2.5 rounded-xl border border-slate-700/80 shadow-2xl flex flex-col items-center gap-2 max-w-[95%]">
          <div className="flex items-center justify-between w-full text-xs text-slate-300">
            <span className="font-semibold text-slate-200">Difference ({legend.units})</span>
            <div className="flex items-center gap-3">
              <span className="text-blue-400 font-medium">Negative (decrease)</span>
              <span className="text-slate-400">|</span>
              <span className="text-red-400 font-medium">Positive (increase)</span>
            </div>
          </div>

          {/* Diverging gradient bar */}
          <div className="relative w-72 sm:w-80 h-3 rounded-full overflow-hidden border border-slate-700 shadow-inner">
            <div
              className="w-full h-full"
              style={{
                background: `linear-gradient(to right, ${legend.colors.join(', ')})`,
              }}
            />
          </div>

          {/* Scale labels */}
          <div className="flex items-center justify-between w-72 sm:w-80 text-[10px] font-mono text-slate-400">
            {legend.thresholds.map((val, idx) => (
              <span key={idx} className={val === 0 ? 'font-bold text-white' : ''}>
                {val > 0 ? `+${val}` : `${val}`}
              </span>
            ))}
          </div>

          {/* No data swatch - visibly distinct from zero */}
          <div className="flex items-center gap-2 pt-1 border-t border-slate-800 w-full justify-center text-[11px] text-slate-400">
            <span
              className="w-3.5 h-3.5 rounded border border-slate-600 shadow"
              style={{ backgroundColor: legend.no_data_swatch.color }}
            />
            <span>{legend.no_data_swatch.label}</span>
            <span className="text-slate-500">•</span>
            <span className="text-slate-500">Transparent = unmasked background</span>
          </div>
        </div>
      )}

      {/* Bottom Left: Click-to-inspect Grid Cell Popup Card */}
      {inspecting && (
        <div className="absolute bottom-4 left-4 z-[1000] bg-slate-900/95 backdrop-blur-md p-3 rounded-xl border border-blue-500/50 shadow-2xl text-xs text-slate-300 flex items-center gap-2">
          <div className="w-3 h-3 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
          <span>Querying grid cell at clicked point...</span>
        </div>
      )}

      {inspectError && !inspecting && (
        <div className="absolute bottom-4 left-4 z-[1000] bg-slate-900/95 backdrop-blur-md p-3 rounded-xl border border-red-500/50 shadow-2xl text-xs text-red-300 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-red-400" />
          <span>{inspectError}</span>
          <button onClick={() => setInspectError(null)} className="ml-2 hover:text-white">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {inspectData && !inspecting && (
        <div className="absolute bottom-4 left-4 z-[1000] bg-slate-900/95 backdrop-blur-md p-4 rounded-xl border border-slate-700/80 shadow-2xl text-xs text-slate-200 w-72 space-y-2">
          <div className="flex items-center justify-between pb-2 border-b border-slate-800">
            <div className="flex items-center gap-1.5 font-semibold text-slate-100">
              <MapPin className="w-4 h-4 text-cyan-400" />
              <span>Cell Inspection</span>
            </div>
            <button
              onClick={closeInspect}
              className="text-slate-400 hover:text-white p-0.5 rounded hover:bg-slate-800 transition"
              aria-label="Close Inspection"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="grid grid-cols-2 gap-1 text-[11px] text-slate-400 font-mono">
            <div>
              Lat: <span className="text-slate-200">{inspectData.cell_lat.toFixed(2)}°</span>
            </div>
            <div>
              Lon: <span className="text-slate-200">{inspectData.cell_lon.toFixed(2)}°</span>
            </div>
          </div>

          <div className="space-y-1.5 pt-1 text-xs">
            <div className="flex justify-between">
              <span className="text-slate-400">Baseline Mean:</span>
              <span className="font-mono text-slate-200">
                {inspectData.baseline_mean !== null
                  ? `${inspectData.baseline_mean} ${inspectData.units}`
                  : 'No Data'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Comparison Mean:</span>
              <span className="font-mono text-slate-200">
                {inspectData.comparison_mean !== null
                  ? `${inspectData.comparison_mean} ${inspectData.units}`
                  : 'No Data'}
              </span>
            </div>
            <div className="flex justify-between items-center pt-1 border-t border-slate-800 font-semibold">
              <span className="text-slate-300">Difference:</span>
              <span
                className={`font-mono text-sm ${
                  inspectData.difference === null
                    ? 'text-slate-500'
                    : inspectData.difference > 0
                    ? 'text-red-400'
                    : inspectData.difference < 0
                    ? 'text-blue-400'
                    : 'text-slate-300'
                }`}
              >
                {inspectData.difference !== null
                  ? `${inspectData.difference > 0 ? '+' : ''}${inspectData.difference} ${inspectData.units}`
                  : 'No Data'}
              </span>
            </div>
          </div>

          <div className="pt-2 border-t border-slate-800 flex items-center justify-between text-[11px]">
            <span className="text-slate-400">Overlap Fraction:</span>
            <span className="font-mono text-cyan-400">
              {Math.round(inspectData.overlap_fraction * 100)}%
            </span>
          </div>

          <div className="flex items-center gap-1.5 pt-1">
            {inspectData.is_valid ? (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-950/60 text-emerald-300 border border-emerald-800/60">
                <CheckCircle2 className="w-3 h-3 text-emerald-400" /> Valid Cell
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-slate-800 text-slate-400 border border-slate-700">
                No Data / Outside Mask
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
