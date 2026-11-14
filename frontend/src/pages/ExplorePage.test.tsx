import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ExplorePage } from './ExplorePage';
import { RegionPage } from './RegionPage';
import { useSession, initialSessionState } from '../store/session';

const mockVariables = [
  {
    id: 'precipitation',
    name: 'Precipitation',
    category: 'Atmosphere',
    description: 'Global monthly precipitation estimates combining satellite and gauge observations.',
    scientific_question: 'How has precipitation changed over time across regional and global scales?',
    default_dataset_id: 'gpcp_monthly_v23',
    status: 'Available',
    datasets: [
      {
        id: 'gpcp_monthly_v23',
        variable_id: 'precipitation',
        product_name: 'Global Precipitation Climatology Project (GPCP) Monthly Analysis Product',
        provider: 'NOAA Physical Sciences Laboratory (PSL)',
        short_name: 'gpcp_monthly_v23',
        collection_id: '44',
        version: 'V2.3',
        doi: null,
        doi_status: 'Needs validation',
        native_variable_name: 'precip',
        long_name: 'Average Monthly Rate of Precipitation',
        var_desc: 'Precipitation',
        units: 'mm/day',
        displayed_unit_conversion: null,
        valid_range: [0.0, 100.0],
        fill_value: -9.96921e36,
        spatial_grid: 'regular_lat_lon',
        crs: 'EPSG:4326',
        cell_dimensions: [2.5, 2.5],
        spatial_coverage: 'Global (-90 to 90 lat, 0 to 357.5 lon)',
        spatial_resolution: '2.5° × 2.5°',
        temporal_resolution: 'monthly',
        start_date: '1979-01-01',
        latest_observation_date: '2026-10-01',
        last_catalogue_check: '2026-11-13T06:00:00Z',
        update_latency: null,
        update_latency_status: 'Needs validation',
        product_documentation: 'https://www.psl.noaa.gov/data/gridded/data.gpcp.html',
        citation: 'Adler et al. 2003',
        access_url: 'https://downloads.psl.noaa.gov/Datasets/gpcp/precip.mon.mean.nc',
        opendap_url: 'https://psl.noaa.gov/thredds/dodsC/Datasets/gpcp/precip.mon.mean.nc',
        terms_licensing: 'Acknowledge NOAA PSL',
        known_limitations: 'Do not mix versions invisibly.',
        no_data_mask_semantics: 'Decode to NaN',
        status: 'Available',
      },
    ],
  },
];

describe('ExplorePage (Page 1) Interactions and Store Write', () => {
  beforeEach(() => {
    useSession.setState({
      ...initialSessionState,
    });

    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/catalog/variables')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockVariables),
        });
      }
      return Promise.reject(new Error(`Unhandled fetch url: ${url}`));
    });
  });

  it('loads variable cards and shows preview available once data is loaded (SPEC 5.4)', async () => {
    render(
      <MemoryRouter initialEntries={['/explore']}>
        <ExplorePage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 3, name: 'Precipitation' })).toBeInTheDocument();
    });

    expect(screen.getByText(/Preview available once data is loaded/i)).toBeInTheDocument();
    expect(screen.getByText('2.5° × 2.5°')).toBeInTheDocument();
    expect(screen.getByText('1979-01-01')).toBeInTheDocument();
  });

  it('opens Details Drawer with metadata and unverified fields marked as Needs validation', async () => {
    render(
      <MemoryRouter initialEntries={['/explore']}>
        <ExplorePage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 3, name: 'Precipitation' })).toBeInTheDocument();
    });

    // Click Details button
    const detailsBtn = screen.getByRole('button', { name: /Details/i });
    fireEvent.click(detailsBtn);

    // Verify Drawer contents
    expect(screen.getByText('Dataset Specifications & Provenance')).toBeInTheDocument();
    expect(screen.getByText('Verification Audit')).toBeInTheDocument();
    expect(screen.getAllByText('2026-10-01').length).toBeGreaterThan(0);
    expect(screen.getByText('Last Catalogue Check:')).toBeInTheDocument();
    expect(screen.getByText('Close Drawer')).toBeInTheDocument();

    // Close drawer
    fireEvent.click(screen.getByText('Close Drawer'));
    expect(screen.queryByText('Dataset Specifications & Provenance')).not.toBeInTheDocument();
  });

  it('clicking Continue persists selection to Zustand store and navigates to Page 2 (/region)', async () => {
    render(
      <MemoryRouter initialEntries={['/explore']}>
        <Routes>
          <Route path="/explore" element={<ExplorePage />} />
          <Route path="/region" element={<RegionPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 3, name: 'Precipitation' })).toBeInTheDocument();
    });

    // Verify Selection Summary has default date 1990-01-01 and Monthly
    expect(screen.getByText(/1990-01-01 → Latest complete/i)).toBeInTheDocument();

    // Click Continue to Geographic Explorer
    const continueBtn = screen.getByRole('button', { name: /Continue to Geographic Explorer/i });
    fireEvent.click(continueBtn);

    // Verify navigation reached Page 2
    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 1, name: 'Page 2: Geographic Explorer' })).toBeInTheDocument();
    });

    // Verify Page 2 displays the persisted selection from store
    expect(screen.getByText(/Persisted Selection from Page 1/i)).toBeInTheDocument();
    expect(screen.getByText('gpcp_monthly_v23')).toBeInTheDocument();

    // Verify Zustand store directly
    const sessionState = useSession.getState();
    expect(sessionState.selectedVariables).toHaveLength(1);
    expect(sessionState.selectedVariables[0].variableId).toBe('precipitation');
    expect(sessionState.selectedVariables[0].datasetId).toBe('gpcp_monthly_v23');
    expect(sessionState.selectedVariables[0].datasetVersion).toBe('V2.3');
    expect(sessionState.selectedVariables[0].units).toBe('mm/day');
    expect(sessionState.dateRange.start).toBe('1990-01-01');
    expect(sessionState.dateRange.endMode).toBe('latest_complete');
    expect(sessionState.frequency).toBe('monthly');
  });
});
