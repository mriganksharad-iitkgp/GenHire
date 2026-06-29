/**
 * SubscriptionPlans - Dedicated page for wallet recharge management
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
import {
  getPlans,
  getPaymentHistory,
  getCreditTransactions,
} from "../services/payment";
import styles from "./SubscriptionPlans.module.css";

// View tabs configuration
const TABS = [
  { id: "plans", label: "Recharge Packs", icon: GridIcon },
  { id: "transactions", label: "Credit Activity", icon: ClockIcon },
  { id: "history", label: "Payment History", icon: ClockIcon },
];

const getRecruiterSignupBonusPlan = () => ({
  id: "recruiter-signup-bonus",
  slug: "recruiter-signup-bonus",
  name: "Signup Bonus",
  description: "One-time welcome credits added automatically at signup",
  price: 0,
  recharge_credits: 100,
  disable_action: true,
  cta_label: "Included at Signup",
});

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

const CreditSummary = ({ subscription }) => {
  const creditsRemaining = Number(
    subscription?.credits_remaining ?? subscription?.interviews_remaining ?? 0,
  );
  const creditsAllocated = Number(
    subscription?.credits_allocated ?? subscription?.interviews_allowed ?? 0,
  );
  const creditsUsed = Number(
    subscription?.credits_used ?? subscription?.interviews_used ?? 0,
  );

  const stats = [
    {
      label: "Credits Remaining",
      value: creditsRemaining.toLocaleString("en-IN"),
    },
    { label: "Credits Used", value: creditsUsed.toLocaleString("en-IN") },
    {
      label: "Total Credited",
      value: creditsAllocated.toLocaleString("en-IN"),
    },
    { label: "Total Debited", value: creditsUsed.toLocaleString("en-IN") },
  ];

  return (
    <section className={styles.creditSummary}>
      {stats.map((item) => (
        <article key={item.label} className={styles.creditStatCard}>
          <p>{item.label}</p>
          <h3>{item.value}</h3>
        </article>
      ))}
    </section>
  );
};

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
  if (plans.length === 0) {
    return <EmptyPlans />;
  }

  return (
    <div className={styles.plansGrid}>
      {plans.map((plan) => (
        <PlanCard
          key={plan.id || plan.slug}
          plan={plan}
          isCurrent={false}
          isPopular={plan.slug === "recruiter-pro" || plan.is_popular}
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

const CreditTransactions = ({ items }) => {
  if (!items?.length) {
    return <div className={styles.noPlans}>No credit transactions yet.</div>;
  }

  return (
    <div className={styles.paymentHistoryWrapper}>
      <table className={styles.historyTable}>
        <thead>
          <tr>
            <th>Date</th>
            <th>Type</th>
            <th>Delta</th>
            <th>Balance</th>
          </tr>
        </thead>
        <tbody>
          {items.map((tx) => (
            <tr key={tx.id}>
              <td>{tx.created_at ? new Date(tx.created_at).toLocaleString() : "-"}</td>
              <td>{tx.transaction_type || "-"}</td>
              <td>{Number(tx.delta_credits || 0) > 0 ? `+${tx.delta_credits}` : tx.delta_credits}</td>
              <td>{tx.balance_after ?? 0}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

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
  const [creditTransactions, setCreditTransactions] = useState([]);
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

  // Fallback plans when API is unavailable
  const getFallbackPlans = () => [
    getRecruiterSignupBonusPlan(),
    {
      id: "recruiter-pro",
      slug: "recruiter-pro",
      name: "Recruiter Pro",
      description: "5,000 non-expiring credits",
      price: 4999,
      currency: "INR",
      interval: "one_time",
      features: [
        { name: "5,000 non-expiring credits", included: true },
        { name: "AI JD generation", included: true },
        { name: "Real interview billing", included: true },
      ],
      credits_allocated: 5000,
      interviews_allowed: 5000,
      is_popular: true,
    },
    {
      id: "recruiter-max",
      slug: "recruiter-max",
      name: "Recruiter Max",
      description: "10,000 non-expiring credits",
      price: 9999,
      currency: "INR",
      interval: "one_time",
      features: [
        { name: "10,000 non-expiring credits", included: true },
        { name: "AI JD generation", included: true },
        { name: "Real interview billing", included: true },
      ],
      credits_allocated: 10000,
      interviews_allowed: 10000,
      is_popular: false,
    },
  ];

  /**
   * Load plans and payment history
   */
  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const [plansRes, historyRes, txRes] = await Promise.all([
        getPlans().catch(() => null),
        getPaymentHistory().catch(() => ({ payments: [] })),
        getCreditTransactions().catch(() => ({ transactions: [] })),
      ]);

      // Normalize plans response or use fallback
      let normalizedPlans =
        plansRes?.data?.plans ||
        plansRes?.plans ||
        (Array.isArray(plansRes) ? plansRes : []);

      // Use fallback plans if API returned empty or failed
      if (!normalizedPlans || normalizedPlans.length === 0) {
        normalizedPlans = getFallbackPlans();
      }

      const allowedRecruiterPlanSlugs = new Set([
        "recruiter-pro",
        "recruiter-max",
      ]);
      const recruiterPlans = normalizedPlans.filter((plan) =>
        allowedRecruiterPlanSlugs.has(String(plan?.slug || "").toLowerCase()),
      );

      setPlans([getRecruiterSignupBonusPlan(), ...recruiterPlans]);

      // Normalize history response
      const normalizedHistory =
        historyRes?.data?.payments ||
        historyRes?.payments ||
        (Array.isArray(historyRes) ? historyRes : []);
      setPaymentHistory(normalizedHistory);

      const normalizedTx =
        txRes?.data?.transactions ||
        txRes?.transactions ||
        (Array.isArray(txRes) ? txRes : []);
      setCreditTransactions(normalizedTx);
    } catch (err) {
      console.error("Error loading wallet data:", err);
      // Use fallback plans even on error
      setPlans(getFallbackPlans());
      setError("Failed to load recharge wallet data. Please try again.");
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
              Recruiter Recharge Packs
            </h1>
            <p>Top up your wallet with non-expiring recruiter credits</p>
          </div>
        </header>

        {/* Tab Navigation */}
        <TabNav activeView={activeView} onChangeView={setActiveView} />

        <CreditSummary subscription={subscription} />

        {/* Error Display */}
        {displayError && (
          <ErrorAlert message={displayError} onRetry={handleRetry} />
        )}

        {/* Main Content */}
        {loading ? (
          <LoadingState message="Loading recharge wallet data..." />
        ) : activeView === "plans" ? (
          <PlansGrid
            plans={plans}
            subscription={subscription}
            loadingPlanId={paymentLoading}
            onSelectPlan={handleSelectPlan}
          />
        ) : activeView === "transactions" ? (
          <CreditTransactions items={creditTransactions} />
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
