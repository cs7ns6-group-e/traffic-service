const TOKEN_KEY = "tb_access_token";
const REFRESH_KEY = "tb_refresh_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setTokens(access: string, refresh: string) {
  localStorage.setItem(TOKEN_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}
export function clearTokens() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

async function refreshAccessToken(): Promise<string | null> {
  const refresh = localStorage.getItem(REFRESH_KEY);
  if (!refresh) return null;
  try {
    const res = await fetch("/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!res.ok) { clearTokens(); return null; }
    const data = await res.json();
    setTokens(data.access_token, data.refresh_token ?? refresh);
    return data.access_token;
  } catch {
    return null;
  }
}

async function request<T>(url: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let res = await fetch(url, { ...options, headers });

  // Attempt token refresh on 401
  if (res.status === 401) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      headers["Authorization"] = `Bearer ${newToken}`;
      res = await fetch(url, { ...options, headers });
    }
  }

  if (!res.ok) {
    let message = `HTTP ${res.status}`;
    let rawBody: Record<string, unknown> | null = null;
    try {
      const text = await res.text();
      if (text) {
        try {
          rawBody = JSON.parse(text) as Record<string, unknown>;
          const detail = rawBody.detail;
          if (typeof detail === "string") {
            message = detail;
          } else if (typeof detail === "object" && detail !== null) {
            message = (detail as Record<string, unknown>).message as string ?? JSON.stringify(detail);
          } else if (typeof rawBody.message === "string") {
            message = rawBody.message;
          } else {
            message = text;
          }
        } catch { message = text; }
      }
    } catch { /* ignore */ }
    const apiErr = new Error(message) as Error & { body: unknown; statusCode: number };
    apiErr.body = rawBody;
    apiErr.statusCode = res.status;
    throw apiErr;
  }

  // 204 No Content
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export function apiGet<T>(url: string): Promise<T> {
  return request<T>(url);
}
export function apiPost<T>(url: string, body?: unknown): Promise<T> {
  return request<T>(url, { method: "POST", body: body !== undefined ? JSON.stringify(body) : undefined });
}
export function apiDelete<T>(url: string, body?: unknown): Promise<T> {
  return request<T>(url, { method: "DELETE", body: body !== undefined ? JSON.stringify(body) : undefined });
}
