import PortalPageHeader from "shared/components/ui/PortalPageHeader";
import usePricingCatalog from "shared/hooks/usePricingCatalog";
/**
 * SubscriptionPlans - Dedicated page for wallet recharge management
 * Clean, decoupled architecture using custom hooks and components
 */
import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "shared/components/layout/Navbar";
import { useSubscription } from "features/payment/components/recruiter-subscription";
import {
  PlanCard,
  PaymentHistory,
  ArrowLeftIcon,
  GridIcon,
  ClockIcon,
  AlertCircleIcon,
  LockIcon,
} from "features/payment/components";
import { useRazorpay } from "features/payment/hooks/useRazorpay";
import {
  getPlans,
  getPaymentHistory,
  getCreditTransactions,
} from "features/payment/api";
import styles from "./SubscriptionPlans.module.css";

// View tabs configuration
const TABS = [
  { id: "plans", label: "Recharge Packs", icon: GridIcon },
  { id: "transactions", label: "Credit Activity", icon: ClockIcon },
  { id: "history", label: "Payment History", icon: ClockIcon },
];

const getRecruiterSignupBonusPlan = (credits) => ({
  id: "recruiter-signup-bonus",
  slug: "recruiter-signup-bonus",
  name: "Signup Bonus",
  description: "One-time welcome credits added automatically at signup",
  price: 0,
  recharge_credits: credits,
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
              <td>{tx.created_at ? new Date(tx.created_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' }) : "-"}</td>
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
  const {catalog, error:pricingError, reload:reloadPricing} = usePricingCatalog();
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
  const displayError = error || paymentError || pricingError;

  // Load authoritative prices; an outage leaves paid packs unavailable.
  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const [plansRes, historyRes, txRes] = await Promise.all([
        getPlans().catch(() => null),
        getPaymentHistory().catch(() => ({ payments: [] })),
        getCreditTransactions().catch(() => ({ transactions: [] })),
      ]);

      // Display only plans returned by the service.
      let normalizedPlans =
        plansRes?.data?.plans ||
        plansRes?.plans ||
        (Array.isArray(plansRes) ? plansRes : []);

      // Missing server prices must not become purchasable fallback offers.
      if (!normalizedPlans || normalizedPlans.length === 0) {
        normalizedPlans = [];
        setError("Recharge prices are unavailable. Retry to load current packs before paying.");
      }

      const allowedRecruiterPlanSlugs = new Set([
        "recruiter-pro",
        "recruiter-max",
      ]);
      const recruiterPlans = normalizedPlans.filter((plan) =>
        allowedRecruiterPlanSlugs.has(String(plan?.slug || "").toLowerCase()),
      );

      setPlans(recruiterPlans);

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
      // Never display invented prices after a plan-service failure.
      setPlans([]);
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
    reloadPricing();
  }, [loadData, clearPaymentError, reloadPricing]);

  return (
    <div className={styles.pageContainer}>
      <Navbar userType="recruiter" />

      <div className={styles.content}>
        {/* Page Header */}
        <header className={styles.pageHeader}>
          <button
            className={styles.backButton}
            onClick={() => navigate("/recruiter/dashboard")}
            aria-label="Back to Dashboard"
          >
            <ArrowLeftIcon />
            Back to Dashboard
          </button>
          <PortalPageHeader title="Recharge your wallet" eyebrow="Recruiter credits" icon="fa-credit-card" subtitle="Fund screening and available OAs. Setup, accepted attempts and optional extras have separate quotes; review wallet history here." />
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
            plans={[...(Number.isInteger(catalog?.credits?.signup_bonus) ? [getRecruiterSignupBonusPlan(catalog.credits.signup_bonus)] : []), ...plans]}
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
