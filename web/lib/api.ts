// The one place the browser talks to the API. Same origin (/api is rewritten to
// FastAPI by Next.js), so there is no CORS and Clerk's session cookie rides along.

import { getToken } from "@clerk/nextjs";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

/** A network failure (offline, server down), as opposed to an API error response. */
export class NetworkError extends Error {}

// Clerk's session token lives 60 seconds. The cookie copy can be stale when a
// tab has been asleep, so a freshly minted token is also sent as a Bearer header.
async function authHeader(): Promise<Record<string, string>> {
  try {
    const token = await getToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch {
    return {}; // Clerk not loaded or offline: fall back to the cookie
  }
}

type Options = { method?: string; body?: unknown; signal?: AbortSignal };

export async function api<T>(path: string, { method = "GET", body, signal }: Options = {}): Promise<T> {
  const headers: Record<string, string> = { "X-Requested-With": "fetch", ...(await authHeader()) };
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch (error) {
    throw new NetworkError(error instanceof Error ? error.message : "Network error");
  }

  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    // A 5xx without our error shape means the API itself is unreachable behind the rewrite.
    if (!data?.error && response.status >= 500) throw new NetworkError(`API unavailable (${response.status})`);
    throw new ApiError(
      response.status,
      data?.error?.code ?? "http_error",
      data?.error?.message ?? `Request failed (${response.status})`,
    );
  }
  return data as T;
}

export function errorMessage(error: unknown): string {
  if (error instanceof NetworkError) return "Can't reach the server. Check your connection.";
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}
