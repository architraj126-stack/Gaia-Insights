import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { SignificancePage } from './SignificancePage';
import { useSession, initialSessionState } from '../store/session';
import * as significanceApi from '../api/significance';

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
      tileLayer: vi.fn(() => ({ addTo: vi.fn().mockReturnThis(), setUrl: vi.fn() })),
      geoJSON: vi.fn(() => ({
        addTo: vi.fn().mockReturnThis(),
        getBounds: vi.fn(() => ({
          isValid: () => true,
        })),
        remove: vi.fn(),
      })),
      imageOverlay: vi.fn(() => ({
        addTo: vi.fn().mockReturnThis(),
        setOpacity: vi.fn(),
        remove: vi.fn(),
      })),
      latLngBounds: vi.fn(() => ({
        isValid: () => true,
      })),
    },
  };
});

describe('SignificancePage (Page 5 - Significance & Reports)', () => {
  const mockSignificanceResult: significanceApi.SignificanceAnalysisResult = {
    run_id: 'sig_test_12345',
    status: 'completed',
    regional: {
      test_name: 'Seasonal Mann-Kendall with Hamed-Rao Variance Correction',
      null_hypothesis: 'There is no monotonic trend in the seasonal series over time.',
      test_statistic: 2.854,
      raw_p_value: 0.0043,
      sens_slope: 1.45,
      ci_lower: 0.42,
      ci_upper: 2.68,
      sample_size: 420,
      alpha: 0.05,
      ci_level: 0.95,
      lag1_autocorrelation: 0.284,
      autocorrelation_handling: 'hamed_rao',
      choice_documentation: 'Positive lag-1 autocorrelation detected (r1 = 0.2840 > 0.10). Hamed-Rao variance inflation applied.',
      interpretation: 'The regional series exhibits a statistically significant monotonic trend (p = 0.0043 < 0.05). Note that statistical significance does not imply large environmental magnitude or a causal mechanism.',
      is_significant: true,
    },
    spatial: {
      overlay_url: '/api/analysis/significance/sig_test_12345/overlay.png',
      geotiff_url: '/api/analysis/significance/sig_test_12345/geotiff',
      bounds: [
        [-10.0, -10.0],
        [10.0, 10.0],
      ],
      legend: {
        title: 'Statistical Significance Classes (SPEC 10.4)',
        p_value_mode: 'Benjamini-Hochberg FDR Adjusted',
        alpha: 0.05,
        classes: [
          {
            code: 1,
            label: 'Significant Increase',
            badge_symbol: '+',
            pattern: 'dots',
            color: '#0284c7',
            count: 34,
            description: 'Positive slope meeting evidence threshold after multiple testing correction.',
          },
          {
            code: 2,
            label: 'Significant Decrease',
            badge_symbol: '−',
            pattern: 'stripes',
            color: '#ea580c',
            count: 12,
            description: 'Negative slope meeting evidence threshold after multiple testing correction.',
          },
          {
            code: 3,
            label: 'Not Significant',
            badge_symbol: 'o',
            pattern: 'neutral',
            color: '#94a3b8',
            count: 154,
            description: 'Valid estimate exists but does not meet significance threshold.',
          },
          {
            code: 4,
            label: 'Insufficient Data',
            badge_symbol: '?',
            pattern: 'crosshatch',
            color: '#facc15',
            count: 0,
            description: 'Fewer than minimum required valid annual observations.',
          },
          {
            code: 0,
            label: 'Not Covered',
            badge_symbol: 'x',
            pattern: 'blank',
            color: '#334155',
            count: 0,
            description: 'Outside dataset spatial boundary or polygon mask.',
          },
        ],
      },
      class_counts: {
        significant_increase: 34,
        significant_decrease: 12,
        not_significant: 154,
        insufficient_data: 0,
        not_covered: 0,
      },
      min_valid_years: 10,
      fdr_correction: true,
      alpha: 0.05,
    },
    provenance: {
      run_id: 'sig_test_12345',
      dataset_id: 'gpcp_monthly_v23',
      dataset_version: 'v2.3',
    },
    warnings: [],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    useSession.setState({
      ...initialSessionState,
      page3ResultId: 'series_p3_111',
      page4ResultId: 'change_p4_222',
      region: {
        label: 'Northern Africa',
        type: 'polygon',
        geometry: {
          type: 'Polygon',
          coordinates: [
            [
              [-10.0, 10.0],
              [30.0, 10.0],
              [30.0, 35.0],
              [-10.0, 35.0],
              [-10.0, 10.0],
            ],
          ],
        },
        crs: 'EPSG:4326',
      },
      selectedVariables: [
        {
          variableId: 'precipitation',
          datasetId: 'gpcp_monthly_v23',
          datasetVersion: 'v2.3',
          fieldName: 'precip',
          units: 'mm/month',
        },
      ],
    });

    vi.spyOn(significanceApi, 'executeSignificanceAnalysis').mockResolvedValue(mockSignificanceResult);
    vi.spyOn(significanceApi, 'reclassifySignificance').mockResolvedValue(mockSignificanceResult);
    vi.spyOn(significanceApi, 'fetchSignificanceResult').mockResolvedValue(mockSignificanceResult);
  });

  it('renders Step 5, title, settings, and traces to stored run ID', async () => {
    render(
      <MemoryRouter>
        <SignificancePage />
      </MemoryRouter>
    );

    // Initial load executes analysis
    await waitFor(() => {
      expect(significanceApi.executeSignificanceAnalysis).toHaveBeenCalledTimes(1);
    });

    expect(screen.getByText('Significance & Evidence Evaluation')).toBeInTheDocument();
    expect(screen.getByText(/run: sig_test_12345/i)).toBeInTheDocument();
    expect(screen.getByText(/Recommended Method/i)).toBeInTheDocument();
  });

  it('renders the 5 accessible classes with symbol badges and counts (not color alone)', async () => {
    render(
      <MemoryRouter>
        <SignificancePage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('significance-map-legend')).toBeInTheDocument();
    });

    // Check legend title
    expect(screen.getByText('Statistical Significance Classes (SPEC 10.4)')).toBeInTheDocument();

    // Check symbol badges and labels
    expect(screen.getByText('Significant Increase')).toBeInTheDocument();
    expect(screen.getByText('+')).toBeInTheDocument();

    expect(screen.getByText('Significant Decrease')).toBeInTheDocument();
    expect(screen.getByText('−')).toBeInTheDocument();

    expect(screen.getByText('Not Significant')).toBeInTheDocument();
    expect(screen.getByText('o')).toBeInTheDocument();

    expect(screen.getByText('Insufficient Data')).toBeInTheDocument();
    expect(screen.getByText('?')).toBeInTheDocument();

    expect(screen.getByText('Not Covered')).toBeInTheDocument();
    expect(screen.getByText('x')).toBeInTheDocument();
  });

  it('indicates whether map displays Benjamini-Hochberg FDR Adjusted or Raw p-values', async () => {
    render(
      <MemoryRouter>
        <SignificancePage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('legend-p-value-mode')).toBeInTheDocument();
    });

    expect(screen.getByTestId('legend-p-value-mode')).toHaveTextContent('Benjamini-Hochberg FDR Adjusted');
  });

  it('switches between Spatial Significance Map and Regional Trend Test views', async () => {
    render(
      <MemoryRouter>
        <SignificancePage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('view-regional-button')).toBeInTheDocument();
    });

    // Switch to Regional view
    fireEvent.click(screen.getByTestId('view-regional-button'));

    expect(screen.getByText('Regional Non-Parametric Trend Assessment')).toBeInTheDocument();
    expect(screen.getAllByText(/Seasonal Mann-Kendall with Hamed-Rao/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/There is no monotonic trend in the seasonal series/i)).toBeInTheDocument();
    expect(screen.getByTestId('regional-p-value')).toHaveTextContent('0.0043');

    // Switch back to Spatial view
    fireEvent.click(screen.getByTestId('view-spatial-button'));
    expect(screen.getByTestId('significance-map-container')).toBeInTheDocument();
  });

  it('displays SPEC 10.5 & 10.6 plain-language interpretations and cautions', async () => {
    render(
      <MemoryRouter>
        <SignificancePage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Plain-Language Reading/i)).toBeInTheDocument();
    });

    // Cautions
    expect(screen.getByText(/Interpretation Cautions/i)).toBeInTheDocument();
    expect(screen.getByText(/the probability that the null hypothesis is true/i)).toBeInTheDocument();
    expect(screen.getByText(/large environmental importance/i)).toBeInTheDocument();
    expect(screen.getAllByText(/a causal mechanism/i).length).toBeGreaterThanOrEqual(1);
  });

  it('triggers fast reclassification when toggling alpha or FDR without full data re-fetch', async () => {
    render(
      <MemoryRouter>
        <SignificancePage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/run: sig_test_12345/i)).toBeInTheDocument();
    });

    // Click alpha = 0.01 button
    const alpha001Btn = screen.getByText('α = 0.01');
    fireEvent.click(alpha001Btn);

    await waitFor(() => {
      expect(significanceApi.reclassifySignificance).toHaveBeenCalledWith(
        'sig_test_12345',
        0.01,
        true
      );
    });

    // Toggle FDR checkbox
    const fdrCheckbox = screen.getByLabelText(/Benjamini-Hochberg FDR/i);
    fireEvent.click(fdrCheckbox);

    await waitFor(() => {
      expect(significanceApi.reclassifySignificance).toHaveBeenCalledWith(
        'sig_test_12345',
        0.01,
        false
      );
    });
  });

  it('expands data quality and methodology drawer', async () => {
    render(
      <MemoryRouter>
        <SignificancePage />
      </MemoryRouter>
    );

    const toggleBtn = screen.getByTestId('toggle-methodology-button');
    fireEvent.click(toggleBtn);

    expect(screen.getByText(/Dataset & Coverage Rules/i)).toBeInTheDocument();
    expect(screen.getByText(/Autocorrelation & Serial Dependence/i)).toBeInTheDocument();
    expect(screen.getByText(/Spatial Multiple-Testing Limitations/i)).toBeInTheDocument();
  });
});
