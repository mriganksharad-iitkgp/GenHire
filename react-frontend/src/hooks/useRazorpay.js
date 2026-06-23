/**
 * useRazorpay - Custom hook for Razorpay payment integration
 * Handles script loading, checkout, and payment verification
 */
import { useState, useCallback, useRef } from "react";
import { getUser } from "../utils/sessionManager";
import { initiatePayment, verifyPayment } from "../services/payment";

const RAZORPAY_SCRIPT_URL = "https://checkout.razorpay.com/v1/checkout.js";

const RAZORPAY_CONFIG = {
  name: "HRTech",
  theme: {
    color: "#6366f1",
  },
  currency: "INR",
};

/**
 * Load Razorpay script dynamically
 * @returns {Promise<boolean>} - Whether script loaded successfully
 */
const loadScript = () => {
  return new Promise((resolve) => {
    if (window.Razorpay) {
      resolve(true);
      return;
    }

    const script = document.createElement("script");
    script.src = RAZORPAY_SCRIPT_URL;
    script.async = true;
    script.onload = () => resolve(true);
    script.onerror = () => resolve(false);
    document.body.appendChild(script);
  });
};

/**
 * Get user info from localStorage for prefill
 */
const getUserInfo = () => {
  try {
    return getUser() || {};
  } catch {
    return {};
  }
};

/**
 * Custom hook for Razorpay payment flow
 * @param {Object} options - Hook options
 * @param {Function} options.onSuccess - Called on successful payment
 * @param {Function} options.onError - Called on payment error
 * @param {Function} options.onCancel - Called when modal is dismissed
 */
export const useRazorpay = ({ onSuccess, onError, onCancel } = {}) => {
  const [loading, setLoading] = useState(null); // planId being processed
  const [error, setError] = useState(null);
  const razorpayRef = useRef(null);

  const clearError = useCallback(() => setError(null), []);

  /**
   * Initiate payment for a plan
   * @param {string} planId - Plan ID to purchase
   */
  const checkout = useCallback(
    async (planId) => {
      try {
        setLoading(planId);
        setError(null);

        // 1. Load Razorpay script
        const scriptLoaded = await loadScript();
        if (!scriptLoaded) {
          throw new Error("Failed to load payment gateway. Please try again.");
        }

        // 2. Create order via backend
        const response = await initiatePayment(planId);
        const orderData = response?.data || response;

        // 3. Handle free plans (no order_id)
        if (!orderData?.order_id) {
          setLoading(null);
          onSuccess?.({ free: true, planId });
          return { success: true, free: true };
        }

        // 4. Get user info for prefill
        const userInfo = getUserInfo();

        // 5. Configure Razorpay options
        const options = {
          key: orderData.key_id,
          amount: orderData.amount,
          currency: orderData.currency || RAZORPAY_CONFIG.currency,
          name: RAZORPAY_CONFIG.name,
          description: `Recharge - ${orderData.notes?.plan_name || "Pack"}`,
          order_id: orderData.order_id,
          prefill: {
            name:
              orderData.prefill?.name ||
              userInfo.name ||
              userInfo.company_name ||
              "",
            email: orderData.prefill?.email || userInfo.email || "",
            contact: userInfo.phone || "",
          },
          theme: RAZORPAY_CONFIG.theme,

          // Success handler
          handler: async (response) => {
            try {
              setLoading(planId);

              const verifyResponse = await verifyPayment({
                razorpay_order_id: response.razorpay_order_id,
                razorpay_payment_id: response.razorpay_payment_id,
                razorpay_signature: response.razorpay_signature,
              });

              if (verifyResponse?.success) {
                onSuccess?.({
                  paymentId: response.razorpay_payment_id,
                  orderId: response.razorpay_order_id,
                  planId,
                });
              } else {
                const errorMsg =
                  "Payment verification failed. Please contact support.";
                setError(errorMsg);
                onError?.(new Error(errorMsg));
              }
            } catch (err) {
              console.error("Payment verification error:", err);
              const errorMsg =
                "Payment verification failed. Please contact support.";
              setError(errorMsg);
              onError?.(err);
            } finally {
              setLoading(null);
            }
          },

          // Modal dismiss handler
          modal: {
            ondismiss: () => {
              setLoading(null);
              onCancel?.();
            },
          },
        };

        // 6. Create and open Razorpay instance
        razorpayRef.current = new window.Razorpay(options);

        razorpayRef.current.on("payment.failed", (response) => {
          console.error("Payment failed:", response.error);
          const errorMsg =
            response.error?.description || "Payment failed. Please try again.";
          setError(errorMsg);
          setLoading(null);
          onError?.(new Error(errorMsg));
        });

        razorpayRef.current.open();

        return { success: true, orderId: orderData.order_id };
      } catch (err) {
        console.error("Payment initiation error:", err);
        const errorMsg =
          err.message || "Failed to process payment. Please try again.";
        setError(errorMsg);
        setLoading(null);
        onError?.(err);
        return { success: false, error: errorMsg };
      }
    },
    [onSuccess, onError, onCancel],
  );

  /**
   * Close Razorpay modal programmatically
   */
  const close = useCallback(() => {
    razorpayRef.current?.close();
    setLoading(null);
  }, []);

  return {
    checkout,
    close,
    loading,
    error,
    clearError,
    isProcessing: loading !== null,
  };
};

export default useRazorpay;
