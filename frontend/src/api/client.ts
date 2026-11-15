/**
 * Base API client configuration and URL resolver.
 * Respects VITE_API_BASE_URL from environment variables (e.g. for Vercel deployment),
 * or falls back to relative '/api' for local Vite proxy and Vercel Edge proxy rewrites.
 */

export const API_BASE_URL = (
  (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_BASE_URL) ||
  '/api'
).replace(/\/+$/, '');

/**
 * Resolves an API path to a full or relative URL.
 * Handles paths with or without leading slash, and avoids duplicate '/api' prefixes.
 */
export function getApiUrl(path: string): string {
  if (path.startsWith('http://') || path.startsWith('https://')) {
    return path;
  }
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  if (cleanPath.startsWith('/api') && API_BASE_URL.endsWith('/api')) {
    return `${API_BASE_URL}${cleanPath.slice(4)}`;
  }
  return `${API_BASE_URL}${cleanPath}`;
}

/**
 * Standard fetch wrapper that resolves the URL through getApiUrl.
 */
export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(getApiUrl(path), init);
}
