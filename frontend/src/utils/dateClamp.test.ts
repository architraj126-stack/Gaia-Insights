import { describe, it, expect } from 'vitest';
import { clampStartDate, getDefaultStartDate, PROJECT_DEFAULT_START_DATE } from './dateClamp';

describe('dateClamp utility (SPEC 5.3)', () => {
  it('uses 1990-01-01 when product availability starts earlier (e.g. GPCP 1979-01-01)', () => {
    const productStart = '1979-01-01';
    const defaultDate = getDefaultStartDate(productStart);
    expect(defaultDate).toBe('1990-01-01');
  });

  it('clamps to product start date when product starts later than 1990-01-01 (e.g. 2000-02-15)', () => {
    const productStart = '2000-02-15';
    const defaultDate = getDefaultStartDate(productStart);
    expect(defaultDate).toBe('2000-02-15');
  });

  it('handles null or undefined product start date gracefully', () => {
    expect(getDefaultStartDate(null)).toBe(PROJECT_DEFAULT_START_DATE);
    expect(getDefaultStartDate(undefined)).toBe(PROJECT_DEFAULT_START_DATE);
  });

  it('clamps user-requested dates earlier than product start date', () => {
    const productStart = '1985-06-01';
    // User requested 1980-01-01, but product started in 1985
    expect(clampStartDate('1980-01-01', productStart)).toBe('1985-06-01');

    // User requested 1995-01-01, which is after product start -> valid as is
    expect(clampStartDate('1995-01-01', productStart)).toBe('1995-01-01');
  });

  it('handles empty requested date by falling back to product start or default', () => {
    expect(clampStartDate('', '1995-01-01')).toBe('1995-01-01');
    expect(clampStartDate('', null)).toBe(PROJECT_DEFAULT_START_DATE);
  });
});
