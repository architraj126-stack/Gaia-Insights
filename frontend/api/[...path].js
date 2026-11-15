export const config = {
  runtime: 'edge',
};

export default async function handler(request) {
  const backendUrl = process.env.BACKEND_URL || process.env.VITE_API_BASE_URL;
  const url = new URL(request.url);

  if (!backendUrl) {
    return new Response(
      JSON.stringify(
        {
          status: 'backend_not_configured',
          message:
            'The Gaia Insights frontend is running on Vercel, but no backend URL is configured. Please add the environment variable BACKEND_URL in your Vercel Project Settings (Environment Variables) pointing to your deployed FastAPI backend (e.g. https://your-backend.railway.app or https://your-backend.onrender.com).',
          endpoint: url.pathname + url.search,
        },
        null,
        2
      ),
      {
        status: 503,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*',
        },
      }
    );
  }

  // Handle CORS preflight requests
  if (request.method === 'OPTIONS') {
    return new Response(null, {
      status: 204,
      headers: {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS, HEAD',
        'Access-Control-Allow-Headers': '*',
      },
    });
  }

  const targetBase = backendUrl.replace(/\/+$/, '');
  const targetUrl = `${targetBase}${url.pathname}${url.search}`;

  const headers = new Headers(request.headers);
  headers.delete('host');
  headers.delete('connection');

  try {
    const fetchOptions = {
      method: request.method,
      headers,
      body:
        request.method !== 'GET' && request.method !== 'HEAD'
          ? request.body
          : undefined,
      duplex: 'half',
    };

    const response = await fetch(targetUrl, fetchOptions);

    const responseHeaders = new Headers(response.headers);
    responseHeaders.set('Access-Control-Allow-Origin', '*');

    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: responseHeaders,
    });
  } catch (err) {
    return new Response(
      JSON.stringify(
        {
          status: 'proxy_error',
          message: `Failed to proxy request to backend at ${targetBase}: ${err?.message || err}`,
          endpoint: url.pathname,
        },
        null,
        2
      ),
      {
        status: 502,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*',
        },
      }
    );
  }
}
