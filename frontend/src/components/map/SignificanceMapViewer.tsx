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
  Info,
} from 'lucide-react';
import type { SignificanceLegend } from '../../api/significance';

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

export interface SignificanceMapViewerProps {
  runId?: string;
  overlayUrl?: string;
  geotiffUrl?: string;
  bounds?: [[number, number], [number, number]];
  legend?: SignificanceLegend;
  geometry?: Geometry | null;
  className?: string;
}

export const SignificanceMapViewer: React.FC<SignificanceMapViewerProps> = ({
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

  const [baseMap, setBaseMap] = useState<BaseMapType>('street');
  const [opacity, setOpacity] = useState<number>(0.85);
  const [isFullscreen, setIsFullscreen] = useState(false);

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

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Update base tile layer on change
  useEffect(() => {
    if (!mapRef.current || !baseTileLayerRef.current) return;
    const baseConfig = BASE_MAPS[baseMap];
    baseTileLayerRef.current.setUrl(baseConfig.url);
  }, [baseMap]);

  // Render region geometry outline
  useEffect(() => {
    if (!mapRef.current) return;

    if (geojsonLayerRef.current) {
      geojsonLayerRef.current.remove();
      geojsonLayerRef.current = null;
    }

    if (geometry) {
      try {
        const geoLayer = L.geoJSON(geometry as any, {
          style: {
            color: '#38bdf8',
            weight: 2,
            dashArray: '4, 4',
            fillColor: '#0284c7',
            fillOpacity: 0.05,
          },
        }).addTo(mapRef.current);
        geojsonLayerRef.current = geoLayer;

        if (!bounds) {
          mapRef.current.fitBounds(geoLayer.getBounds(), { padding: [20, 20], maxZoom: 8 });
        }
      } catch (err) {
        console.error('Failed to render geometry outline:', err);
      }
    }
  }, [geometry, bounds]);

  // Render image overlay when overlayUrl or bounds change
  useEffect(() => {
    if (!mapRef.current) return;

    if (imageOverlayRef.current) {
      imageOverlayRef.current.remove();
      imageOverlayRef.current = null;
    }

    if (overlayUrl && bounds && bounds.length === 2) {
      try {
        const leafletBounds: L.LatLngBoundsExpression = [
          [bounds[0][0], bounds[0][1]],
          [bounds[1][0], bounds[1][1]],
        ];

        const overlay = L.imageOverlay(overlayUrl, leafletBounds, {
          opacity,
          interactive: true,
          crossOrigin: true,
        }).addTo(mapRef.current);

        imageOverlayRef.current = overlay;

        mapRef.current.fitBounds(leafletBounds, {
          padding: [20, 20],
          maxZoom: 7,
        });
      } catch (err) {
        console.error('Failed to attach significance image overlay:', err);
      }
    }
  }, [overlayUrl, bounds]);

  // Update opacity dynamically
  useEffect(() => {
    if (imageOverlayRef.current) {
      imageOverlayRef.current.setOpacity(opacity);
    }
  }, [opacity]);

  // Zoom / View handlers
  const handleZoomIn = useCallback(() => mapRef.current?.zoomIn(), []);
  const handleZoomOut = useCallback(() => mapRef.current?.zoomOut(), []);
  const handleResetView = useCallback(() => {
    if (!mapRef.current) return;
    if (bounds) {
      mapRef.current.fitBounds(
        [
          [bounds[0][0], bounds[0][1]],
          [bounds[1][0], bounds[1][1]],
        ],
        { padding: [20, 20], maxZoom: 7 }
      );
    } else if (geojsonLayerRef.current) {
      mapRef.current.fitBounds(geojsonLayerRef.current.getBounds(), { padding: [20, 20], maxZoom: 7 });
    } else {
      mapRef.current.setView([20, 0], 2);
    }
  }, [bounds]);

  const toggleFullscreen = useCallback(() => {
    if (!containerRef.current?.parentElement) return;
    if (!isFullscreen) {
      containerRef.current.parentElement.requestFullscreen?.();
      setIsFullscreen(true);
    } else {
      document.exitFullscreen?.();
      setIsFullscreen(false);
    }
  }, [isFullscreen]);

  return (
    <div
      className={`relative flex flex-col bg-slate-900 border border-slate-700/60 rounded-xl overflow-hidden shadow-2xl ${className}`}
      data-testid="significance-map-container"
    >
      {/* Top Map Toolbar */}
      <div className="flex flex-wrap items-center justify-between px-3 py-2 bg-slate-900/95 border-b border-slate-800 text-xs text-slate-300 z-10 gap-2">
        <div className="flex items-center space-x-2">
          <span className="font-semibold text-slate-200">Base:</span>
          <div className="inline-flex rounded-md shadow-sm bg-slate-800 p-0.5 border border-slate-700">
            {(['street', 'satellite', 'terrain'] as BaseMapType[]).map((type) => (
              <button
                key={type}
                type="button"
                onClick={() => setBaseMap(type)}
                className={`px-2 py-0.5 rounded text-[11px] font-medium capitalize transition-colors ${
                  baseMap === type
                    ? 'bg-blue-600 text-white shadow'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700/50'
                }`}
              >
                {type}
              </button>
            ))}
          </div>
        </div>

        {/* Opacity control */}
        <div className="flex items-center space-x-2">
          <Eye className="w-3.5 h-3.5 text-slate-400" />
          <span className="text-slate-400">Opacity:</span>
          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={opacity}
            onChange={(e) => setOpacity(parseFloat(e.target.value))}
            className="w-20 h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
            title={`Overlay Opacity: ${Math.round(opacity * 100)}%`}
          />
          <span className="w-8 text-right font-mono text-[11px] text-slate-300">
            {Math.round(opacity * 100)}%
          </span>
        </div>

        {/* Actions (Downloads & Fullscreen) */}
        <div className="flex items-center space-x-1.5">
          {geotiffUrl && (
            <a
              href={geotiffUrl}
              download
              className="inline-flex items-center space-x-1 px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-600 rounded text-[11px] font-medium transition-colors"
              title="Download Georeferenced GeoTIFF"
            >
              <Download className="w-3.5 h-3.5 text-cyan-400" />
              <span>GeoTIFF</span>
            </a>
          )}
          {overlayUrl && (
            <a
              href={overlayUrl}
              download={`significance_${runId || 'map'}.png`}
              className="inline-flex items-center space-x-1 px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-600 rounded text-[11px] font-medium transition-colors"
              title="Download PNG Overlay"
            >
              <FileImage className="w-3.5 h-3.5 text-blue-400" />
              <span>PNG</span>
            </a>
          )}
          <button
            type="button"
            onClick={toggleFullscreen}
            className="p-1 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded transition-colors"
            title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
          >
            {isFullscreen ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {/* Leaflet Map Canvas */}
      <div className="relative flex-1 min-h-[420px] w-full">
        <div ref={containerRef} className="absolute inset-0 z-0 bg-slate-950" />

        {/* Floating Zoom & Reset controls */}
        <div className="absolute top-3 left-3 z-[400] flex flex-col space-y-1 bg-slate-900/90 p-1 rounded-lg border border-slate-700/80 shadow-lg backdrop-blur">
          <button
            type="button"
            onClick={handleZoomIn}
            className="p-1.5 text-slate-300 hover:text-white hover:bg-slate-800 rounded transition-colors"
            title="Zoom In"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={handleZoomOut}
            className="p-1.5 text-slate-300 hover:text-white hover:bg-slate-800 rounded transition-colors"
            title="Zoom Out"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={handleResetView}
            className="p-1.5 text-slate-300 hover:text-white hover:bg-slate-800 rounded transition-colors border-t border-slate-800"
            title="Reset View"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
        </div>

        {/* Accessible 5-Class Map Legend */}
        {legend && (
          <div
            className="absolute bottom-4 left-4 z-[400] max-w-sm bg-slate-900/95 border border-slate-700/90 rounded-lg p-3 shadow-xl backdrop-blur text-xs"
            data-testid="significance-map-legend"
          >
            <div className="flex items-center justify-between pb-1.5 mb-2 border-b border-slate-800">
              <span className="font-semibold text-slate-200">{legend.title}</span>
              <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono bg-blue-950/80 border border-blue-800 text-blue-300">
                α = {legend.alpha}
              </span>
            </div>

            {/* Multiple-Testing Status Badge (SPEC 10.4) */}
            <div className="mb-2 px-2 py-1 rounded bg-slate-800/80 border border-slate-700 text-[11px] flex items-center justify-between">
              <span className="text-slate-400">Mode:</span>
              <span
                className={`font-semibold ${
                  (legend.p_value_mode || '').includes('FDR') ? 'text-emerald-400' : 'text-amber-400'
                }`}
                data-testid="legend-p-value-mode"
              >
                {legend.p_value_mode || 'FDR Adjusted'}
              </span>
            </div>

            {/* 5 Classes Swatches with Pattern/Symbol Badges */}
            <div className="space-y-1.5">
              {legend.classes.map((cls) => (
                <div
                  key={cls.code}
                  className="flex items-center justify-between py-0.5 px-1 rounded hover:bg-slate-800/50 transition-colors"
                >
                  <div className="flex items-center space-x-2">
                    {/* Accessible Symbol Badge (not color alone) */}
                    <div
                      className="w-5 h-5 rounded flex items-center justify-center font-bold text-xs shadow-inner"
                      style={{
                        backgroundColor: cls.color,
                        color: cls.code === 3 ? '#1e293b' : '#ffffff',
                      }}
                      title={cls.description}
                    >
                      {cls.badge_symbol || (cls as any).badge}
                    </div>
                    <span className="text-slate-300 font-medium">{cls.label || (cls as any).name}</span>
                  </div>
                  <div className="flex items-center space-x-2 text-[11px] font-mono text-slate-400">
                    <span className="text-slate-200 font-semibold">{cls.count?.toLocaleString?.() ?? 0}</span>
                    <span>cells</span>
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-2 pt-1.5 border-t border-slate-800/80 text-[10px] text-slate-400 flex items-center space-x-1">
              <Info className="w-3 h-3 text-cyan-400 shrink-0" />
              <span>Classes use pattern symbols (+, −, o, ?, x) to ensure accessibility.</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
