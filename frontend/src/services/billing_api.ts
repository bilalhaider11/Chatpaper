import { api } from "../api/axios";

export type Plan = {
  id: string;
  name: string;
  price_label: string;
  period: string;
  credits: number;
};

export type CreditsInfo = {
  credits: number;
  plan: string | null;
  subscription_active: boolean | null;
};

export type SubscriptionInfo = {
  plan: string | null;
  status: boolean | null;
  can_use_free: boolean;
};

export type ActivateFreeResponse = {
  plan: string;
  credits: number;
};

export type CheckoutResponse = {
  id: string;
  url: string;
};

export async function fetchPlans() {
  const response = await api.get<{ plans: Plan[] }>("/billing/plans");
  return response.data.plans;
}

export async function fetchCredits() {
  const response = await api.get<CreditsInfo>("/billing/credits");
  return response.data;
}

export async function fetchSubscription() {
  const response = await api.get<SubscriptionInfo>("/billing/subscription");
  return response.data;
}

export async function activateFreePlan() {
  const response = await api.post<ActivateFreeResponse>("/billing/activate-free");
  return response.data;
}

export type ChangePlanResponse = {
  status: string;
  plan: string;
  message: string;
};

export async function createCheckoutSession(plan: "basic" | "pro") {
  const response = await api.post<CheckoutResponse>(
    "/billing/create-checkout-session",
    { plan }
  );
  return response.data;
}

export async function changePlan(plan: "basic" | "pro") {
  const response = await api.post<ChangePlanResponse>(
    "/billing/change-plan",
    { plan }
  );
  return response.data;
}
