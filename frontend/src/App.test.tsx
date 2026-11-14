import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MemoryRouter } from 'react-router-dom';
import { AppRoutes } from './App';

describe('App Route Navigation and Page Rendering', () => {
  beforeEach(() => {
    // Mock global fetch for catalog endpoints
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/catalog/variables')) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve([
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
                    latest_observation_date: null,
                    latest_observation_status: 'Not yet checked',
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
            ]),
        });
      }
      if (url.includes('/api/analysis/timeseries')) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              status: 'completed',
              series_id: 'series_mock',
              dataset: { units: 'mm' },
              coverage: { actual_end: '2026-10-01', valid_steps: 12, expected_steps: 12, completeness_pct: 100 },
              points: [],
              summary: {
                trend_direction: 'no clear trend',
                rate_of_change: 0,
                mean: 100,
                completeness: { valid: 12, expected: 12, pct: 100, denominator_description: '' },
                ols: {},
                sens_slope: {},
                mann_kendall: {},
              },
            }),
        });
      }
      if (url.includes('/api/analysis/change-map')) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              status: 'completed',
              run_id: 'run_mock',
              units: 'mm/year',
              metric: 'absolute',
              spatial_summary: {
                area_weighted_mean_change: 15.2,
                share_increasing_pct: 60.0,
                share_decreasing_pct: 35.0,
                share_no_change_pct: 5.0,
                highest_change: { value: 50.0, lat: 10, lon: 10 },
                lowest_change: { value: -30.0, lat: -10, lon: -10 },
                valid_area_km2: 1000000,
                total_region_area_km2: 1100000,
                nodata_area_km2: 100000,
                nodata_share_pct: 9.09,
              },
              legend: {
                colormap: 'RdBu_r',
                symmetric_zero: 0,
                min_val: -100,
                max_val: 100,
                units: 'mm/year',
                thresholds: [-100, -50, 0, 50, 100],
                colors: ['#000', '#333', '#fff', '#f00', '#900'],
                no_data_swatch: { color: '#999', label: 'No Data' },
              },
              bounds: [[-10, -10], [10, 10]],
              overlay_url: '/overlay.png',
              geotiff_url: '/change.tif',
              provenance: {},
              warnings: [],
            }),
        });
      }
      return Promise.reject(new Error(`Unhandled fetch url: ${url}`));
    });
  });

  it('renders Homepage per SPEC 4 with hero, headline, buttons, and sections', async () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <AppRoutes />
      </MemoryRouter>
    );

    // Hero headline and description
    expect(screen.getByRole('heading', { level: 1, name: /Understand Our/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Start Exploring/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Learn More/i })).toBeInTheDocument();

    // Four "What you can do" cards (SPEC 4.3)
    expect(screen.getByRole('heading', { level: 2, name: 'What You Can Do' })).toBeInTheDocument();
    expect(screen.getAllByRole('heading', { level: 3, name: 'Explore Data' }).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByRole('heading', { level: 3, name: 'Analyse Trends' }).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByRole('heading', { level: 3, name: 'Detect Changes' }).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole('heading', { level: 3, name: 'Generate Reports' })).toBeInTheDocument();

    // Five-step How It Works section (SPEC 4.4)
    expect(screen.getByRole('heading', { level: 2, name: 'How It Works' })).toBeInTheDocument();

    // Final CTA and footer
    expect(screen.getByRole('heading', { level: 2, name: "Discover the Story Behind Earth's Data." })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Begin Your Analysis/i })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 3, name: 'Precipitation' })).toBeInTheDocument();
    });
  });

  it('renders Page 1: Data Explorer per SPEC 5 with search, filters, and configuration', async () => {
    render(
      <MemoryRouter initialEntries={['/explore']}>
        <AppRoutes />
      </MemoryRouter>
    );

    expect(screen.getByRole('heading', { level: 1, name: 'Data Explorer' })).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Search variable or dataset/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Atmosphere' })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 3, name: 'Precipitation' })).toBeInTheDocument();
    });
  });

  it('renders Page 2: Geographic Explorer at "/region" with loaded selection panel', () => {
    render(
      <MemoryRouter initialEntries={['/region']}>
        <AppRoutes />
      </MemoryRouter>
    );

    expect(screen.getByRole('heading', { level: 1, name: 'Page 2: Geographic Explorer' })).toBeInTheDocument();
    expect(screen.getByText(/Persisted Selection from Page 1/i)).toBeInTheDocument();
  });

  it('renders Page 3: Trend Analysis at "/trends"', () => {
    render(
      <MemoryRouter initialEntries={['/trends']}>
        <AppRoutes />
      </MemoryRouter>
    );

    expect(screen.getByRole('heading', { level: 1, name: /Page 3: Trend Analysis/i })).toBeInTheDocument();
  });

  it('renders Page 4: Change Detection at "/changes"', () => {
    render(
      <MemoryRouter initialEntries={['/changes']}>
        <AppRoutes />
      </MemoryRouter>
    );

    expect(screen.getByRole('heading', { level: 1, name: /Page 4: Change Detection/i })).toBeInTheDocument();
  });

  it('renders Page 5: Significance & Evidence Evaluation at "/significance"', () => {
    render(
      <MemoryRouter initialEntries={['/significance']}>
        <AppRoutes />
      </MemoryRouter>
    );

    expect(
      screen.getByRole('heading', { level: 1, name: /Significance & Evidence Evaluation/i })
    ).toBeInTheDocument();
  });
});
