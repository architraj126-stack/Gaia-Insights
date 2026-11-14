import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { RegionPage } from './RegionPage';
import { useSession, initialSessionState } from '../store/session';
import * as regionsApi from '../api/regions';
import * as availabilityApi from '../api/availability';

// Mock the API calls
vi.mock('../api/regions', async () => {
  const actual = await vi.importActual<typeof import('../api/regions')>('../api/regions');
  return {
    ...actual,
    searchRegions: vi.fn(),
    fetchRegionGeometry: vi.fn(),
    validateRegion: vi.fn(),
  };
});

vi.mock('../api/availability', async () => {
  const actual = await vi.importActual<typeof import('../api/availability')>('../api/availability');
  return {
    ...actual,
    fetchDatasetAvailability: vi.fn(),
  };
});

describe('RegionPage (Page 2 - Geographic Explorer)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useSession.setState({
      ...initialSessionState,
      selectedVariables: [
        {
          variableId: 'precipitation',
          datasetId: 'gpcp_monthly_v23',
          datasetVersion: 'V2.3',
          fieldName: 'precip',
          units: 'mm/day',
        },
      ],
      page3ResultId: 'prior-trend-result',
    });

    // Default mock implementations
    vi.mocked(regionsApi.searchRegions).mockResolvedValue([
      {
        id: 'admin0_fji_fiji',
        name: 'Fiji',
        type: 'admin-0',
        subtype: 'country',
        country: 'Fiji',
        iso_a3: 'FJI',
        bbox: [-180, -18.28, 180, -16.02],
      },
    ]);

    vi.mocked(regionsApi.fetchRegionGeometry).mockResolvedValue({
      id: 'admin0_fji_fiji',
      name: 'Fiji',
      type: 'admin-0',
      crs: 'EPSG:4326',
      bbox: [-180, -18.28, 180, -16.02],
      geometry: {
        type: 'MultiPolygon',
        coordinates: [
          [[[177, -17], [179, -17], [179, -16], [177, -16], [177, -17]]],
          [[[-180, -17], [-178, -17], [-178, -16], [-180, -16], [-180, -17]]],
        ],
      },
    });

    vi.mocked(regionsApi.validateRegion).mockResolvedValue({
      status: 'valid',
      crs: 'EPSG:4326',
      geometry: {
        type: 'MultiPolygon',
        coordinates: [
          [[[177, -17], [179, -17], [179, -16], [177, -16], [177, -17]]],
          [[[-180, -17], [-178, -17], [-178, -16], [-180, -16], [-180, -17]]],
        ],
      },
      area_km2: 18272.5,
      bbox: [-180, -18.28, 180, -16.02],
      centroid: [179.0, -16.5],
      warnings: ['Geometry crosses the antimeridian (180°/-180°) and was split into a MultiPolygon.'],
    });

    vi.mocked(availabilityApi.fetchDatasetAvailability).mockResolvedValue({
      dataset_id: 'gpcp_monthly_v23',
      variable_id: 'precipitation',
      product_name: 'GPCP Monthly Analysis Product',
      version: 'V2.3',
      status: 'Available',
      spatial_coverage_percent: 100.0,
      temporal_coverage_percent: 100.0,
      cell_count: 14,
      spatial_resolution: '2.5° × 2.5°',
      temporal_resolution: 'monthly',
      area_km2: 18272.5,
      valid_date_range: {
        start: '1979-01-01',
        latest_observation_date: '2026-10-01',
        last_catalogue_check: '2026-11-13T06:00:00Z',
      },
      warnings: [],
      provider: 'NOAA PSL',
    });
  });

  it('renders the 3-column Geographic Explorer layout with mode selectors', () => {
    render(
      <MemoryRouter>
        <RegionPage />
      </MemoryRouter>
    );

    expect(screen.getByRole('heading', { level: 1, name: 'Page 2: Geographic Explorer' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Admin Boundary/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Draw Polygon/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Draw Rectangle/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Point \+ Buffer/i })).toBeInTheDocument();

    // Check right panel headers
    expect(screen.getByRole('heading', { level: 2, name: /Region Details/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2, name: /Dataset Availability/i })).toBeInTheDocument();

    // Check persisted selection card
    expect(screen.getByText(/Persisted Selection from Page 1/i)).toBeInTheDocument();
    expect(screen.getByText('gpcp_monthly_v23')).toBeInTheDocument();
  });

  it('searches administrative boundaries, displays resolved feature, and confirms region into store', async () => {
    render(
      <MemoryRouter>
        <RegionPage />
      </MemoryRouter>
    );

    const searchInput = screen.getByPlaceholderText(/Search place name/i);
    fireEvent.change(searchInput, { target: { value: 'Fiji' } });

    // Wait for searchResults dropdown
    await waitFor(() => {
      expect(regionsApi.searchRegions).toHaveBeenCalledWith('Fiji', 15);
    });

    const fijiItem = await screen.findByRole('button', { name: /Fiji/i });
    fireEvent.click(fijiItem);

    // Verify fetchRegionGeometry and validateRegion were called
    await waitFor(() => {
      expect(regionsApi.fetchRegionGeometry).toHaveBeenCalledWith('admin0_fji_fiji');
      expect(regionsApi.validateRegion).toHaveBeenCalled();
    });

    // Check right panel displays validated metrics
    expect(await screen.findByText(/18,272.5 km²/)).toBeInTheDocument();
    expect(screen.getByText(/14 valid centres/i)).toBeInTheDocument();

    // Check scientific warning is displayed
    expect(screen.getByText(/Geometry crosses the antimeridian/i)).toBeInTheDocument();

    // Confirm button should be active
    const confirmBtn = screen.getByRole('button', { name: /Confirm Selected Region/i });
    expect(confirmBtn).not.toBeDisabled();
    fireEvent.click(confirmBtn);

    // Verify region stored in Zustand store and downstream results cleared
    const storedState = useSession.getState();
    expect(storedState.region).not.toBeNull();
    expect(storedState.region?.label).toBe('Fiji');
    expect(storedState.region?.areaKm2).toBe(18272.5);
    expect(storedState.page3ResultId).toBeUndefined(); // Invalidation rule checked!
  });

  it('supports point + buffer mode and updates geodesic area', async () => {
    vi.mocked(regionsApi.validateRegion).mockResolvedValueOnce({
      status: 'valid',
      crs: 'EPSG:4326',
      geometry: {
        type: 'Polygon',
        coordinates: [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
      },
      area_km2: 7853.98,
      bbox: [-0.45, -0.45, 0.45, 0.45],
      centroid: [0.0, 0.0],
      warnings: ['Generated geodesic buffer polygon with radius 50.0 km.'],
    });

    render(
      <MemoryRouter>
        <RegionPage />
      </MemoryRouter>
    );

    const bufferTab = screen.getByRole('button', { name: /Point \+ Buffer/i });
    fireEvent.click(bufferTab);

    // Verify validateRegion was called for buffer mode
    await waitFor(() => {
      expect(regionsApi.validateRegion).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'point_buffer',
          radius_km: 50,
        })
      );
    });

    // Verify area is displayed
    const areas = await screen.findAllByText(/7,854/);
    expect(areas.length).toBeGreaterThan(0);
  });
});
