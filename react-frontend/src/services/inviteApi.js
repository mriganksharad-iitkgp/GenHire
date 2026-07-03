// Invite API surface
// - Recruiter endpoints reuse the bearer-token request helper from api.js.
// - Redeem endpoints are public; we hit them without an auth header so an
//   already-logged-in candidate clicking a magic link doesn't trip the JWT check.

import { getToken } from "../utils/sessionManager";

const API_BASE =
  process.env.REACT_APP_API_BASE || `${process.env.REACT_APP_API_URL}/api`;

function authHeaders() {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function jsonRequest(path, { method = "GET", body, headers, withAuth = true } = {}) {
  const finalHeaders = {
    ...(withAuth ? authHeaders() : {}),
    ...(headers || {}),
  };
  if (body && !(body instanceof FormData)) {
    finalHeaders["Content-Type"] = finalHeaders["Content-Type"] || "application/json";
  }
  const finalBody = body instanceof FormData || body == null ? body : JSON.stringify(body);
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: finalHeaders,
    body: finalBody,
  });

  let data = null;
  try {
    data = await res.json();
  } catch (_) {
    // empty body
  }
  if (!res.ok) {
    const err = new Error((data && (data.error || data.message)) || `Request failed (${res.status})`);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

// ----- Recruiter endpoints (auth required) ---------------------------------

export async function previewInvites(jobId, { file, text, single } = {}) {
  if (file) {
    const fd = new FormData();
    fd.append("file", file);
    if (text) fd.append("text", text);
    if (single) fd.append("email", single);
    return jsonRequest(`/recruiter/jobs/${jobId}/invites/preview`, {
      method: "POST",
      body: fd,
    });
  }
  return jsonRequest(`/recruiter/jobs/${jobId}/invites/preview`, {
    method: "POST",
    body: { text, email: single },
  });
}

export async function sendInvites(jobId, { emails, invite_type, source = "manual" }) {
  return jsonRequest(`/recruiter/jobs/${jobId}/invites`, {
    method: "POST",
    body: { emails, invite_type, source },
  });
}

// sendInvites now returns immediately (batch is dispatched in the
// background) — poll this to drive a live progress UI instead of waiting
// on one long-running request.
export async function getInviteBatchStatus(jobId, batchId) {
  return jsonRequest(`/recruiter/jobs/${jobId}/invites/batches/${batchId}`, {
    method: "GET",
  });
}

// ----- Public redeem endpoints --------------------------------------------

export async function lookupInvite(token) {
  return jsonRequest(
    `/invite/redeem?token=${encodeURIComponent(token)}`,
    { method: "GET", withAuth: false },
  );
}

export async function redeemInvite({ token }) {
  return jsonRequest("/invite/redeem", {
    method: "POST",
    body: { token },
    withAuth: false,
  });
}
