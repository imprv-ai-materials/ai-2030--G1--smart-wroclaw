/**
 * Thin fetch wrapper for the Smart Wrocław backend.
 *
 * Every request targets `${NEXT_PUBLIC_API_URL}` (default
 * http://localhost:8101/api/v1) and carries the dev auth headers:
 *   - `X-Citizen-Id: 1` on every call
 *   - `X-Specialist-Key: dev-specialist` additionally on specialist (HITL) calls
 *
 * Non-2xx responses throw `APIError`; 204 / non-JSON bodies resolve to
 * `undefined`. Swap the dev headers for real auth before shipping.
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8101/api/v1";

// Dev-mode identity for the legacy assistant/report endpoints. Real auth for
// citizens goes through the JWT stored under `TOKEN_KEY` (see below).
const CITIZEN_ID = "1";
const SPECIALIST_KEY = "dev-specialist";

// -- JWT storage (localStorage) ----------------------------------------------
// Single source of truth for the citizen auth token. Re-exported from
// `lib/auth` as getToken/setToken/clearToken to match the public API.
export const TOKEN_KEY = "sw_token";

// Tiny pub/sub so `useSyncExternalStore` can subscribe to token changes (this
// is what powers `useAuth` without a setState-in-effect / hydration hack).
const tokenListeners = new Set<() => void>();

function emitTokenChange(): void {
  for (const listener of tokenListeners) listener();
}

/** Subscribe to token changes (same-tab writes and cross-tab `storage`). */
export function subscribeToken(callback: () => void): () => void {
  tokenListeners.add(callback);
  const onStorage = (e: StorageEvent) => {
    if (e.key === TOKEN_KEY) callback();
  };
  if (typeof window !== "undefined") {
    window.addEventListener("storage", onStorage);
  }
  return () => {
    tokenListeners.delete(callback);
    if (typeof window !== "undefined") {
      window.removeEventListener("storage", onStorage);
    }
  };
}

/** Server snapshot for `useSyncExternalStore` — never authed during SSR. */
export function getTokenServerSnapshot(): string | null {
  return null;
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    /* localStorage unavailable */
    return null;
  }
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* localStorage unavailable */
  }
  emitTokenChange();
}

export function clearToken(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* localStorage unavailable */
  }
  emitTokenChange();
}

export class APIError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown, message: string) {
    super(message);
    this.name = "APIError";
    this.status = status;
    this.body = body;
  }
}

type RequestOptions = {
  /** Also send the specialist key header (HITL / review endpoints). */
  specialist?: boolean;
  /** Attach `Authorization: Bearer <token>` from localStorage (citizen auth). */
  auth?: boolean;
};

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  options?: RequestOptions,
): Promise<T> {
  const headers: Record<string, string> = { "X-Citizen-Id": CITIZEN_ID };
  if (options?.specialist) headers["X-Specialist-Key"] = SPECIALIST_KEY;
  if (options?.auth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  let payload: BodyInit | undefined;
  if (body !== undefined) {
    headers["content-type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const res = await fetch(`${BASE_URL}${path.startsWith("/") ? path : `/${path}`}`, {
    method,
    headers,
    body: payload,
    cache: "no-store",
  });

  if (!res.ok) {
    // An authed call that 401s means the token is invalid/expired — drop it.
    if (res.status === 401 && options?.auth) clearToken();

    const text = await res.text();
    let parsed: unknown = text;
    try {
      parsed = JSON.parse(text);
    } catch {
      /* keep raw text */
    }
    throw new APIError(
      res.status,
      parsed,
      typeof parsed === "object" && parsed && "detail" in parsed
        ? String((parsed as { detail: unknown }).detail)
        : `HTTP ${res.status}`,
    );
  }

  if (res.status === 204) return undefined as T;
  const contentType = res.headers.get("content-type") ?? "";
  if (!contentType.includes("json")) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string, options?: RequestOptions) =>
    request<T>("GET", path, undefined, options),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>("POST", path, body, options),
  patch: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>("PATCH", path, body, options),
  delete: <T>(path: string, options?: RequestOptions) =>
    request<T>("DELETE", path, undefined, options),
};
