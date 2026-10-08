// Auth endpoints (login, registration, OAuth, email verification, password
// reset). These calls are public (no bearer token) and each page inspects the
// raw Response itself — flows like Google-recruiter onboarding branch on
// specific statuses/payloads — so this module deliberately returns fetch's
// Response unchanged instead of going through shared/api/client's request()
// (which would throw on non-2xx and clear the session on 401s such as a
// failed login attempt).

import { API_BASE } from "shared/api/client";

export async function authPost(path, payload) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 20000);
  try {
    return await fetch(API_BASE + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
  } catch (error) {
    throw new Error(error.name === "AbortError"
      ? "The request timed out. Please check your connection and try again."
      : "Unable to reach the server. Please check your internet connection.");
  } finally {
    clearTimeout(timeout);
  }
}

export const login = (payload) => authPost("/login", payload);
export const register = (payload) => authPost("/register", payload);
export const googleOAuth = (payload) => authPost("/google-oauth", payload);
export const forgotPassword = (payload) => authPost("/forgot-password", payload);
export const resetPassword = (payload) => authPost("/reset-password", payload);
export const verifyEmail = (payload) => authPost("/verify-email", payload);
export const checkEmailAccountType = (payload) =>
  authPost("/check-email-account-type", payload);
