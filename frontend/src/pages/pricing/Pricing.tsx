import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import logo from "../../assets/logo.png";
import { tokenStore } from "../../api/axios";
import {
  activateFreePlan,
  changePlan,
  createCheckoutSession,
  cancelSubcription,
  fetchCredits,
  fetchPlans,
  fetchSubscription,
  type Plan,
} from "../../services/billing_api";
import CancelSubscriptionModal from "./CancelSubscriptionModal";
import "../landing/Landing.css";
import "./Pricing.css";

const PLAN_FEATURES: Record<string, string[]> = {
  free: [
    "100 credits included (one-time)",
    "Upload PDF, DOCX, TXT, CSV, XLSX",
    "Per-document & global chat",
    "AI-powered citations",
  ],
  basic: [
    "200 credits / week",
    "Everything in Free",
  ],
  pro: [
    "400 credits / month",
    "Everything in Basic",
    "Higher usage limits",
    "Priority support",
  ],
};

export default function Pricing() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const isLoggedIn = Boolean(tokenStore.getToken());

  const [plans, setPlans] = useState<Plan[]>([]);
  const [currentPlan, setCurrentPlan] = useState<string | null>(null);
  const [subscriptionActive, setSubscriptionActive] = useState<boolean | null>(null);
  const [canUseFree, setCanUseFree] = useState(true);
  const [credits, setCredits] = useState<number | null>(null);
  const [loadingPlan, setLoadingPlan] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [cancelScheduled, setCancelScheduled] = useState(false);
  const [cancelingSubscription, setCancelingSubscription] = useState(false);
  const [cancelModal, setCancelModal] = useState<{
    open: boolean;
    mode: "confirm" | "success" | "error";
    title: string;
    message: string;
  }>({
    open: false,
    mode: "confirm",
    title: "",
    message: "",
  });

  const loadUserBilling = () => {
    if (!isLoggedIn) return;
    Promise.all([fetchCredits(), fetchSubscription()])
      .then(([creditsData, subData]) => {
        setCredits(creditsData.credits);
        setCurrentPlan(creditsData.plan);
        setSubscriptionActive(creditsData.subscription_active);
        setCanUseFree(subData.can_use_free);
              })
      .catch(() => {});
  };

  useEffect(() => {
    fetchPlans()
      .then(setPlans)
      .catch(() => setError("Unable to load plans. Please refresh the page."));

    loadUserBilling();
  }, [isLoggedIn]);

  useEffect(() => {
    if (searchParams.get("success") === "true") {
      setNotice("Subscription activated! Your credits have been updated.");
      loadUserBilling();
    } else if (searchParams.get("canceled") === "true") {
      setNotice("Checkout was canceled. No charges were made.");
    }
  }, [searchParams]);

  const hasPaidSubscription =
    subscriptionActive === true &&
    (currentPlan === "basic" || currentPlan === "pro");

  const handleSelectPlan = async (planId: string) => {
    setError(null);

    if (planId === "free") {
      if (!isLoggedIn) {
        navigate("/login?mode=signup&next=/pricing");
        return;
      }
      if (!canUseFree) return;

      setLoadingPlan(planId);
      try {
        const result = await activateFreePlan();
        setCurrentPlan(result.plan);
        setCredits(result.credits);
        setCanUseFree(false);
        setSubscriptionActive(true);
        setNotice("Free plan activated! You received 100 credits.");
      } catch {
        setError("Unable to activate free plan. You may already have a subscription.");
      } finally {
        setLoadingPlan(null);
      }
      return;
    }

    if (!isLoggedIn) {
      navigate(`/login?next=/pricing`);
      return;
    }

    if (currentPlan === planId && subscriptionActive) return;

    setLoadingPlan(planId);
    try {
      if (hasPaidSubscription && (planId === "basic" || planId === "pro")) {
        const result = await changePlan(planId);
        setCancelScheduled(false);
        setNotice(result.message);
        loadUserBilling();
        window.setTimeout(loadUserBilling, 2500);
        setLoadingPlan(null);
        return;
      }

      const session = await createCheckoutSession(planId as "basic" | "pro");
      window.location.href = session.url;
    } catch {
      setError(
        hasPaidSubscription
          ? "Unable to change plan. Please try again."
          : "Unable to start checkout. Please try again."
      );
      setLoadingPlan(null);
    }
  };

  const openCancelConfirmModal = () => {
    setCancelModal({
      open: true,
      mode: "confirm",
      title: "Cancel subscription?",
      message:
        "Your plan will remain active until the end of the current billing period. After that, you will lose access to paid plan benefits.",
    });
  };

  const closeCancelModal = () => {
    if (cancelingSubscription) return;
    setCancelModal((prev) => ({ ...prev, open: false }));
  };

  const handleConfirmCancelSubscription = async () => {
    setCancelingSubscription(true);
    try {
      const response = await cancelSubcription();
      setCancelScheduled(true);
      setCancelModal({
        open: true,
        mode: "success",
        title: "Cancellation scheduled",
        message: response.message,
      });
    } catch {
      setCancelModal({
        open: true,
        mode: "error",
        title: "Unable to cancel",
        message: "We couldn't cancel your subscription. Please try again or contact support.",
      });
    } finally {
      setCancelingSubscription(false);
    }
  };

  const getPlanButtonLabel = (plan: Plan) => {
    const isCurrent = currentPlan === plan.id && subscriptionActive === true;

    if (loadingPlan === plan.id) {
      return plan.id === "free" ? "Activating…" : hasPaidSubscription ? "Updating…" : "Redirecting…";
    }
    if (isCurrent) return "Current Plan";

    if (plan.id === "free") {
      if (!isLoggedIn) return "Get Started Free";
      if (!canUseFree) return "Not Available";
      return "Activate Free Plan";
    }

    if (hasPaidSubscription) {
      const currentTier = currentPlan === "pro" ? 2 : currentPlan === "basic" ? 1 : 0;
      const targetTier = plan.id === "pro" ? 2 : 1;
      return targetTier > currentTier ? `Upgrade to ${plan.name}` : `Downgrade to ${plan.name}`;
    }

    return `Subscribe to ${plan.name}`;
  };

  const isPlanDisabled = (plan: Plan) => {
    const isCurrent = currentPlan === plan.id && subscriptionActive === true;
    //if (plan.credits > 50) return true;
    if (loadingPlan === plan.id) return true;
    if (isCurrent) return true;
    if (plan.id === "free" && isLoggedIn && !canUseFree) return true;
    return false;
  };

  const isCancelButtonDisabled =
    !hasPaidSubscription || cancelScheduled || cancelingSubscription;

  const orderedPlans = plans.length
    ? plans
    : [
      { id: "free", name: "Free", price_label: "$0", period: "/ forever", credits: 100 },
      { id: "basic", name: "Basic", price_label: "$9", period: "/ week", credits: 200 },
      { id: "pro", name: "Pro", price_label: "$18", period: "/ month", credits: 400 },
    ];

  return (
    <div className="lp-root pricing-page">
      <nav className="lp-nav">
        <div className="lp-nav-inner">
          <Link to="/" className="lp-nav-brand">
            <img src={logo} alt="Chatpaper" className="lp-nav-logo" />
            <span className="lp-nav-brand-name">Chatpaper</span>
          </Link>
          <div className="lp-nav-actions">
            {isLoggedIn ? (
              <Link to="/dashboard" className="lp-nav-cta">
                Dashboard
              </Link>
            ) : (
              <>
                <Link to="/login" className="lp-nav-signin">
                  Sign in
                </Link>
                <Link to="/login?mode=signup" className="lp-nav-cta">
                  Get Started
                </Link>
              </>
            )}
          </div>
        </div>
      </nav>

      <section className="lp-section lp-pricing-section pricing-hero">
        <div className="lp-section-inner">
          <p className="lp-section-label">PRICING</p>
          <h1 className="lp-section-heading">Choose Your Plan</h1>
          <p className="lp-section-sub">
            Credits are used for file uploads and chat messages. Upgrade anytime.
          </p>

          {isLoggedIn && credits !== null && (
            <p className="pricing-credits-badge">
              Your balance: <strong>{credits.toLocaleString()}</strong> credits
              {currentPlan && subscriptionActive
                ? ` · ${currentPlan.charAt(0).toUpperCase()}${currentPlan.slice(1)} plan`
                : ""}
            </p>
          )}

          {notice && <p className="pricing-notice">{notice}</p>}
          {error && <p className="pricing-error">{error}</p>}

          <div className="lp-pricing pricing-grid">
            {orderedPlans.map((plan) => {
              const features = PLAN_FEATURES[plan.id] ?? [];
              const isFeatured = plan.id === "basic";

              return (
                <div
                  key={plan.id}
                  className={`lp-plan pricing-plan${isFeatured ? " pricing-plan-featured" : ""}`}
                >
                  <div className="lp-plan-badge">{plan.name}</div>
                  <div className="lp-plan-price">
                    <span className="lp-plan-amount">{plan.price_label}</span>
                    <span className="lp-plan-period">{plan.period}</span>
                  </div>
                  <p className="pricing-credits-line">
                    {plan.credits.toLocaleString()} credits
                  </p>
                  <ul className="lp-plan-features">
                    {features.map((feat) => (
                      <li key={feat} className="lp-plan-feature">
                        <span className="lp-plan-check">✓</span>
                        {feat}
                      </li>
                    ))}
                  </ul>

                  <button
                    type="button"
                    className="lp-plan-cta pricing-cta-btn"
                    disabled={isPlanDisabled(plan)}
                    onClick={() => handleSelectPlan(plan.id)}
                  >
                    {getPlanButtonLabel(plan)}
                  </button>
                </div>
              );
            })}
          </div>

          {hasPaidSubscription && (
            <div className="cancel-button">
              <button
                type="button"
                className="cancelSubscriptionButton lp-plan-cta"
                onClick={openCancelConfirmModal}
                disabled={isCancelButtonDisabled}
              >
                {cancelScheduled ? "Cancellation scheduled" : "Cancel subscribed plan"}
              </button>
              {cancelScheduled && (
                <p className="pricing-cancel-note">
                  Your subscription will end at the close of this billing period. Upgrade or
                  downgrade to keep your plan active.
                </p>
              )}
            </div>
          )}

          <CancelSubscriptionModal
            open={cancelModal.open}
            mode={cancelModal.mode}
            title={cancelModal.title}
            message={cancelModal.message}
            loading={cancelingSubscription}
            onClose={closeCancelModal}
            onConfirm={() => void handleConfirmCancelSubscription()}
          />

          <p className="pricing-footnote">
            File uploads cost 50 credits · Each chat message costs 10 credits
          </p>
        </div>
      </section>
    </div>
  );
}
