import { callDemoBackend, DEMO_MODE } from "./demo";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

let accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken() {
  return accessToken;
}

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : "Request failed");
    this.status = status;
    this.detail = detail;
  }
}

function extractDetail(body: unknown): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail.map((d) => (typeof d === "object" && d && "msg" in d ? String((d as { msg: unknown }).msg) : String(d))).join("; ");
    }
  }
  return "Request failed";
}

let refreshPromise: Promise<boolean> | null = null;

async function refreshAccessToken(): Promise<boolean> {
  if (DEMO_MODE) {
    // Stands in for the httpOnly refresh cookie: demo mode remembers the signed-in
    // user in localStorage, so a reload restores the session the same way.
    const response = await callDemoBackend({ method: "POST", path: "/auth/refresh", token: null });
    if (response.status !== 200) return false;
    setAccessToken((response.body as { access_token: string }).access_token);
    return true;
  }
  if (!refreshPromise) {
    refreshPromise = fetch(`${API_BASE_URL}/auth/refresh`, {
      method: "POST",
      credentials: "include",
    })
      .then(async (res) => {
        if (!res.ok) return false;
        const data = await res.json();
        setAccessToken(data.access_token);
        return true;
      })
      .catch(() => false)
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  skipAuthRetry?: boolean;
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, skipAuthRetry, headers, ...rest } = options;
  const isFormData = body instanceof FormData;

  if (DEMO_MODE) {
    const { status, body: payload } = await callDemoBackend({
      method: (rest.method ?? "GET").toUpperCase(),
      path,
      body,
      token: accessToken,
    });
    if (status === 204) return undefined as T;
    if (status >= 400) throw new ApiError(status, extractDetail(payload));
    return payload as T;
  }

  const doFetch = async (): Promise<Response> =>
    fetch(`${API_BASE_URL}${path}`, {
      ...rest,
      credentials: "include",
      headers: {
        ...(isFormData ? {} : body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        ...headers,
      },
      body: body === undefined ? undefined : isFormData ? (body as FormData) : JSON.stringify(body),
    });

  let response = await doFetch();

  if (response.status === 401 && !skipAuthRetry && !path.startsWith("/auth/")) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      response = await doFetch();
    }
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();

  if (!response.ok) {
    throw new ApiError(response.status, typeof payload === "string" ? payload : extractDetail(payload));
  }
  return payload as T;
}

export { refreshAccessToken };
