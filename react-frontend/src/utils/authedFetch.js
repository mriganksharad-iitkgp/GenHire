import { clearSession } from "./sessionManager";

/**
 * Wraps fetch() with centralized 401 and network-error handling.
 * Returns the Response object unchanged so callers can still check
 * response.ok and parse response.json() themselves.
 */
export async function authedFetch(url, options = {}) {
  let response;
  try {
    response = await fetch(url, options);
  } catch (_) {
    const error = new Error(
      "Unable to reach the server. Please check your internet connection."
    );
    error.status = 0;
    throw error;
  }
  if (response.status === 401) {
    clearSession();
    window.dispatchEvent(new CustomEvent("auth:session-expired"));
    const error = new Error("Your session has expired. Please log in again.");
    error.status = 401;
    throw error;
  }
  return response;
}
