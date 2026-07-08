// Single HTTP client for the whole app.
//
// Promoted from services/api.js's request(); every legacy service wrapper
// (api, adminApi, inviteApi, paymentApi, cvService, authedFetch) now delegates
// here instead of keeping its own copy of the same ~40 lines.
//
// Behavioral contracts preserved from the originals:
//  - Base URL: REACT_APP_API_BASE, else REACT_APP_API_URL + "/api" (verbatim).
//  - 401 handling is opt-out: most callers clear the session and broadcast
//    "auth:session-expired"; payment/invite flows deliberately don't
//    (signalOn401: false) so an in-flight payment doesn't log the user out.
//  - Content-Type is set to JSON only when a non-FormData body is present.
//  - 204 -> null; response bodies that fail to parse as JSON -> null.

import { clearSession, getToken } from "shared/utils/session";

export const API_BASE =
  process.env.REACT_APP_API_BASE || `${process.env.REACT_APP_API_URL}/api`;

export function signalExpiredSession() {
  clearSession();
  window.dispatchEvent(new CustomEvent("auth:session-expired"));
}

export function authHeaders() {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function networkError() {
  const error = new Error(
    "Unable to reach the server. Please check your internet connection."
  );
  error.status = 0;
  return error;
}

function expiredError() {
  const error = new Error("Your session has expired. Please log in again.");
  error.status = 401;
  return error;
}

/**
 * Perform an authenticated JSON request against the API.
 *
 * @param {string} path - path under the API base, e.g. "/jobs"
 * @param {object} options - fetch options plus:
 *   auth          (default true)  - attach the bearer token
 *   signalOn401   (default true)  - clear session + broadcast expiry on 401
 *   catchNetwork  (default true)  - wrap network failures in a friendly error
 */
export async function request(path, options = {}) {
  const {
    auth = true,
    signalOn401 = true,
    catchNetwork = true,
    ...fetchOptions
  } = options;

  const headers = {
    ...(auth ? authHeaders() : {}),
    ...(fetchOptions.headers || {}),
  };
  if (
    fetchOptions.body &&
    typeof FormData !== "undefined" &&
    !(fetchOptions.body instanceof FormData)
  ) {
    headers["Content-Type"] = headers["Content-Type"] || "application/json";
  }

  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, { ...fetchOptions, headers });
  } catch (err) {
    if (catchNetwork) throw networkError();
    throw err;
  }

  if (!res.ok) {
    if (res.status === 401 && signalOn401) {
      signalExpiredSession();
      throw expiredError();
    }
    let errMsg = "Request failed";
    let errorData = null;
    try {
      errorData = await res.json();
      errMsg = errorData.error || errorData.message || errMsg;
    } catch (_) {}
    const error = new Error(errMsg);
    error.status = res.status;
    error.data = errorData;
    throw error;
  }

  if (res.status === 204) return null;
  try {
    return await res.json();
  } catch (_) {
    return null; // empty 200 body
  }
}

/** Like request(), but resolves to a Blob (file downloads / previews). */
export async function requestBlob(path, options = {}) {
  const { auth = true, signalOn401 = true, ...fetchOptions } = options;
  const headers = {
    ...(auth ? authHeaders() : {}),
    ...(fetchOptions.headers || {}),
  };

  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, { ...fetchOptions, headers });
  } catch (_) {
    throw networkError();
  }

  if (!res.ok) {
    if (res.status === 401 && signalOn401) {
      signalExpiredSession();
      throw expiredError();
    }
    const error = new Error(`Request failed: ${res.status}`);
    error.status = res.status;
    throw error;
  }
  return res.blob();
}

/**
 * fetch() wrapper that returns the raw Response (callers parse themselves)
 * with centralized 401 + network-error handling. For calls to absolute URLs
 * or endpoints whose responses aren't JSON.
 */
export async function authedFetch(url, options = {}) {
  let response;
  try {
    response = await fetch(url, options);
  } catch (_) {
    throw networkError();
  }
  if (response.status === 401) {
    signalExpiredSession();
    throw expiredError();
  }
  return response;
}

// Convenience verbs
export const get = (path, options = {}) => request(path, options);
export const post = (path, body, options = {}) =>
  request(path, {
    method: "POST",
    body: body instanceof FormData ? body : JSON.stringify(body),
    ...options,
  });
export const put = (path, body, options = {}) =>
  request(path, {
    method: "PUT",
    body: body instanceof FormData ? body : JSON.stringify(body),
    ...options,
  });
export const del = (path, options = {}) =>
  request(path, { method: "DELETE", ...options });
