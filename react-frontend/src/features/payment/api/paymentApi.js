// Payment & Wallet API Layer
// Centralized recharge and wallet endpoints

import { request as clientRequest } from "shared/api/client";

// Payment calls intentionally do NOT broadcast session-expiry on 401 and do
// not wrap network failures (matching the previous local implementation), so
// an in-flight payment error never logs the user out.
const request = (path, options = {}) =>
  clientRequest(path, { signalOn401: false, catchNetwork: false, ...options });

// =============================================================================
// PLANS
// =============================================================================

/** Get all available subscription plans */
export const getPlans = () => request("/payment/recharge/packs");

/** Get specific plan by ID */
export const getPlan = (planId) => request(`/payment/plans/${planId}`);

// =============================================================================
// SUBSCRIPTIONS
// =============================================================================

/** Get wallet summary for logged-in user */
export const getCurrentSubscription = () => request("/payment/wallet/summary");

/** Check if user can conduct interviews */
export const checkSubscription = () => request("/payment/wallet/check");

/** Get subscription history */
export const getSubscriptionHistory = () =>
  request("/payment/subscriptions/history");

/** Cancel subscription */
export const cancelSubscription = (reason) =>
  request("/payment/subscriptions/cancel", {
    method: "POST",
    body: JSON.stringify({ reason }),
  });

// =============================================================================
// PAYMENTS
// =============================================================================

/** Initiate payment for a plan (creates Razorpay order) */
export const initiatePayment = (planId) =>
  request("/payment/recharge/initiate", {
    method: "POST",
    body: JSON.stringify({ plan_id: planId }),
  });

/** Verify Razorpay payment after checkout */
export const verifyPayment = (paymentData) =>
  request("/payment/recharge/verify", {
    method: "POST",
    body: JSON.stringify(paymentData),
  });

/** Get payment history */
export const getPaymentHistory = (limit = 100) =>
  request(`/payment/payments/history?limit=${encodeURIComponent(limit)}`);

/** Get recent credit transactions */
export const getCreditTransactions = (kind = "all") =>
  request(`/payment/wallet/transactions?kind=${encodeURIComponent(kind)}`);

// =============================================================================
// INTERVIEWS (Usage)
// =============================================================================

/** Use an interview (decrement remaining count) */
export const useInterview = () =>
  request("/payment/interviews/use", { method: "POST" });
