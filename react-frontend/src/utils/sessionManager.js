/**
 * sessionManager.js — Centralised session storage for multi-tab isolation.
 *
 * WHY sessionStorage instead of localStorage?
 * ────────────────────────────────────────────
 * localStorage is shared across ALL tabs of the same origin.  If a user
 * logs in as Candidate in Tab 1 and then as Recruiter in Tab 2, Tab 2's
 * login OVERWRITES Tab 1's token.  On refresh, Tab 1 reads the Recruiter
 * token and redirects — breaking the session.
 *
 * sessionStorage is scoped to a single browser tab.  Each tab maintains
 * its own independent copy:
 *   • Survives page refresh (F5)  ✔
 *   • Does NOT leak across tabs   ✔
 *   • Lost when the tab is closed ✔ (user re-logs — acceptable)
 *
 * This module is the SINGLE source of truth for reading / writing the
 * auth token and user object.  Every file in the codebase should import
 * from here instead of touching localStorage / sessionStorage directly.
 */

const TOKEN_KEY = process.env.REACT_APP_TOKEN_KEY || "companyxyz-token";
const USER_KEY = process.env.REACT_APP_USER_KEY || "companyxyz-user";

// ── Token ──────────────────────────────────────────────────────────────

/** @returns {string|null} The JWT token for the current tab, or null. */
export function getToken() {
  return sessionStorage.getItem(TOKEN_KEY);
}

/** Store the JWT token for the current tab. */
export function setToken(token) {
  sessionStorage.setItem(TOKEN_KEY, token);
}

// ── User object ────────────────────────────────────────────────────────

/** @returns {Object|null} Parsed user object for the current tab. */
export function getUser() {
  try {
    const raw = sessionStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

/** Store the user object (will be JSON-stringified). */
export function setUser(user) {
  sessionStorage.setItem(USER_KEY, JSON.stringify(user));
}

// ── Convenience helpers ────────────────────────────────────────────────

/** Remove both token and user for the current tab (logout). */
export function clearSession() {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(USER_KEY);
  // Also clean up any ancillary keys that other parts of the app may set
  sessionStorage.removeItem("recruiterName");
}

/** @returns {boolean} Whether the current tab has a stored token. */
export function isLoggedIn() {
  return !!getToken();
}
