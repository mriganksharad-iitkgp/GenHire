// Payment & Wallet API Layer
// Centralized recharge and wallet endpoints

const API_BASE =
  process.env.REACT_APP_API_BASE || `${process.env.REACT_APP_API_URL}/api`;

function authHeaders() {
  const token = localStorage.getItem(
    process.env.REACT_APP_TOKEN_KEY || "companyxyz-token",
  );
  return {
    Authorization: `Bearer ${token}`,
  };
}

async function request(path, options = {}) {
  const headers = { ...authHeaders(), ...(options.headers || {}) };
  if (
    options.body &&
    typeof FormData !== "undefined" &&
    !(options.body instanceof FormData)
  ) {
    headers["Content-Type"] = headers["Content-Type"] || "application/json";
  }
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    let errMsg = "Request failed";
    try {
      const data = await res.json();
      errMsg = data.error || data.message || errMsg;
    } catch (_) {
      // ignore json parse error
    }
    const error = new Error(errMsg);
    error.status = res.status;
    throw error;
  }
  if (res.status === 204) return null;
  return res.json();
}

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
export const getPaymentHistory = () => request("/payment/payments/history");

/** Get recent credit transactions */
export const getCreditTransactions = () =>
  request("/payment/wallet/transactions");

// =============================================================================
// INTERVIEWS (Usage)
// =============================================================================

/** Use an interview (decrement remaining count) */
export const useInterview = () =>
  request("/payment/interviews/use", { method: "POST" });
