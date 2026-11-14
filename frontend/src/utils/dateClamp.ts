/**
 * SPEC 5.3:
 * Start date: 1990-01-01 for the project's historical analysis, unless
 * product availability starts later.
 */

export const PROJECT_DEFAULT_START_DATE = '1990-01-01';

/**
 * Clamps the requested start date against product's earliest available date.
 * If product starts after requested date (e.g. product start is 2000-01-01 and requested is 1990-01-01),
 * it returns the product's start date.
 * Otherwise, returns the requested date.
 */
export function clampStartDate(
  requestedDate: string,
  productStartDate?: string | null
): string {
  if (!requestedDate) {
    return productStartDate || PROJECT_DEFAULT_START_DATE;
  }
  if (!productStartDate) {
    return requestedDate;
  }

  // ISO dates (YYYY-MM-DD) compare lexicographically accurately
  if (requestedDate < productStartDate) {
    return productStartDate;
  }

  return requestedDate;
}

/**
 * Calculates the initial default start date for a dataset product,
 * clamping the project's standard 1990-01-01 baseline against product start date.
 */
export function getDefaultStartDate(productStartDate?: string | null): string {
  return clampStartDate(PROJECT_DEFAULT_START_DATE, productStartDate);
}
