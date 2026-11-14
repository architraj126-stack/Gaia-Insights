import { describe, it, expect, beforeEach } from 'vitest';
import { useSession, invalidateDownstreamResults, initialSessionState } from './session';

describe('useSession store and invalidation rules (SPEC 13.3)', () => {
  beforeEach(() => {
    // Reset store before each test
    useSession.setState({
      ...initialSessionState,
      page3ResultId: 'result-p3-123',
      page4ResultId: 'result-p4-456',
      page5ResultId: 'result-p5-789',
    });
  });

  it('has initial result IDs set up in test harness', () => {
    const state = useSession.getState();
    expect(state.page3ResultId).toBe('result-p3-123');
    expect(state.page4ResultId).toBe('result-p4-456');
    expect(state.page5ResultId).toBe('result-p5-789');
  });

  it('invalidateDownstreamResults helper clears all downstream results', () => {
    const input = {
      sessionId: 'sess-1',
      page3ResultId: 'p3',
      page4ResultId: 'p4',
      page5ResultId: 'p5',
    };
    const output = invalidateDownstreamResults(input);
    expect(output.page3ResultId).toBeUndefined();
    expect(output.page4ResultId).toBeUndefined();
    expect(output.page5ResultId).toBeUndefined();
    expect(output.sessionId).toBe('sess-1');
  });

  it('changing dataset/version invalidates Page 3, 4, 5 results (SPEC 13.3)', () => {
    useSession.getState().setSelectedVariables([
      {
        variableId: 'precip',
        datasetId: 'gpcp',
        datasetVersion: 'V2.3',
        fieldName: 'precip',
        units: 'mm/day',
      },
    ]);

    const state = useSession.getState();
    expect(state.selectedVariables).toHaveLength(1);
    expect(state.selectedVariables[0].datasetId).toBe('gpcp');
    expect(state.page3ResultId).toBeUndefined();
    expect(state.page4ResultId).toBeUndefined();
    expect(state.page5ResultId).toBeUndefined();
  });

  it('changing dateRange invalidates downstream results (SPEC 13.3)', () => {
    useSession.getState().setDateRange({
      start: '2000-01-01',
      endMode: 'custom',
      end: '2020-12-31',
    });

    const state = useSession.getState();
    expect(state.dateRange.start).toBe('2000-01-01');
    expect(state.page3ResultId).toBeUndefined();
    expect(state.page4ResultId).toBeUndefined();
    expect(state.page5ResultId).toBeUndefined();
  });

  it('changing frequency (aggregation) invalidates downstream results (SPEC 13.3)', () => {
    useSession.getState().setFrequency('annual');

    const state = useSession.getState();
    expect(state.frequency).toBe('annual');
    expect(state.page3ResultId).toBeUndefined();
    expect(state.page4ResultId).toBeUndefined();
    expect(state.page5ResultId).toBeUndefined();
  });

  it('changing region invalidates downstream results (SPEC 13.3)', () => {
    useSession.getState().setRegion({
      label: 'Sahel',
      type: 'rectangle',
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [-18, 10],
            [30, 10],
            [30, 20],
            [-18, 20],
            [-18, 10],
          ],
        ],
      },
      crs: 'EPSG:4326',
      areaKm2: 4500000,
    });

    const state = useSession.getState();
    expect(state.region?.label).toBe('Sahel');
    expect(state.page3ResultId).toBeUndefined();
    expect(state.page4ResultId).toBeUndefined();
    expect(state.page5ResultId).toBeUndefined();
  });

  it('setting result IDs independently updates state without clearing prior inputs', () => {
    useSession.setState({
      ...initialSessionState,
      selectedVariables: [
        {
          variableId: 'precip',
          datasetId: 'gpcp',
          datasetVersion: 'V2.3',
          fieldName: 'precip',
          units: 'mm/day',
        },
      ],
      page3ResultId: undefined,
      page4ResultId: undefined,
      page5ResultId: undefined,
    });

    useSession.getState().setPage3ResultId('new-p3-result');
    expect(useSession.getState().page3ResultId).toBe('new-p3-result');
    expect(useSession.getState().selectedVariables).toHaveLength(1);

    useSession.getState().setPage4ResultId('new-p4-result');
    expect(useSession.getState().page4ResultId).toBe('new-p4-result');

    useSession.getState().setPage5ResultId('new-p5-result');
    expect(useSession.getState().page5ResultId).toBe('new-p5-result');
  });

  it('resetSession resets state to defaults with new sessionId', () => {
    useSession.getState().resetSession();
    const state = useSession.getState();
    expect(state.selectedVariables).toEqual([]);
    expect(state.region).toBeNull();
    expect(state.page3ResultId).toBeUndefined();
    expect(state.page4ResultId).toBeUndefined();
    expect(state.page5ResultId).toBeUndefined();
    expect(state.sessionId).toContain('session-');
  });

  it('correctly persists Page 1 selection (SPEC 5.5) with dataset, version, dateRange and frequency', () => {
    useSession.getState().resetSession();

    // Simulate Page 1 Continue write
    useSession.getState().setSelectedVariables([
      {
        variableId: 'precipitation',
        datasetId: 'gpcp_monthly_v23',
        datasetVersion: 'V2.3',
        fieldName: 'precip',
        units: 'mm/day',
        spatialCoverage: 'Global (-90 to 90 lat, 0 to 357.5 lon)',
        citation: 'Adler et al. 2003',
      },
    ]);

    useSession.getState().setDateRange({
      start: '1990-01-01',
      endMode: 'latest_complete',
    });

    useSession.getState().setFrequency('monthly');

    const state = useSession.getState();
    expect(state.selectedVariables).toHaveLength(1);
    expect(state.selectedVariables[0]).toEqual({
      variableId: 'precipitation',
      datasetId: 'gpcp_monthly_v23',
      datasetVersion: 'V2.3',
      fieldName: 'precip',
      units: 'mm/day',
      spatialCoverage: 'Global (-90 to 90 lat, 0 to 357.5 lon)',
      citation: 'Adler et al. 2003',
    });
    expect(state.dateRange).toEqual({
      start: '1990-01-01',
      endMode: 'latest_complete',
    });
    expect(state.frequency).toBe('monthly');
  });
});
