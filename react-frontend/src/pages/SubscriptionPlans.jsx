/**
 * SubscriptionPlans - Dedicated page for subscription management
 * Clean, decoupled architecture using custom hooks and components
 */
import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import { useSubscription } from "../components/recruiter/subscription";
import {
  PlanCard,
  PaymentHistory,
  ArrowLeftIcon,
  StarIcon,
  GridIcon,
  ClockIcon,
  AlertCircleIcon,
  LockIcon,
} from "../components/payment";
import { useRazorpay } from "../hooks/useRazorpay";
import { getPlans, getPaymentHistory } from "../services/payment";
import styles from "./SubscriptionPlans.module.css";

// View tabs configuration
const TABS = [
  { id: "plans", label: "Plans", icon: GridIcon },
  { id: "history", label: "Payment History", icon: ClockIcon },
];

/**
 * Tab Navigation Component
 */
const TabNav = ({ activeView, onChangeView }) => (
  <div className={styles.tabNav}>
    {TABS.map(({ id, label, icon: Icon }) => (
      <button
        key={id}
        className={`${styles.tab} ${activeView === id ? styles.active : ""}`}
        onClick={() => onChangeView(id)}
      >
        <Icon />
        {label}
      </button>
    ))}
  </div>
);

/**
 * Error Alert Component
 */
const ErrorAlert = ({ message, onRetry }) => (
  <div className={styles.errorMessage}>
    <AlertCircleIcon />
    {message}
    {onRetry && (
      <button onClick={onRetry} className={styles.retryButton}>
        Retry
      </button>
    )}
  </div>
);

/**
 * Loading Spinner Component
 */
const LoadingState = ({ message = "Loading..." }) => (
  <div className={styles.loadingContainer}>
    <div className={styles.spinner} />
    <p>{message}</p>
  </div>
);

/**
 * Empty Plans State Component
 */
const EmptyPlans = () => (
  <div className={styles.noPlans}>
    <AlertCircleIcon />
    <h3>No plans available</h3>
    <p>Please check back later or contact support.</p>
  </div>
);

/**
 * Plans Grid Component
 */
const PlansGrid = ({ plans, subscription, loadingPlanId, onSelectPlan }) => {
  const isCurrentPlan = (plan) => {
    if (!subscription?.plan) return plan.slug === "free";
    return (
      subscription.plan.slug === plan.slug || subscription.plan.id === plan.id
    );
  };

  if (plans.length === 0) {
    return <EmptyPlans />;
  }

  return (
    <div className={styles.plansGrid}>
      {plans.map((plan) => (
        <PlanCard
          key={plan.id || plan.slug}
          plan={plan}
          isCurrent={isCurrentPlan(plan)}
          isPopular={plan.slug === "professional" || plan.is_popular}
          isLoading={loadingPlanId === (plan.id || plan.slug)}
          onSelect={onSelectPlan}
        />
      ))}
    </div>
  );
};

/**
 * Page Footer Component
 */
const Footer = () => (
  <div className={styles.footer}>
    <div className={styles.secureNote}>
      <LockIcon />
      Secure payment powered by Razorpay
    </div>
  </div>
);

/**
 * Main SubscriptionPlans Component
 */
const SubscriptionPlans = () => {
  const navigate = useNavigate();

  // Subscription state from shared hook
  const { subscription, refresh: refreshSubscription } = useSubscription();

  // Local state
  const [plans, setPlans] = useState([]);
  const [paymentHistory, setPaymentHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeView, setActiveView] = useState("plans");

  // Razorpay hook with callbacks
  const {
    checkout,
    loading: paymentLoading,
    error: paymentError,
    clearError: clearPaymentError,
  } = useRazorpay({
    onSuccess: async ({ paymentId, orderId, free }) => {
      await loadData();
      refreshSubscription();

      if (!free) {
        navigate("/payment/success", {
          state: { payment_id: paymentId, order_id: orderId },
        });
      }
    },
    onError: (err) => {
      console.error("Payment error:", err);
    },
  });

  // Combined error state
  const displayError = error || paymentError;

  /**
   * Load plans and payment history
   */
  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const [plansRes, historyRes] = await Promise.all([
        getPlans(),
        getPaymentHistory().catch(() => ({ payments: [] })),
      ]);

      // Normalize plans response
      const normalizedPlans =
        plansRes?.data?.plans ||
        plansRes?.plans ||
        (Array.isArray(plansRes) ? plansRes : []);
      setPlans(normalizedPlans);
      console.log("Fetched plans:", normalizedPlans); 
      console.log("Fetched plansres:", plansRes);

      // Normalize history response
      const normalizedHistory =
        historyRes?.data?.payments ||
        historyRes?.payments ||
        (Array.isArray(historyRes) ? historyRes : []);
      setPaymentHistory(normalizedHistory);
    } catch (err) {
      console.error("Error loading subscription data:", err);
      setError("Failed to load subscription data. Please try again.");
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial data load
  useEffect(() => {
    loadData();
  }, [loadData]);

  // Clear payment error when switching views
  useEffect(() => {
    clearPaymentError();
  }, [activeView, clearPaymentError]);

  /**
   * Handle plan selection
   */
  const handleSelectPlan = useCallback(
    (planId) => {
      checkout(planId);
    },
    [checkout],
  );

  /**
   * Handle retry after error
   */
  const handleRetry = useCallback(() => {
    setError(null);
    clearPaymentError();
    loadData();
  }, [loadData, clearPaymentError]);

  return (
    <div className={styles.pageContainer}>
      <Navbar userType="recruiter" />

      <div className={styles.content}>
        {/* Page Header */}
        <header className={styles.pageHeader}>
          <button
            className={styles.backButton}
            onClick={() => navigate("/recruiter-dashboard")}
            aria-label="Back to Dashboard"
          >
            <ArrowLeftIcon />
            Back to Dashboard
          </button>
          <div className={styles.headerText}>
            <h1>
              <StarIcon />
              Subscription Plans
            </h1>
            <p>Choose the plan that fits your hiring needs</p>
          </div>
        </header>

        {/* Tab Navigation */}
        <TabNav activeView={activeView} onChangeView={setActiveView} />

        {/* Error Display */}
        {displayError && (
          <ErrorAlert message={displayError} onRetry={handleRetry} />
        )}

        {/* Main Content */}
        {loading ? (
          <LoadingState message="Loading subscription data..." />
        ) : activeView === "plans" ? (
          <PlansGrid
            plans={plans}
            subscription={subscription}
            loadingPlanId={paymentLoading}
            onSelectPlan={handleSelectPlan}
          />
        ) : (
          <PaymentHistory payments={paymentHistory} />
        )}

        {/* Footer */}
        <Footer />
      </div>
    </div>
  );
};

export default SubscriptionPlans;
