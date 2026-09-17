/** Stable guest user id for pre-auth memory + trips. */
const STORAGE_KEY = "tripmind_guest_user_id";

export function getGuestUserId(): string {
  if (typeof window === "undefined") {
    return "00000000-0000-4000-8000-000000000001";
  }
  const existing = window.localStorage.getItem(STORAGE_KEY);
  if (existing) return existing;
  const created =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `00000000-0000-4000-8000-${Date.now().toString(16).padStart(12, "0").slice(-12)}`;
  window.localStorage.setItem(STORAGE_KEY, created);
  return created;
}
