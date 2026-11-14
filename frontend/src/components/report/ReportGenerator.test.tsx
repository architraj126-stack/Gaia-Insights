import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ReportGenerator } from './ReportGenerator';
import * as reportsApi from '../../api/reports';

describe('ReportGenerator (SPEC 10.7, 10.8, 17.3)', () => {
  const mockReportResponse: reportsApi.ReportResponse = {
    report_id: 'rep_test_9999',
    title: 'Earth Science Explorer — Precipitation Analysis for Western Europe',
    status: 'completed',
    created_at: '2026-11-13T19:00:00Z',
    sections_enabled: {
      executive_summary: true,
      dataset_and_study_area: true,
      historical_trends: true,
      change_detection: true,
      statistical_significance: true,
      data_quality: true,
      methodology_and_references: true,
    },
    executive_summary: {
      paragraphs: [
        'Historical trend analysis of Precipitation from 1990 to 2025 reveals a baseline regional mean of 69.78 mm/month.',
        'Spatial change detection identifies an area-weighted mean change of +34.62 mm/year.',
        'Inferential hypothesis testing evaluates the observed trend as statistically significant (p = 0.0018).',
      ],
      key_metrics: {
        regional_mean: '69.78 mm/month',
        sen_slope: '+0.250 mm/year',
        area_weighted_mean_change: '+34.62 mm/year',
        increasing_area_share: '68.4%',
        significance_p_value: '0.0018',
      },
    },
    dataset_info: {
      dataset_id: 'gpcp_monthly_v23',
      dataset_version: 'v2.3',
      variable: 'Precipitation',
      units: 'mm',
      provider: 'NOAA PSL / NASA GSFC',
      doi: '10.7289/V56971M6',
    },
    study_area: {
      label: 'Western Europe',
      bounds: [[40.0, -10.0], [55.0, 15.0]],
    },
    trends_summary: {
      mean: 69.775,
      slope: 0.25,
      sens_slope: 0.25,
      units: 'mm/month',
    },
    change_summary: {
      area_weighted_mean_change: 34.62,
      share_increasing_pct: 68.4,
    },
    significance_info: {
      regional: {
        raw_p_value: 0.0018,
      },
      spatial: {
        class_counts: {
          significant_increase: 14,
        },
      },
    },
    downloads: {
      pdf_url: '/api/reports/rep_test_9999/pdf',
      csv_url: '/api/reports/rep_test_9999/csv',
      chart_png_url: '/api/reports/rep_test_9999/chart.png',
      change_geotiff_url: '/api/analysis/change-map/run_c456/geotiff',
      significance_geotiff_url: '/api/analysis/significance/sig_p5_123/geotiff',
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(reportsApi, 'generateReport').mockResolvedValue(mockReportResponse);
  });

  it('renders with all 7 default sections enabled', () => {
    render(
      <ReportGenerator
        seriesId="test_series"
        changeRunId="test_change"
        significanceRunId="test_sig"
        regionLabel="Western Europe"
      />
    );

    expect(screen.getByText('Scientific Audit Report Generator')).toBeInTheDocument();
    expect(screen.getByText('1. Executive Summary')).toBeInTheDocument();
    expect(screen.getByText('2. Dataset and Study Area')).toBeInTheDocument();
    expect(screen.getByText('3. Historical Trend Analysis')).toBeInTheDocument();
    expect(screen.getByText('4. Spatial Change Detection')).toBeInTheDocument();
    expect(screen.getByText('5. Statistical Significance')).toBeInTheDocument();
    expect(screen.getByText('6. Data Quality & Limitations')).toBeInTheDocument();
    expect(screen.getByText('7. Methodology & References')).toBeInTheDocument();
  });

  it('toggles sections on click', () => {
    render(
      <ReportGenerator
        seriesId="test_series"
        changeRunId="test_change"
        significanceRunId="test_sig"
      />
    );

    const trendsToggle = screen.getByTestId('section-toggle-historical_trends');
    fireEvent.click(trendsToggle);

    // Click Compile button and verify toggled payload
    const compileBtn = screen.getByTestId('generate-report-button');
    fireEvent.click(compileBtn);

    expect(reportsApi.generateReport).toHaveBeenCalledWith(
      expect.objectContaining({
        sections: expect.objectContaining({
          historical_trends: false,
          executive_summary: true,
        }),
      })
    );
  });

  it('generates report and surfaces download buttons and live preview', async () => {
    render(
      <ReportGenerator
        seriesId="test_series"
        changeRunId="test_change"
        significanceRunId="test_sig"
      />
    );

    const compileBtn = screen.getByTestId('generate-report-button');
    fireEvent.click(compileBtn);

    await waitFor(() => {
      expect(screen.getByTestId('report-downloads-panel')).toBeInTheDocument();
    });

    // Check download buttons
    expect(screen.getByTestId('download-pdf-button')).toHaveAttribute('href', '/api/reports/rep_test_9999/pdf');
    expect(screen.getByTestId('download-csv-button')).toHaveAttribute('href', '/api/reports/rep_test_9999/csv');

    // Check preview content
    expect(screen.getByTestId('report-preview-panel')).toBeInTheDocument();
    expect(screen.getByText(/DOI: 10.7289\/V56971M6/i)).toBeInTheDocument();
    expect(screen.getByText(/Historical trend analysis of Precipitation from 1990 to 2025/i)).toBeInTheDocument();
    expect(screen.getByText('69.78 mm/month')).toBeInTheDocument();
    expect(screen.getByText('+34.62 mm/yr')).toBeInTheDocument();
  });

  it('displays error message when report compilation fails', async () => {
    vi.spyOn(reportsApi, 'generateReport').mockRejectedValue(
      new Error('Dataset version mismatch: Page 3 uses v2.3 while Page 4 uses v3.0.')
    );

    render(
      <ReportGenerator
        seriesId="test_series"
        changeRunId="test_change"
        significanceRunId="test_sig"
      />
    );

    const compileBtn = screen.getByTestId('generate-report-button');
    fireEvent.click(compileBtn);

    await waitFor(() => {
      expect(screen.getByText(/Dataset version mismatch/i)).toBeInTheDocument();
    });
  });
});
