import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import {
  SubscriptionBanner,
  useSubscription,
} from "../components/recruiter/subscription";
import styles from "./SubscriptionPlans.module.css";
import {
  getPlans,
  initiatePayment,
  getPaymentHistory,
} from "../services/payment";

/**
 * SubscriptionPlans - Dedicated page for subscription management
 * Uses existing subscription components for consistency
 */
const SubscriptionPlans = () => {
  const navigate = useNavigate();
  
  // Use the shared subscription hook
  const {
    subscription,
    loading: subscriptionLoading,
    refresh: refreshSubscription,
  } = useSubscription();

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

      // Handle plans response
      if (plansRes?.data?.plans) {
        setPlans(plansRes.data.plans);
      } else if (plansRes?.plans) {
        setPlans(plansRes.plans);
      } else if (Array.isArray(plansRes)) {
        setPlans(plansRes);
      }

      // Handle payment history
      if (historyRes?.data?.payments) {
        setPaymentHistory(historyRes.data.payments);
      } else if (historyRes?.payments) {
        setPaymentHistory(historyRes.payments);
      } else if (Array.isArray(historyRes)) {
        setPaymentHistory(historyRes);
      }

      // Subscription is handled by useSubscription hook
    } catch (err) {
      console.error("Error loading subscription data:", err);
      setError("Failed to load subscription data. Please try again.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleUpgrade = async (planId) => {
    try {
      setPaymentLoading(planId);
      setError(null);

      const response = await initiatePayment(planId);

      if (response?.data?.checkout_url) {
        window.location.href = response.data.checkout_url;
      } else if (response?.checkout_url) {
        window.location.href = response.checkout_url;
      } else {
        // If no checkout URL, plan might be free - refresh subscription
        await loadData();
        refreshSubscription();
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
    return new Date(dateStr).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  };

  const isCurrentPlan = (plan) => {
    if (!subscription?.plan) return plan.slug === "free";
    return (
      subscription.plan.slug === plan.slug ||
      subscription.plan.id === plan.id
    );
  };

  const getPlanFeatures = (plan) => {
    const features = [];
    
    if (plan.interviews_allowed === -1 || plan.is_unlimited) {
      features.push({ text: "Unlimited AI Interviews", included: true });
    } else {
      features.push({ text: `${plan.interviews_allowed} AI Interviews`, included: true });
    }
    
    features.push({ text: "Smart CV Matching", included: true });
    features.push({ text: "Candidate Analytics", included: plan.price > 0 });
    features.push({ text: "Priority Support", included: plan.price >= 49 });
    features.push({ text: "Custom Branding", included: plan.price >= 99 });
    features.push({ text: "API Access", included: plan.price >= 99 });
    
    return features;
  };

  return (
    <div className={styles.pageContainer}>
      <Navbar userType="recruiter" />
      
      <div className={styles.content}>
        {/* Page Header */}
        <div className={styles.pageHeader}>
          <button className={styles.backButton} onClick={() => navigate("/recruiter-dashboard")}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
            Back to Dashboard
          </button>
          <div className={styles.headerText}>
            <h1>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 2L15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2z" />
              </svg>
              Subscription Plans
            </h1>
            <p>Choose the plan that fits your hiring needs</p>
          </div>
        </div>

        {/* Current Plan Banner - Using the existing component */}
        <div className={styles.bannerWrapper}>
          <SubscriptionBanner
            subscription={subscription}
            loading={subscriptionLoading}
            onUpgrade={() => {}} // Already on upgrade page
          />
        </div>

        {/* Tab Navigation */}
        <div className={styles.tabNav}>
          <button
            className={`${styles.tab} ${activeView === "plans" ? styles.active : ""}`}
            onClick={() => setActiveView("plans")}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <path d="M3 9h18M9 21V9" />
            </svg>
            Plans
          </button>
          <button
            className={`${styles.tab} ${activeView === "history" ? styles.active : ""}`}
            onClick={() => setActiveView("history")}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12,6 12,12 16,14" />
            </svg>
            Payment History
          </button>
        </div>

        {/* Error Message */}
        {error && (
          <div className={styles.errorMessage}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            {error}
            <button onClick={loadData} className={styles.retryButton}>
              Retry
            </button>
          </div>
        )}

        {/* Loading State */}
        {loading ? (
          <div className={styles.loadingContainer}>
            <div className={styles.spinner}></div>
            <p>Loading subscription data...</p>
          </div>
        ) : activeView === "plans" ? (
          /* Plans Grid */
          <div className={styles.plansGrid}>
            {plans.length === 0 ? (
              <div className={styles.noPlans}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
                <h3>No plans available</h3>
                <p>Please check back later or contact support.</p>
              </div>
            ) : (
              plans.map((plan) => {
                const isCurrent = isCurrentPlan(plan);
                const features = getPlanFeatures(plan);
                const isPopular = plan.slug === "professional" || plan.is_popular;

                return (
                  <div
                    key={plan.id || plan.slug}
                    className={`${styles.planCard} ${isCurrent ? styles.currentPlan : ""} ${isPopular ? styles.popular : ""}`}
                  >
                    {isPopular && (
                      <div className={styles.popularBadge}>Most Popular</div>
                    )}
                    
                    <div className={styles.planHeader}>
                      <h3>{plan.name}</h3>
                      <p className={styles.planDescription}>
                        {plan.description || "Perfect for your hiring needs"}
                      </p>
                    </div>

                    <div className={styles.planPrice}>
                      <span className={styles.amount}>{formatPrice(plan.price)}</span>
                      {plan.price > 0 && (
                        <span className={styles.period}>/{plan.billing_period || "month"}</span>
                      )}
                    </div>

                    <ul className={styles.featuresList}>
                      {features.map((feature, idx) => (
                        <li key={idx} className={feature.included ? styles.included : styles.notIncluded}>
                          {feature.included ? (
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <polyline points="20,6 9,17 4,12" />
                            </svg>
                          ) : (
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <line x1="18" y1="6" x2="6" y2="18" />
                              <line x1="6" y1="6" x2="18" y2="18" />
                            </svg>
                          )}
                          {feature.text}
                        </li>
                      ))}
                    </ul>

                    <button
                      className={`${styles.selectButton} ${isCurrent ? styles.currentButton : ""}`}
                      onClick={() => !isCurrent && handleUpgrade(plan.id || plan.slug)}
                      disabled={isCurrent || paymentLoading === (plan.id || plan.slug)}
                    >
                      {paymentLoading === (plan.id || plan.slug) ? (
                        <>
                          <div className={styles.buttonSpinner}></div>
                          Processing...
                        </>
                      ) : isCurrent ? (
                        <>
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <polyline points="20,6 9,17 4,12" />
                          </svg>
                          Current Plan
                        </>
                      ) : (
                        <>
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M12 2L15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2z" />
                          </svg>
                          {plan.price === 0 ? "Select Plan" : "Upgrade Now"}
                        </>
                      )}
                    </button>
                  </div>
                );
              })
            )}
          </div>
        ) : (
          /* Payment History */
          <div className={styles.historyContainer}>
            {paymentHistory.length === 0 ? (
              <div className={styles.noHistory}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                  <line x1="16" y1="2" x2="16" y2="6" />
                  <line x1="8" y1="2" x2="8" y2="6" />
                  <line x1="3" y1="10" x2="21" y2="10" />
                </svg>
                <h3>No payment history</h3>
                <p>Your payment history will appear here after your first transaction.</p>
              </div>
            ) : (
              <div className={styles.historyTable}>
                <div className={styles.tableHeader}>
                  <span>Date</span>
                  <span>Plan</span>
                  <span>Amount</span>
                  <span>Status</span>
                </div>
                {paymentHistory.map((payment, idx) => (
                  <div key={idx} className={styles.tableRow}>
                    <span>{formatDate(payment.created_at)}</span>
                    <span>{payment.plan_name || "Subscription"}</span>
                    <span>{formatPrice(payment.amount)}</span>
                    <span className={`${styles.status} ${styles[payment.status?.toLowerCase()]}`}>
                      {payment.status}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Footer */}
        <div className={styles.footer}>
          <div className={styles.secureNote}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
            Secure payment powered by Stripe
          </div>
        </div>
      </div>
    </div>
  );
};

export default SubscriptionPlans;
