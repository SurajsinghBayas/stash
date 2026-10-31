/**
 * The only place that talks to the API. Session cookies are HttpOnly, so the client never sees a token: on a 401
 * it calls /auth/refresh once (shared by every request that failed at the same moment) and retries.
 */

const BASE = "/api/v1";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public requestId?: string,
    public retryAfter?: number,
  ) {
    super(message);
  }
}

let refreshing: Promise<boolean> | null = null;
let onSessionLost: () => void = () => {};

export function setSessionLostHandler(fn: () => void) {
  onSessionLost = fn;
}

async function refreshSession(): Promise<boolean> {
  refreshing ??= fetch(`${BASE}/auth/refresh`, { method: "POST", credentials: "same-origin" })
    .then((r) => r.ok)
    .catch(() => false)
    .finally(() => setTimeout(() => (refreshing = null), 0));
  return refreshing;
}

async function toError(res: Response): Promise<ApiError> {
  let code = "http_error";
  let message = res.status >= 500 ? "Something went wrong on our side. Try again." : "Request failed.";
  let requestId: string | undefined;
  try {
    const body = await res.json();
    if (body?.error) ({ code, message, request_id: requestId } = body.error);
  } catch {
    /* not JSON (proxy error page) */
  }
  const retry = Number(res.headers.get("Retry-After")) || undefined;
  return new ApiError(res.status, code, message, requestId, retry);
}

export interface RequestOptions {
  method?: string;
  body?: unknown;
  signal?: AbortSignal;
  /** Return the raw Response (for streaming). */
  raw?: boolean;
}

export async function request<T = unknown>(path: string, opts: RequestOptions = {}): Promise<T> {
  const init: RequestInit = {
    method: opts.method ?? (opts.body === undefined ? "GET" : "POST"),
    credentials: "same-origin",
    signal: opts.signal,
    headers: opts.body === undefined ? undefined : { "Content-Type": "application/json" },
    body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
  };
  let res: Response;
  try {
    res = await fetch(BASE + path, init);
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError(0, "offline", "You're offline. Changes will save when you reconnect.");
  }
  if (res.status === 401 && !path.startsWith("/auth/")) {
    if (await refreshSession()) {
      res = await fetch(BASE + path, init);
    }
    if (res.status === 401) {
      onSessionLost();
      throw await toError(res);
    }
  }
  if (!res.ok) throw await toError(res);
  if (opts.raw) return res as unknown as T;
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string, signal?: AbortSignal) => request<T>(path, { signal }),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body: body ?? {} }),
  patch: <T>(path: string, body: unknown) => request<T>(path, { method: "PATCH", body }),
  del: (path: string) => request<void>(path, { method: "DELETE" }),
};

export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  return "Something went wrong. Try again.";
}
