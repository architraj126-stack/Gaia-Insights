import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ChangesPage } from './ChangesPage';
import { useSession, initialSessionState } from '../store/session';
import * as changeApi from '../api/change';

// Mock Leaflet
vi.mock('leaflet', () => {
  const mapInstance = {
    setView: vi.fn().mockReturnThis(),
    fitBounds: vi.fn().mockReturnThis(),
    zoomIn: vi.fn().mockReturnThis(),
    zoomOut: vi.fn().mockReturnThis(),
    remove: vi.fn(),
    addLayer: vi.fn().mockReturnThis(),
    removeLayer: vi.fn().mockReturnThis(),
    on: vi.fn(),
  };

  return {
    default: {
      map: vi.fn(() => mapInstance),
      tileLayer: vi.fn(() => ({ addTo: vi.fn().mockReturnThis() })),
      geoJSON: vi.fn(() => ({
        addTo: vi.fn().mockReturnThis(),
        getBounds: vi.fn(() => ({
          isValid: () => true,
        })),
      })),
      imageOverlay: vi.fn(() => ({
        addTo: vi.fn().mockReturnThis(),
        setOpacity: vi.fn(),
      })),
      circleMarker: vi.fn(() => ({
        addTo: vi.fn().mockReturnThis(),
        setLatLng: vi.fn(),
      })),
      latLngBounds: vi.fn(() => ({
        isValid: () => true,
      })),
    },
  };
});

describe('ChangesPage (Page 4 - Change Detection)', () => {
  const mockChangeResult: changeApi.ChangeMapResult = {
    job_id: 'job_c123',
    run_id: 'run_c123',
    status: 'completed',
    overlay_url: '/api/analysis/change-map/run_c123/overlay.png',
    geotiff_url: '/api/analysis/change-map/run_c123/geotiff',
    bounds: [
      [-10.0, -10.0],
      [10.0, 10.0],
    ],
    legend: {
      colormap: 'RdBu_r',
      symmetric_zero: 0.0,
      min_val: -250.0,
      max_val: 250.0,
      units: 'mm/year',
      thresholds: [-250.0, -125.0, 0.0, 125.0, 250.0],
      colors: ['#0571b0', '#92c5de', '#f7f7f7', '#f4a582', '#ca0020'],
      no_data_swatch: {
        color: '#9ca3af',
        label: 'No data / Outside study region',
      },
    },
    spatial_summary: {
      area_weighted_mean_change: 32.45,
      share_increasing_pct: 65.5,
      share_decreasing_pct: 28.5,
      share_no_change_pct: 6.0,
      highest_change: {
        value: 184.2,
        lat: 5.0,
        lon: 2.5,
      },
      lowest_change: {
        value: -112.8,
        lat: -7.5,
        lon: -2.5,
      },
      valid_area_km2: 1250000.0,
      total_region_area_km2: 1350000.0,
      nodata_area_km2: 100000.0,
      nodata_share_pct: 7.41,
      valid_cell_count: 42,
      intersecting_cell_count: 48,
    },
    provenance: {
      run_id: 'run_c123',
      dataset_id: 'gpcp_monthly_v23',
      dataset_version: 'v2.3',
      variable: 'precipitation',
      baseline_period: '1990-2005',
      comparison_period: '2006-2025',
      metric: 'absolute',
      aggregation: 'annual',
      formula: 'B - A (Comparison mean minus Baseline mean)',
      units: 'mm/year',
      native_units: 'mm/year',
      mask_method: 'fractional_overlap',
      area_weighting: 'geodesic_ellipsoid',
    },
    warnings: [],
    units: 'mm/year',
    metric: 'absolute',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    useSession.setState({
      ...initialSessionState,
      selectedVariables: [
        {
          variableId: 'precipitation',
          datasetId: 'gpcp_monthly_v23',
          datasetVersion: 'v2.3',
          fieldName: 'precip',
          units: 'mm',
        },
      ],
      region: {
        label: 'France (FRA)',
        type: 'admin',
        geometry: {
          type: 'Polygon',
          coordinates: [
            [
              [-5.0, 42.0],
              [8.0, 42.0],
              [8.0, 51.0],
              [-5.0, 51.0],
              [-5.0, 42.0],
            ],
          ],
        },
        crs: 'EPSG:4326',
        areaKm2: 551695,
      },
    });

    vi.spyOn(changeApi, 'executeChangeMapAnalysis').mockResolvedValue(mockChangeResult);
  });

  it('renders 23/52/25 layout with variable, read-only region, baseline and comparison period inputs', async () => {
    render(
      <MemoryRouter>
        <ChangesPage />
      </MemoryRouter>
    );

    // Left panel checks
    expect(screen.getByText('Change Settings')).toBeInTheDocument();
    expect(screen.getByText('France (FRA)')).toBeInTheDocument();
    expect(screen.getByText(/Baseline Period/i)).toBeInTheDocument();
    expect(screen.getByText(/Comparison Period/i)).toBeInTheDocument();
    expect(screen.getByText('Absolute Change (B − A)')).toBeInTheDocument();
    expect(screen.getByText('Percentage Change (%)')).toBeInTheDocument();
    expect(screen.getByText('Spatial Trend (Slope/Year)')).toBeInTheDocument();

    // Centre panel checks
    expect(screen.getByText('Difference Map Overlay')).toBeInTheDocument();

    // Right panel checks
    expect(screen.getByText('Spatial Summary')).toBeInTheDocument();

    await waitFor(() => {
      expect(changeApi.executeChangeMapAnalysis).toHaveBeenCalledTimes(1);
    });
  });

  it('displays spatial summary metrics according to SPEC 9.6', async () => {
    render(
      <MemoryRouter>
        <ChangesPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      // Overall area-weighted change
      expect(screen.getByText('+32.45')).toBeInTheDocument();
      // Increasing and decreasing shares
      expect(screen.getByText('65.5%')).toBeInTheDocument();
      expect(screen.getByText('28.5%')).toBeInTheDocument();
      expect(screen.getByText('6%')).toBeInTheDocument();
      // Extremes
      expect(screen.getByText('+184.2 mm/year')).toBeInTheDocument();
      expect(screen.getByText('-112.8 mm/year')).toBeInTheDocument();
      // No-data area reported separately from no change
      expect(screen.getByText('7.41%')).toBeInTheDocument();
    });
  });

  it('diverging legend displays units and distinct no-data swatch', async () => {
    render(
      <MemoryRouter>
        <ChangesPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Difference \(mm\/year\)/i)).toBeInTheDocument();
      expect(screen.getByText(/No data \/ Outside study region/i)).toBeInTheDocument();
      expect(screen.getByText('+250')).toBeInTheDocument();
      expect(screen.getByText('-250')).toBeInTheDocument();
    });
  });

  it('rejects overlapping periods unless explicitly confirmed', async () => {
    render(
      <MemoryRouter>
        <ChangesPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(changeApi.executeChangeMapAnalysis).toHaveBeenCalledTimes(1);
    });

    // Baseline end year changed to 2010 (overlapping with comparison start year 2006)
    const baselineEndInput = screen.getAllByRole('spinbutton')[1];
    fireEvent.change(baselineEndInput, { target: { value: '2010' } });

    // Warning alert should appear
    expect(screen.getByText('Overlapping Periods')).toBeInTheDocument();

    // Calculate button should be disabled without confirmation checkbox
    const calcButton = screen.getByRole('button', { name: /Calculate Change Map/i });
    expect(calcButton).toBeDisabled();

    // Check confirmation checkbox
    const confirmCheckbox = screen.getByRole('checkbox', { name: /Explicitly confirm overlap/i });
    fireEvent.click(confirmCheckbox);

    // Button should now be enabled
    expect(calcButton).not.toBeDisabled();
  });

  it('shows percentage change warning when percentage metric is selected', async () => {
    render(
      <MemoryRouter>
        <ChangesPage />
      </MemoryRouter>
    );

    const pctButton = screen.getByText('Percentage Change (%)');
    fireEvent.click(pctButton);

    expect(screen.getByText(/Cells with baseline \|A\| ≤ 1.0 mm\/year are suppressed/i)).toBeInTheDocument();
  });

  it('strictly adheres to SPEC 9.8 by never using the word "significant" on this page', async () => {
    const { container } = render(
      <MemoryRouter>
        <ChangesPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Spatial Summary')).toBeInTheDocument();
    });

    // SPEC 9.8 non-negotiable rule:
    // "Never use the word 'significant' on this page; SPEC 9.8"
    const textContent = container.textContent || '';
    expect(textContent).not.toMatch(/\bsignificant\b/i);
    // Note: It CAN link to the next page named "Significance & Reports", but the adjective/finding "significant" must never be used on Page 4!
  });
});
