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

/** User id the stored token was issued for, when one is cached. */
export function getStoredTokenUserId(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_USER_KEY);
}

/** Read `exp` (ms) from a JWT payload without pulling in a decoder dependency. */
function readTokenExpiryMs(token: string): number | null {
  const encodedPayload = token.split(".")[1];
  if (!encodedPayload) return null;
  try {
    const base64 = encodedPayload.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64.padEnd(Math.ceil(base64.length / 4) * 4, "=");
    const bytes = Uint8Array.from(atob(padded), (char) => char.charCodeAt(0));
    const payload = JSON.parse(new TextDecoder().decode(bytes)) as { exp?: number };
    return typeof payload.exp === "number" ? payload.exp * 1000 : null;
  } catch {
    return null;
  }
}

/**
 * Guest JWTs expire (12h by default). Refresh shortly before `exp` so an expired
 * token is never reused, and let opaque tokens be validated by the API instead.
 */
export function isAccessTokenExpired(token: string, skewMs = 60_000): boolean {
  const expiresAt = readTokenExpiryMs(token);
  if (expiresAt === null) return false;
  return expiresAt <= Date.now() + skewMs;
}

export async function ensureGuestAccessToken(userId: string): Promise<string | null> {
  if (typeof window === "undefined") return null;
  const existing = window.localStorage.getItem(TOKEN_KEY);
  const boundUser = window.localStorage.getItem(TOKEN_USER_KEY);
  if (existing && boundUser === userId && !isAccessTokenExpired(existing)) return existing;

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

/** Drop the cached token and mint a new guest token for `userId`. */
export async function refreshGuestAccessToken(userId: string): Promise<string | null> {
  clearStoredAccessToken();
  return ensureGuestAccessToken(userId);
}

export async function authHeaders(userId?: string): Promise<Record<string, string>> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  // Without an explicit user, keep scoping to whoever the cached token belongs to
  // so a stale token is refreshed instead of being replayed until the API rejects it.
  const targetUser = userId ?? getStoredTokenUserId();
  if (!targetUser) return headers;
  const token = await ensureGuestAccessToken(targetUser);
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}
