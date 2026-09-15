/** Auth token helpers for guest JWT (never store API keys in the browser). */

const TOKEN_KEY = "tripmind_access_token";
const TOKEN_USER_KEY = "tripmind_access_token_user";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export function getStoredAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function clearStoredAccessToken(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(TOKEN_USER_KEY);
}

export async function ensureGuestAccessToken(userId: string): Promise<string | null> {
  if (typeof window === "undefined") return null;
  const existing = window.localStorage.getItem(TOKEN_KEY);
  const boundUser = window.localStorage.getItem(TOKEN_USER_KEY);
  if (existing && boundUser === userId) return existing;

  try {
    const response = await fetch(`${API_BASE}/auth/guest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId }),
    });
    if (!response.ok) return existing;
    const body = (await response.json()) as { access_token?: string };
    if (!body.access_token) return existing;
    window.localStorage.setItem(TOKEN_KEY, body.access_token);
    window.localStorage.setItem(TOKEN_USER_KEY, userId);
    return body.access_token;
  } catch {
    return existing;
  }
}

export async function authHeaders(userId?: string): Promise<Record<string, string>> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (!userId) {
    const token = getStoredAccessToken();
    if (token) headers.Authorization = `Bearer ${token}`;
    return headers;
  }
  const token = await ensureGuestAccessToken(userId);
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}
