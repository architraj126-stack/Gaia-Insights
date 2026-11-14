import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { Geometry } from 'geojson';

export interface SelectedVariable {
  variableId: string;
  datasetId: string;
  datasetVersion: string;
  fieldName: string;
  units: string;
  spatialCoverage?: string;
  citation?: string;
  caveat?: string;
}

export interface DateRange {
  start: string; // default 1990-01-01
  endMode: 'latest_complete' | 'custom';
  end?: string;
}

export type AnalysisFrequency = 'monthly' | 'annual' | 'seasonal';

export interface AnalysisRegion {
  label: string;
  type: 'admin' | 'polygon' | 'rectangle' | 'point_buffer';
  geometry: Geometry | null;
  crs: string;
  areaKm2?: number;
  bbox?: [number, number, number, number];
  centroid?: [number, number];
  warnings?: string[];
}

export interface AnalysisSession {
  sessionId: string;
  selectedVariables: SelectedVariable[];
  dateRange: DateRange;
  frequency: AnalysisFrequency;
  region: AnalysisRegion | null;
  page3ResultId?: string;
  page4ResultId?: string;
  page5ResultId?: string;
}

export interface SessionActions {
  setSessionId: (id: string) => void;
  setSelectedVariables: (variables: SelectedVariable[]) => void;
  setDateRange: (dateRange: DateRange) => void;
  setFrequency: (frequency: AnalysisFrequency) => void;
  setRegion: (region: AnalysisRegion | null) => void;
  setPage3ResultId: (id?: string) => void;
  setPage4ResultId: (id?: string) => void;
  setPage5ResultId: (id?: string) => void;
  resetSession: () => void;
}

export type SessionStore = AnalysisSession & SessionActions;

/**
 * Helper function implementing SPEC 13.3 invalidation rules:
 * Changing dataset/version, dateRange, region or aggregation invalidates
 * downstream analysis outputs (Page 3 trend, Page 4 change, Page 5 significance).
 */
export function invalidateDownstreamResults<T extends Partial<AnalysisSession>>(state: T): T {
  return {
    ...state,
    page3ResultId: undefined,
    page4ResultId: undefined,
    page5ResultId: undefined,
  };
}

export const initialSessionState: AnalysisSession = {
  sessionId: 'default-session',
  selectedVariables: [],
  dateRange: {
    start: '1990-01-01',
    endMode: 'latest_complete',
  },
  frequency: 'monthly',
  region: null,
  page3ResultId: undefined,
  page4ResultId: undefined,
  page5ResultId: undefined,
};

export const useSession = create<SessionStore>()(
  persist(
    (set) => ({
      ...initialSessionState,

      setSessionId: (sessionId: string) =>
        set({ sessionId }),

      setSelectedVariables: (selectedVariables: SelectedVariable[]) =>
        set((state) =>
          invalidateDownstreamResults({
            ...state,
            selectedVariables,
          })
        ),

      setDateRange: (dateRange: DateRange) =>
        set((state) =>
          invalidateDownstreamResults({
            ...state,
            dateRange,
          })
        ),

      setFrequency: (frequency: AnalysisFrequency) =>
        set((state) =>
          invalidateDownstreamResults({
            ...state,
            frequency,
          })
        ),

      setRegion: (region: AnalysisRegion | null) =>
        set((state) =>
          invalidateDownstreamResults({
            ...state,
            region,
          })
        ),

      setPage3ResultId: (page3ResultId?: string) =>
        set({ page3ResultId }),

      setPage4ResultId: (page4ResultId?: string) =>
        set({ page4ResultId }),

      setPage5ResultId: (page5ResultId?: string) =>
        set({ page5ResultId }),

      resetSession: () =>
        set({
          ...initialSessionState,
          sessionId: `session-${Date.now()}`,
        }),
    }),
    {
      name: 'earth_science_analysis_session',
      storage: createJSONStorage(() => localStorage),
    }
  )
);
