import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../../components/Navbar";
import { useCandidateSubscription } from "../../components/candidate/subscription";
import {
  PlanCard,
  PaymentHistory,
  ArrowLeftIcon,
  StarIcon,
  GridIcon,
  ClockIcon,
  AlertCircleIcon,
  LockIcon,
} from "../../components/payment";
import { useRazorpay } from "../../hooks/useRazorpay";
import { getPlans, getPaymentHistory } from "../../services/payment";
import styles from "../SubscriptionPlans.module.css";

const TABS = [
  { id: "plans", label: "Plans", icon: GridIcon },
  { id: "history", label: "Payment History", icon: ClockIcon },
];

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

const LoadingState = ({ message = "Loading..." }) => (
  <div className={styles.loadingContainer}>
    <div className={styles.spinner} />
    <p>{message}</p>
  </div>
);

const PlansGrid = ({ plans, subscription, loadingPlanId, onSelectPlan }) => {
  const isCurrentPlan = (plan) => {
    if (!subscription?.plan) return plan.slug === "candidate-free";
    return (
      subscription.plan.slug === plan.slug || subscription.plan.id === plan.id
    );
  };

  return (
    <div className={styles.plansGrid}>
      {plans.map((plan) => (
        <PlanCard
          key={plan.id || plan.slug}
          plan={plan}
          isCurrent={isCurrentPlan(plan)}
          isPopular={plan.slug === "candidate-pro" || plan.is_popular}
          isLoading={loadingPlanId === (plan.id || plan.slug)}
          onSelect={onSelectPlan}
        />
      ))}
    </div>
  );
};

const Footer = () => (
  <div className={styles.footer}>
    <div className={styles.secureNote}>
      <LockIcon />
      Secure payment powered by Razorpay
    </div>
  </div>
);

const CandidateSubscriptionPlans = () => {
  const navigate = useNavigate();
  const { subscription, refresh: refreshSubscription } =
    useCandidateSubscription();

  const [plans, setPlans] = useState([]);
  const [paymentHistory, setPaymentHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeView, setActiveView] = useState("plans");

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

  const displayError = error || paymentError;

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const [plansRes, historyRes] = await Promise.all([
        getPlans().catch(() => null),
        getPaymentHistory().catch(() => ({ payments: [] })),
      ]);

      let normalizedPlans =
        plansRes?.data?.plans ||
        plansRes?.plans ||
        (Array.isArray(plansRes) ? plansRes : []);

      normalizedPlans = normalizedPlans.filter(
        (plan) =>
          plan?.audience === "candidate" ||
          String(plan?.slug || "").startsWith("candidate-"),
      );

      if (!normalizedPlans || normalizedPlans.length === 0) {
        normalizedPlans = [];
        setError("No candidate subscription plans available right now.");
      }

      setPlans(normalizedPlans);

      const normalizedHistory =
        historyRes?.data?.payments ||
        historyRes?.payments ||
        (Array.isArray(historyRes) ? historyRes : []);
      setPaymentHistory(normalizedHistory);
    } catch (err) {
      console.error("Error loading candidate subscription data:", err);
      setPlans([]);
      setError("Failed to load subscription data. Please try again.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    clearPaymentError();
  }, [activeView, clearPaymentError]);

  const handleSelectPlan = useCallback(
    (planId) => {
      checkout(planId);
    },
    [checkout],
  );

  const handleRetry = useCallback(() => {
    setError(null);
    clearPaymentError();
    loadData();
  }, [loadData, clearPaymentError]);

  return (
    <div className={styles.pageContainer}>
      <Navbar userType="candidate" />

      <div className={styles.content}>
        <header className={styles.pageHeader}>
          <button
            className={styles.backButton}
            onClick={() => navigate("/dashboard")}
            aria-label="Back to Dashboard"
          >
            <ArrowLeftIcon />
            Back to Dashboard
          </button>
          <div className={styles.headerText}>
            <h1>
              <StarIcon />
              Candidate Subscription Plans
            </h1>
            <p>Choose the best plan for your practice interview preparation</p>
          </div>
        </header>

        <TabNav activeView={activeView} onChangeView={setActiveView} />

        {displayError && (
          <ErrorAlert message={displayError} onRetry={handleRetry} />
        )}

        {loading ? (
          <LoadingState message="Loading candidate subscription data..." />
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

        <Footer />
      </div>
    </div>
  );
};

export default CandidateSubscriptionPlans;
