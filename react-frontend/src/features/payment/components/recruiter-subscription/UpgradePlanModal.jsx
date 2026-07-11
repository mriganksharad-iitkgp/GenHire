import React, { useState, useEffect, useCallback } from "react";
import styles from "./UpgradePlanModal.module.css";
import {
  getPlans,
  initiatePayment,
  getCurrentSubscription,
  getPaymentHistory,
} from "features/payment/api";

/**
 * UpgradePlanModal - Modal for viewing and upgrading subscription plans
 * Shows current subscription, available plans, and payment history
 */
const UpgradePlanModal = ({
  isOpen,
  onClose,
  currentSubscription,
  onSubscriptionUpdate,
}) => {
  const [plans, setPlans] = useState([]);
  const [paymentHistory, setPaymentHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [paymentLoading, setPaymentLoading] = useState(null);
  const [error, setError] = useState(null);
  const [activeView, setActiveView] = useState("plans"); // 'plans' | 'history'

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const [plansRes, historyRes] = await Promise.all([
        getPlans(),
        getPaymentHistory().catch(() => ({ data: { payments: [] } })),
      ]);

      const rawPlans = plansRes?.data?.plans || plansRes?.plans || (Array.isArray(plansRes) ? plansRes : []);
      const allowedRecruiterPlanSlugs = new Set(["free", "professional", "recruiter-max"]);
      const filteredPlans = rawPlans.filter((plan) =>
        allowedRecruiterPlanSlugs.has(String(plan?.slug || "").toLowerCase()),
      );
      setPlans(filteredPlans);

      if (historyRes?.data?.payments) {
        setPaymentHistory(historyRes.data.payments);
      }
    } catch (err) {
      console.error("Error loading plans:", err);
      setError("Failed to load plans. Please try again.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      loadData();
    }
  }, [isOpen, loadData]);

  const handleUpgrade = async (planId) => {
    try {
      setPaymentLoading(planId);
      setError(null);

      const response = await initiatePayment(planId);

      if (response?.data?.checkout_url) {
        // Redirect to Stripe checkout
        window.location.href = response.data.checkout_url;
      } else if (response?.checkout_url) {
        window.location.href = response.checkout_url;
      } else {
        // If no checkout URL, plan might be free - refresh subscription
        if (onSubscriptionUpdate) {
          const newSub = await getCurrentSubscription();
          onSubscriptionUpdate(
            newSub?.data?.subscription || newSub?.subscription
          );
        }
        onClose();
      }
    } catch (err) {
      console.error("Error initiating payment:", err);
      setError(err.message || "Failed to process payment. Please try again.");
    } finally {
      setPaymentLoading(null);
    }
  };

  const formatPrice = (price) => {
    if (price === 0) return "Free";
    return `$${price.toFixed(2)}`;
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return "-";
    return new Date(dateStr).toLocaleDateString("en-IN", { timeZone: "Asia/Kolkata",
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  };

  const isCurrentPlan = (plan) => {
    if (!currentSubscription?.plan) return plan.slug === "free";
    return (
      currentSubscription.plan.slug === plan.slug ||
      currentSubscription.plan.id === plan.id
    );
  };

  if (!isOpen) return null;

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className={styles.header}>
          <div className={styles.headerContent}>
            <h2>
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="M12 2L15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2z" />
              </svg>
              Subscription Plans
            </h2>
            <p>Choose the plan that fits your hiring needs</p>
          </div>
          <button className={styles.closeButton} onClick={onClose}>
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Tab Navigation */}
        <div className={styles.tabNav}>
          <button
            className={`${styles.tab} ${
              activeView === "plans" ? styles.active : ""
            }`}
            onClick={() => setActiveView("plans")}
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <path d="M9 9h6" />
              <path d="M9 15h6" />
            </svg>
            Plans
          </button>
          <button
            className={`${styles.tab} ${
              activeView === "history" ? styles.active : ""
            }`}
            onClick={() => setActiveView("history")}
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
            Payment History
          </button>
        </div>

        {/* Content */}
        <div className={styles.content}>
          {error && (
            <div className={styles.errorBanner}>
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              {error}
            </div>
          )}

          {loading ? (
            <div className={styles.loading}>
              <div className={styles.spinner}></div>
              <p>Loading plans...</p>
            </div>
          ) : activeView === "plans" ? (
            <div className={styles.plansGrid}>
              {plans.map((plan) => {
                const isCurrent = isCurrentPlan(plan);
                const isFeaturedPlan = plan.slug === "recruiter-max";

                return (
                  <div
                    key={plan.id || plan.slug}
                    className={`${styles.planCard} ${
                      isCurrent ? styles.current : ""
                    } ${isFeaturedPlan ? styles.featured : ""}`}
                  >
                    {isFeaturedPlan && (
                      <div className={styles.featuredBadge}>
                        <svg
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                        >
                          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
                        </svg>
                        Recommended
                      </div>
                    )}

                    {isCurrent && (
                      <div className={styles.currentBadge}>
                        <svg
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                        >
                          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                          <polyline points="22 4 12 14.01 9 11.01" />
                        </svg>
                        Current Plan
                      </div>
                    )}

                    <div className={styles.planHeader}>
                      <h3>{plan.name}</h3>
                      <p className={styles.planDescription}>
                        {plan.description}
                      </p>
                    </div>

                    <div className={styles.planPricing}>
                      <span className={styles.price}>
                        {formatPrice(plan.price)}
                      </span>
                      {plan.price > 0 && (
                        <span className={styles.period}>
                          / {plan.validity_days} days
                        </span>
                      )}
                    </div>

                    <div className={styles.planInterviews}>
                      <div className={styles.interviewCount}>
                        {plan.is_unlimited ? (
                          <>
                            <svg
                              viewBox="0 0 24 24"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="2"
                              className={styles.infinityIcon}
                            >
                              <path d="M18.178 8c5.096 0 5.096 8 0 8-5.095 0-7.133-8-12.739-8-4.585 0-4.585 8 0 8 5.606 0 7.644-8 12.74-8z" />
                            </svg>
                            Unlimited
                          </>
                        ) : (
                          <>
                            <strong>{plan.interviews_allowed}</strong>
                          </>
                        )}
                      </div>
                      <span className={styles.interviewLabel}>
                        AI Interviews
                      </span>
                    </div>

                    <ul className={styles.features}>
                      {plan.features?.map((feature, idx) => (
                        <li key={idx}>
                          <svg
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                          >
                            <polyline points="20 6 9 17 4 12" />
                          </svg>
                          {feature}
                        </li>
                      ))}
                    </ul>

                    <button
                      className={`${styles.selectButton} ${
                        isCurrent ? styles.disabled : ""
                      } ${isFeaturedPlan ? styles.primary : ""}`}
                      onClick={() => !isCurrent && handleUpgrade(plan.id)}
                      disabled={isCurrent || paymentLoading === plan.id}
                    >
                      {paymentLoading === plan.id ? (
                        <>
                          <span className={styles.btnSpinner}></span>
                          Processing...
                        </>
                      ) : isCurrent ? (
                        "Current Plan"
                      ) : plan.price === 0 ? (
                        "Select Free Plan"
                      ) : (
                        <>
                          <svg
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                          >
                            <line x1="12" y1="19" x2="12" y2="5" />
                            <polyline points="5 12 12 5 19 12" />
                          </svg>
                          Upgrade Now
                        </>
                      )}
                    </button>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className={styles.historySection}>
              {paymentHistory.length === 0 ? (
                <div className={styles.emptyHistory}>
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <rect x="1" y="4" width="22" height="16" rx="2" ry="2" />
                    <line x1="1" y1="10" x2="23" y2="10" />
                  </svg>
                  <h4>No payment history</h4>
                  <p>Your payment transactions will appear here</p>
                </div>
              ) : (
                <table className={styles.historyTable}>
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Plan</th>
                      <th>Amount</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paymentHistory.map((payment, idx) => (
                      <tr key={payment.id || idx}>
                        <td>{formatDate(payment.created_at)}</td>
                        <td>{payment.plan_name || "Plan"}</td>
                        <td>{formatPrice(payment.amount / 100)}</td>
                        <td>
                          <span
                            className={`${styles.status} ${
                              styles[payment.status]
                            }`}
                          >
                            {payment.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className={styles.footer}>
          <p>
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
            Secure payment powered by Stripe
          </p>
        </div>
      </div>
    </div>
  );
};

export default UpgradePlanModal;
