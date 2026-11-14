import React, { useEffect, useRef, useState, useCallback } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import '@geoman-io/leaflet-geoman-free';
import '@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css';
import type { Geometry } from 'geojson';
import {
  Layers,
  Maximize2,
  Minimize2,
  RotateCcw,
  ZoomIn,
  ZoomOut,
  Crosshair,
  MapPin,
  Pencil,
  Trash2,
} from 'lucide-react';

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

export interface GeographicMapProps {
  geometry?: Geometry | null;
  drawMode?: 'admin' | 'polygon' | 'rectangle' | 'point_buffer';
  onGeometryDrawn?: (geom: Geometry) => void;
  onPointClicked?: (point: [number, number]) => void;
  className?: string;
}

export const GeographicMap: React.FC<GeographicMapProps> = ({
  geometry,
  drawMode = 'admin',
  onGeometryDrawn,
  onPointClicked,
  className = '',
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const baseTileLayerRef = useRef<L.TileLayer | null>(null);
  const geojsonLayerRef = useRef<L.GeoJSON | null>(null);
  const [baseMap, setBaseMap] = useState<BaseMapType>('street');
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isEditing, setIsEditing] = useState(false);

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

    // Base layer
    const baseConfig = BASE_MAPS[baseMap];
    const tileLayer = L.tileLayer(baseConfig.url, {
      attribution: baseConfig.attribution,
      maxZoom: 18,
    }).addTo(map);
    baseTileLayerRef.current = tileLayer;

    // Attribution
    L.control.attribution({ position: 'bottomright', prefix: false }).addTo(map);

    // Geoman Setup
    map.pm.addControls({
      position: 'topleft',
      drawCircle: false,
      drawCircleMarker: false,
      drawPolyline: false,
      drawText: false,
      drawMarker: false,
      drawPolygon: true,
      drawRectangle: true,
      editMode: true,
      dragMode: false,
      cutPolygon: false,
      removalMode: true,
      rotateMode: false,
    });

    // Event handlers for Geoman shapes
    map.on('pm:create', (e: any) => {
      const layer = e.layer;
      if (layer && typeof layer.toGeoJSON === 'function') {
        const feat = layer.toGeoJSON();
        if (feat && feat.geometry && onGeometryDrawn) {
          onGeometryDrawn(feat.geometry as Geometry);
        }
      }
    });

    map.on('pm:remove', () => {
      if (geojsonLayerRef.current) {
        geojsonLayerRef.current.clearLayers();
      }
    });

    // Map click for point buffer mode
    map.on('click', (e: L.LeafletMouseEvent) => {
      if (drawMode === 'point_buffer' && onPointClicked) {
        onPointClicked([e.latlng.lng, e.latlng.lat]);
      }
    });

    mapRef.current = map;

    return () => {
      try {
        if (map.pm) {
          map.pm.disableDraw();
          map.pm.disableGlobalEditMode();
        }
        map.stop();
        map.remove();
      } catch {
        // Silently handle any teardown race conditions during rapid navigation
      }
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

  // Handle drawMode switching
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.pm) return;

    // Disable all active drawing/editing first
    map.pm.disableDraw();

    if (drawMode === 'polygon') {
      map.pm.enableDraw('Polygon', {
        snappable: true,
        finishOn: 'dblclick',
        pathOptions: {
          color: '#06b6d4',
          fillColor: '#06b6d4',
          fillOpacity: 0.25,
          weight: 2,
        },
      });
    } else if (drawMode === 'rectangle') {
      map.pm.enableDraw('Rectangle', {
        pathOptions: {
          color: '#3b82f6',
          fillColor: '#3b82f6',
          fillOpacity: 0.25,
          weight: 2,
        },
      });
    }
  }, [drawMode]);

  // Update GeoJSON layer when geometry prop changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    // Remove existing GeoJSON layer
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
          opacity: 0.9,
          fillColor: '#06b6d4',
          fillOpacity: 0.2,
          dashArray: undefined,
        },
      }).addTo(map);

      geojsonLayerRef.current = geoLayer;

      // Fit map bounds to the geometry
      const bounds = geoLayer.getBounds();
      if (bounds.isValid()) {
        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 12 });
      }
    } catch (err) {
      console.error('Failed to render GeoJSON on map:', err);
    }
  }, [geometry]);

  // Map Controls Callbacks
  const handleZoomIn = () => mapRef.current?.zoomIn();
  const handleZoomOut = () => mapRef.current?.zoomOut();
  const handleResetView = () => mapRef.current?.setView([20, 0], 2);

  const handleFitBounds = useCallback(() => {
    if (geojsonLayerRef.current && mapRef.current) {
      const bounds = geojsonLayerRef.current.getBounds();
      if (bounds.isValid()) {
        mapRef.current.fitBounds(bounds, { padding: [40, 40] });
      }
    }
  }, []);

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

  const toggleGlobalEdit = () => {
    const map = mapRef.current;
    if (!map) return;
    if (isEditing) {
      map.pm.disableGlobalEditMode();
      setIsEditing(false);
    } else {
      map.pm.enableGlobalEditMode();
      setIsEditing(true);
    }
  };

  const clearAllDrawings = () => {
    const map = mapRef.current;
    if (!map) return;
    if (geojsonLayerRef.current) {
      geojsonLayerRef.current.clearLayers();
    }
    // Also remove any Geoman drawn layers
    map.eachLayer((l: any) => {
      if (l.pm && l !== baseTileLayerRef.current) {
        map.removeLayer(l);
      }
    });
  };

  return (
    <div
      className={`relative w-full h-full min-h-[500px] lg:min-h-[640px] rounded-card overflow-hidden border border-border-subtle bg-navy-950 flex flex-col ${className}`}
    >
      {/* Map Container */}
      <div ref={containerRef} className="w-full h-full flex-1 z-0" />

      {/* Top Left: Base Map Switcher */}
      <div className="absolute top-4 left-4 z-[1000] flex items-center bg-navy-900/90 backdrop-blur-md border border-border-subtle rounded-lg p-1 shadow-card text-xs">
        <div className="flex items-center px-2 py-1 text-slate-400 font-mono text-[11px] border-r border-border-subtle/80 mr-1">
          <Layers className="w-3.5 h-3.5 mr-1 text-cyan-400" />
          Base:
        </div>
        {(['street', 'satellite', 'terrain'] as BaseMapType[]).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setBaseMap(t)}
            className={`px-2.5 py-1 rounded font-medium transition-colors capitalize ${
              baseMap === t
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
                : 'text-slate-400 hover:text-white hover:bg-navy-800'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Top Right: Map Controls (Zoom, Reset, Fit, Fullscreen) */}
      <div className="absolute top-4 right-4 z-[1000] flex flex-col gap-1.5 bg-navy-900/90 backdrop-blur-md border border-border-subtle rounded-lg p-1 shadow-card text-slate-300">
        <button
          type="button"
          onClick={handleZoomIn}
          title="Zoom In"
          aria-label="Zoom In"
          className="p-1.5 hover:bg-navy-800 hover:text-white rounded transition-colors"
        >
          <ZoomIn className="w-4 h-4" />
        </button>
        <button
          type="button"
          onClick={handleZoomOut}
          title="Zoom Out"
          aria-label="Zoom Out"
          className="p-1.5 hover:bg-navy-800 hover:text-white rounded transition-colors"
        >
          <ZoomOut className="w-4 h-4" />
        </button>
        <div className="w-full h-px bg-border-subtle/60 my-0.5" />
        <button
          type="button"
          onClick={handleResetView}
          title="Reset Global View"
          aria-label="Reset Global View"
          className="p-1.5 hover:bg-navy-800 hover:text-white rounded transition-colors"
        >
          <RotateCcw className="w-4 h-4" />
        </button>
        {geometry && (
          <button
            type="button"
            onClick={handleFitBounds}
            title="Fit to Selected Geometry"
            aria-label="Fit to Selected Geometry"
            className="p-1.5 hover:bg-navy-800 hover:text-cyan-400 rounded transition-colors"
          >
            <Crosshair className="w-4 h-4 text-cyan-400" />
          </button>
        )}
        <button
          type="button"
          onClick={toggleFullscreen}
          title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
          aria-label={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
          className="p-1.5 hover:bg-navy-800 hover:text-white rounded transition-colors"
        >
          {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
        </button>
      </div>

      {/* Bottom Floating Drawing Status & Edit Tools */}
      <div className="absolute bottom-4 left-4 z-[1000] flex items-center gap-2 bg-navy-900/90 backdrop-blur-md border border-border-subtle rounded-lg px-3 py-1.5 shadow-card text-xs text-slate-300">
        <span className="flex items-center gap-1.5 text-slate-400">
          <MapPin className="w-3.5 h-3.5 text-cyan-400" />
          Mode: <strong className="text-white capitalize">{drawMode.replace('_', ' ')}</strong>
        </span>
        {(drawMode === 'polygon' || drawMode === 'rectangle') && (
          <>
            <span className="text-border-subtle">|</span>
            <button
              type="button"
              onClick={toggleGlobalEdit}
              className={`flex items-center gap-1 px-2 py-0.5 rounded transition-colors ${
                isEditing ? 'bg-cyan-500/20 text-cyan-300' : 'hover:bg-navy-800 text-slate-400'
              }`}
            >
              <Pencil className="w-3 h-3" />
              {isEditing ? 'Finish Edit' : 'Edit Vertices'}
            </button>
            <button
              type="button"
              onClick={clearAllDrawings}
              className="flex items-center gap-1 px-2 py-0.5 rounded hover:bg-red-500/20 text-rose-400 transition-colors"
            >
              <Trash2 className="w-3 h-3" />
              Clear
            </button>
          </>
        )}
      </div>
    </div>
  );
};
