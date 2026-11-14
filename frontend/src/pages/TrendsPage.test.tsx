import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { TrendsPage } from './TrendsPage';
import { useSession, initialSessionState } from '../store/session';
import * as trendsApi from '../api/trends';

// Mock Plotly component to render safely in jsdom and capture props for verification
vi.mock('react-plotly.js/factory', () => {
  return {
    default: () => {
      return function MockPlot(props: any) {
        return (
          <div data-testid="plotly-mock" data-props={JSON.stringify(props)}>
            <div data-testid="plotly-trace-count">{props.data?.length}</div>
            <div data-testid="plotly-connectgaps">
              {props.data?.find((t: any) => t.connectgaps !== undefined)?.connectgaps ? 'true' : 'false'}
            </div>
            <div data-testid="plotly-points-count">{props.data?.[props.data.length - 1]?.x?.length}</div>
          </div>
        );
      };
    },
  };
});

describe('TrendsPage (Page 3 - Trend Analysis)', () => {
  const mockSeriesData: trendsApi.TimeSeriesResult = {
    job_id: 'job_test123',
    run_id: 'run_test123',
    series_id: 'series_test123',
    status: 'completed',
    dataset: {
      id: 'gpcp_monthly_v23',
      version: 'v2.3',
      units: 'mm',
      source: 'https://downloads.psl.noaa.gov/Datasets/gpcp/precip.mon.mean.nc',
      variable: 'precipitation',
    },
    coverage: {
      requested_start: '2020-01-01',
      actual_start: '2020-01-01',
      actual_end: '2020-12-01',
      valid_steps: 11,
      expected_steps: 12,
      completeness_pct: 91.67,
    },
    series_url: '/api/results/series/series_test123',
    points: [
      {
        date: '2020-01-01',
        value: 100.0,
        units: 'mm',
        is_missing: false,
        flags: [],
        fitted_ols: 101.2,
        ols_ci_lower: 95.0,
        ols_ci_upper: 107.4,
        sens_line: 101.0,
        moving_avg: 100.5,
      },
      {
        date: '2020-02-01',
        value: 105.0,
        units: 'mm',
        is_missing: false,
        flags: [],
        fitted_ols: 104.2,
        ols_ci_lower: 98.2,
        ols_ci_upper: 110.2,
        sens_line: 104.0,
        moving_avg: 103.0,
      },
      {
        date: '2020-03-01',
        value: 110.0,
        units: 'mm',
        is_missing: false,
        flags: [],
        fitted_ols: 107.2,
        ols_ci_lower: 101.5,
        ols_ci_upper: 112.9,
        sens_line: 107.0,
        moving_avg: 106.0,
      },
      {
        date: '2020-04-01',
        value: null, // REAL MISSING MONTH GAP
        units: 'mm',
        is_missing: true,
        flags: ['missing_data'],
        fitted_ols: 110.2,
        ols_ci_lower: 104.0,
        ols_ci_upper: 116.4,
        sens_line: 110.0,
        moving_avg: null,
      },
      {
        date: '2020-05-01',
        value: 118.0,
        units: 'mm',
        is_missing: false,
        flags: [],
        fitted_ols: 113.2,
        ols_ci_lower: 107.0,
        ols_ci_upper: 119.4,
        sens_line: 113.0,
        moving_avg: 112.0,
      },
      {
        date: '2020-06-01',
        value: 122.0,
        units: 'mm',
        is_missing: false,
        flags: [],
        fitted_ols: 116.2,
        ols_ci_lower: 110.0,
        ols_ci_upper: 122.4,
        sens_line: 116.0,
        moving_avg: 115.0,
      },
      {
        date: '2020-07-01',
        value: 128.0,
        units: 'mm',
        is_missing: false,
        flags: [],
        fitted_ols: 119.2,
        ols_ci_lower: 113.0,
        ols_ci_upper: 125.4,
        sens_line: 119.0,
        moving_avg: 118.0,
      },
      {
        date: '2020-08-01',
        value: 130.0,
        units: 'mm',
        is_missing: false,
        flags: [],
        fitted_ols: 122.2,
        ols_ci_lower: 115.5,
        ols_ci_upper: 128.9,
        sens_line: 122.0,
        moving_avg: 121.0,
      },
      {
        date: '2020-09-01',
        value: 135.0,
        units: 'mm',
        is_missing: false,
        flags: [],
        fitted_ols: 125.2,
        ols_ci_lower: 118.0,
        ols_ci_upper: 132.4,
        sens_line: 125.0,
        moving_avg: 124.0,
      },
      {
        date: '2020-10-01',
        value: 140.0,
        units: 'mm',
        is_missing: false,
        flags: [],
        fitted_ols: 128.2,
        ols_ci_lower: 121.0,
        ols_ci_upper: 135.4,
        sens_line: 128.0,
        moving_avg: 127.0,
      },
      {
        date: '2020-11-01',
        value: 144.0,
        units: 'mm',
        is_missing: false,
        flags: [],
        fitted_ols: 131.2,
        ols_ci_lower: 123.5,
        ols_ci_upper: 138.9,
        sens_line: 131.0,
        moving_avg: 130.0,
      },
      {
        date: '2020-12-01',
        value: 150.0,
        units: 'mm',
        is_missing: false,
        flags: [],
        fitted_ols: 134.2,
        ols_ci_lower: 126.0,
        ols_ci_upper: 142.4,
        sens_line: 134.0,
        moving_avg: 133.0,
      },
    ],
    summary: {
      trend_direction: 'increasing',
      slope_method_displayed: 'linear_regression',
      rate_of_change: 36.5,
      rate_of_change_units: 'mm/year',
      mean: 125.18,
      estimated_total_change: 36.5,
      elapsed_years: 1.0,
      valid_n: 11,
      expected_n: 12,
      completeness: {
        valid: 11,
        expected: 12,
        pct: 91.67,
        denominator_description: 'Expected 12 monthly intervals from 2020-01-01 to 2020-12-01',
      },
      ols: {
        slope_per_year: 36.5,
        intercept: 101.2,
        p_value: 0.0001,
        r_squared: 0.98,
        std_err: 1.2,
        ci_lower_slope: 33.8,
        ci_upper_slope: 39.2,
        trend_direction: 'increasing',
      },
      sens_slope: {
        slope_per_year: 36.0,
        intercept: 101.0,
        ci_lower: 33.5,
        ci_upper: 38.8,
        confidence_level: 0.95,
        trend_direction: 'increasing',
      },
      mann_kendall: {
        trend: 'increasing',
        p_value: 0.0005,
        z: 3.48,
        tau: 0.95,
        s: 55,
        var_s: 230,
        significant: true,
      },
      seasonal_mann_kendall: null,
      modified_mann_kendall: {
        trend: 'increasing',
        p_value: 0.0012,
        z: 3.12,
        tau: 0.95,
        s: 55,
        var_s: 280,
        significant: true,
        method: 'hamed_rao',
      },
      alpha: 0.05,
      min_data_points: 10,
      moving_average_window: 12,
    },
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
        label: 'Germany (admin_0)',
        type: 'admin',
        geometry: {
          type: 'Polygon',
          coordinates: [[[5.8, 47.2], [15.0, 47.2], [15.0, 55.0], [5.8, 55.0], [5.8, 47.2]]],
        },
        crs: 'EPSG:4326',
        areaKm2: 357022,
      },
      dateRange: {
        start: '2020-01-01',
        endMode: 'latest_complete',
      },
      frequency: 'monthly',
    });

    vi.spyOn(trendsApi, 'executeTimeSeriesAnalysis').mockResolvedValue(mockSeriesData);
  });

  it('asserts that chart, table, and metrics all derive from one series object', async () => {
    render(
      <MemoryRouter>
        <TrendsPage />
      </MemoryRouter>
    );

    // Wait for analysis to load
    await waitFor(() => {
      expect(screen.getByText('Page 3: Trend Analysis')).toBeInTheDocument();
      expect(trendsApi.executeTimeSeriesAnalysis).toHaveBeenCalledTimes(1);
    });

    // 1. Chart verification: Plotly mock received points from mockSeriesData
    const plotlyMock = screen.getByTestId('plotly-mock');
    expect(plotlyMock).toBeInTheDocument();
    expect(screen.getByTestId('plotly-connectgaps').textContent).toBe('false');
    expect(screen.getByTestId('plotly-points-count').textContent).toBe('12');

    // 2. Metrics verification: Summary metrics derived from mockSeriesData.summary
    expect(screen.getByText('Increasing Trend')).toBeInTheDocument();
    expect(screen.getByText('+36.5 mm/year')).toBeInTheDocument();
    expect(screen.getByText('125.18 mm')).toBeInTheDocument();
    expect(screen.getByText('91.67%')).toBeInTheDocument();
    expect(screen.getByText(/11 valid \/ 12 expected intervals/)).toBeInTheDocument();

    // 3. Table verification: Click to expand data table
    const expandTableBtn = screen.getByText(/Plotted Data Table/);
    fireEvent.click(expandTableBtn);

    // Check that missing month (2020-04-01) is displayed with 'Missing' and 'NaN (gap)'
    expect(screen.getByText('2020-04-01')).toBeInTheDocument();
    expect(screen.getByText('NaN (gap)')).toBeInTheDocument();

    // Valid month check
    expect(screen.getByText('2020-01-01')).toBeInTheDocument();
    expect(screen.getByText('100.00')).toBeInTheDocument();
  });

  it('switching aggregation recalculates and calls backend with updated aggregation', async () => {
    render(
      <MemoryRouter>
        <TrendsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(trendsApi.executeTimeSeriesAnalysis).toHaveBeenCalledTimes(1);
    });

    // Click 'Annual' button
    const annualBtn = screen.getByRole('button', { name: /^annual$/i });
    fireEvent.click(annualBtn);

    await waitFor(() => {
      // Second call triggered with aggregation="annual"
      expect(trendsApi.executeTimeSeriesAnalysis).toHaveBeenCalledTimes(2);
      expect(trendsApi.executeTimeSeriesAnalysis).toHaveBeenLastCalledWith(
        expect.objectContaining({
          aggregation: 'annual',
        })
      );
    });
  });

  it('shows stale result banner when inputs change and allows recalculating', async () => {
    render(
      <MemoryRouter>
        <TrendsPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(trendsApi.executeTimeSeriesAnalysis).toHaveBeenCalledTimes(1);
    });

    // Change start date to trigger stale state
    const startDateInput = screen.getByDisplayValue('2020-01-01');
    fireEvent.change(startDateInput, { target: { value: '2015-01-01' } });

    // Stale result banner should appear
    expect(screen.getByText(/Result shown is from previous calculation/)).toBeInTheDocument();

    // Click recalculate button on the banner
    const recalcBtn = screen.getByRole('button', { name: /recalculate/i });
    fireEvent.click(recalcBtn);

    await waitFor(() => {
      expect(trendsApi.executeTimeSeriesAnalysis).toHaveBeenCalledTimes(2);
      expect(trendsApi.executeTimeSeriesAnalysis).toHaveBeenLastCalledWith(
        expect.objectContaining({
          start_date: '2015-01-01',
        })
      );
    });
  });
});
