import logging
from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user
from core.config import settings
from core.database import AsyncSessionLocal
from core.dependencies import get_db
from models.auth import User
from models.stripe import StripeWebhookEvent, Subscription
from services.credits import (
    PLAN_CREDITS,
    PLAN_TIER,
    adjust_credits_for_plan_change,
    apply_plan_credits,
    get_credits,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["billing"])

stripe.api_key = settings.STRIPE_SECRET_KEY

PLAN_CONFIG = {
    "free": {
        "name": "Free",
        "price_label": "$0",
        "period": "/ forever",
        "credits": PLAN_CREDITS["free"],
        "stripe_price_id": None,
    },
    "basic": {
        "name": "Basic",
        "price_label": "$9",
        "period": "/ week",
        "credits": PLAN_CREDITS["basic"],
        "stripe_price_id": settings.BASIC_PRICE_ID,
        "product_id": settings.BASIC_PRODUCT_ID,
    },
    "pro": {
        "name": "Pro",
        "price_label": "$18",
        "period": "/ month",
        "credits": PLAN_CREDITS["pro"],
        "stripe_price_id": settings.PRO_PRICE_ID,
        "product_id": settings.PRO_PRODUCT_ID,
    },
}


class CheckoutRequest(BaseModel):
    plan: str


class ChangePlanRequest(BaseModel):
    plan: str


class CreditsResponse(BaseModel):
    credits: int
    plan: str | None = None
    subscription_active: bool | None = None


class SubscriptionResponse(BaseModel):
    plan: str | None = None
    status: bool | None = None
    can_use_free: bool


class ChangePlanResponse(BaseModel):
    status: str
    plan: str
    message: str

class CancelSubscriptionResponse(BaseModel):
    status: str
    message: str


async def _get_user_subscription(
    db: AsyncSession, user_id: int
) -> Subscription | None:
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def _get_subscription_by_customer(
    db: AsyncSession, customer_id: str
) -> Subscription | None:
    result = await db.execute(
        select(Subscription).where(Subscription.stripe_customer_id == customer_id)
    )
    return result.scalar_one_or_none()


def _frontend_base() -> str:
    return (settings.frontend_url).rstrip("/")


def _plan_from_price_id(price_id: str) -> str | None:
    if price_id == settings.BASIC_PRICE_ID:
        return "basic"
    if price_id == settings.PRO_PRICE_ID:
        return "pro"
    return None


def _stripe_period_datetimes(subscription: dict) -> tuple[datetime | None, datetime | None]:
    start = subscription["current_period_start"]
    end = subscription["current_period_end"]
    period_start = (
        datetime.fromtimestamp(start, tz=timezone.utc).replace(tzinfo=None)
        if start
        else None
    )
    period_end = (
        datetime.fromtimestamp(end, tz=timezone.utc).replace(tzinfo=None)
        if end
        else None
    )
    return period_start, period_end


def _apply_stripe_subscription_fields(row: Subscription, subscription: dict) -> None:

    items = subscription["items"]["data"] or []
    if not items:
        return

    item = items[0]
    price_id = item["price"]["id"]
    plan = _plan_from_price_id(price_id) if price_id else None

    row.subscription_id = subscription["id"] or row.subscription_id
    row.stripe_subscription_item_id = item["id"] or row.stripe_subscription_item_id
    if price_id:
        row.stripe_price_id = price_id
    if plan:
        row.plan = plan
        row.product_id = PLAN_CONFIG[plan]["product_id"]

    period_start, period_end = _stripe_period_datetimes(items[0])
    if period_start:
        row.current_period_start = period_start
    if period_end:
        row.current_period_end = period_end


async def _upsert_subscription(
    db: AsyncSession,
    *,
    user_id: int,
    plan: str,
    stripe_customer_id: str,
    subscription_id: str,
    product_id: str,
    active: bool,
    stripe_subscription: dict | None = None,
) -> Subscription:
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = Subscription(
            user_id=user_id,
            plan=plan,
            stripe_customer_id=stripe_customer_id,
            subscription_id=subscription_id,
            product_id=product_id,
            status=active,
        )
        db.add(row)
    else:
        row.plan = plan
        row.stripe_customer_id = stripe_customer_id
        row.subscription_id = subscription_id
        row.product_id = product_id
        row.status = active

    if stripe_subscription:
        _apply_stripe_subscription_fields(row, stripe_subscription)

    return row


async def _webhook_already_processed(db: AsyncSession, event_id: str) -> bool:
    result = await db.execute(
        select(StripeWebhookEvent.id).where(StripeWebhookEvent.event_id == event_id)
    )
    return result.scalar_one_or_none() is not None


async def _mark_webhook_processed(db: AsyncSession, event_id: str) -> None:
    db.add(StripeWebhookEvent(event_id=event_id))


async def _retrieve_stripe_subscription(subscription_id: str) -> dict:
    return await run_in_threadpool(
        stripe.Subscription.retrieve,
        subscription_id,
        expand=["items.data.price"],
    )


async def _resolve_subscription_item_id(
    sub_row: Subscription,
) -> tuple[str, dict]:
    stripe_sub = await _retrieve_stripe_subscription(sub_row.subscription_id)
    items = stripe_sub["items"]["data"]
    if not items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stripe subscription has no items",
        )
    item_id = sub_row.stripe_subscription_item_id or items[0]["id"]
    return item_id, stripe_sub


@router.get("/billing/plans")
async def list_plans():
    return {
        "plans": [
            {
                "id": plan_id,
                "name": cfg["name"],
                "price_label": cfg["price_label"],
                "period": cfg["period"],
                "credits": cfg["credits"],
            }
            for plan_id, cfg in PLAN_CONFIG.items()
        ]
    }


@router.get("/billing/credits", response_model=CreditsResponse)
async def get_user_credits(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    credits = await get_credits(current_user.id, db)
    sub = await _get_user_subscription(db, current_user.id)
    return CreditsResponse(
        credits=credits,
        plan=sub.plan if sub else None,
        subscription_active=sub.status if sub else None,
    )


@router.get("/billing/subscription", response_model=SubscriptionResponse)
async def get_user_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sub = await _get_user_subscription(db, current_user.id)
    if sub is None:
        return SubscriptionResponse(plan=None, status=None, can_use_free=True)
    return SubscriptionResponse(
        plan=sub.plan,
        status=sub.status,
        can_use_free=False,
    )


@router.post("/billing/activate-free")
async def activate_free_plan(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await _get_user_subscription(db, current_user.id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Free plan is not available. You already have a subscription.",
        )

    db.add(
        Subscription(
            user_id=current_user.id,
            plan="free",
            stripe_customer_id=None,
            subscription_id=None,
            product_id=None,
            status=True,
        )
    )
    credits = await apply_plan_credits(current_user.id, "free", db)
    await db.commit()
    return {"plan": "free", "credits": credits}


@router.post("/billing/create-checkout-session")
async def create_checkout_session(
    body: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = body.plan
    if plan not in ("basic", "pro"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid plan selected",
        )

    existing = await _get_user_subscription(db, current_user.id)
    if existing and existing.status and existing.subscription_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have an active subscription. Use change-plan to update it.",
        )

    customer_id = existing.stripe_customer_id if existing else None
    price_id = PLAN_CONFIG[plan]["stripe_price_id"]
    frontend = _frontend_base()

    try:
        session = await run_in_threadpool(
            stripe.checkout.Session.create,
            mode="subscription",
            customer=customer_id,
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{frontend}/pricing?success=true",
            cancel_url=f"{frontend}/pricing?canceled=true",
            metadata={
                "user_id": str(current_user.id),
                "plan": plan,
            },
        )
        return {"id": session.id, "url": session.url}
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stripe error: {e.user_message or str(e)}",
        )


@router.post("/billing/change-plan", response_model=ChangePlanResponse)
async def change_plan(
    body: ChangePlanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    new_plan = body.plan
    if new_plan not in ("basic", "pro"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid plan selected",
        )

    sub_row = await _get_user_subscription(db, current_user.id)
    if not sub_row or not sub_row.status or not sub_row.subscription_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active paid subscription found",
        )

    old_plan = sub_row.plan
    if old_plan not in ("basic", "pro"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plan changes are only available for paid subscriptions",
        )
    if new_plan == old_plan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are already on this plan",
        )

    item_id, _stripe_sub = await _resolve_subscription_item_id(sub_row)
    new_price_id = PLAN_CONFIG[new_plan]["stripe_price_id"]
    is_upgrade = PLAN_TIER[new_plan] > PLAN_TIER[old_plan]
    proration_behavior = "always_invoice" if is_upgrade else "create_prorations"

    try:
        await run_in_threadpool(
            stripe.Subscription.modify,
            sub_row.subscription_id,
            items=[{"id": item_id, "price": new_price_id}],
            proration_behavior=proration_behavior,
            cancel_at_period_end=False,
        )
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stripe error: {e.user_message or str(e)}",
        )

    action = "upgraded" if is_upgrade else "downgraded"
    return ChangePlanResponse(
        status="pending" if is_upgrade else "scheduled",
        plan=new_plan,
        message=(
            f"Plan {action} to {new_plan}. "
            + (
                "A prorated charge will be applied for the remainder of this billing period."
                if is_upgrade
                else "A prorated credit will be applied on your next invoice."
            )
        ),
    )


@router.post("/billing/cancel-subscription", response_model=CancelSubscriptionResponse)
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sub_row = await _get_user_subscription(db, current_user.id)

    if not sub_row or not sub_row.status or not sub_row.subscription_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active paid subscription found",
        )

    try:
        stripe_subscription = await run_in_threadpool(
            stripe.Subscription.modify,
            sub_row.subscription_id,
            cancel_at_period_end=True,
        )
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stripe error: {e.user_message or str(e)}",
        )

    return CancelSubscriptionResponse(
        status="scheduled",
        message=(
            "Your subscription has been scheduled for cancellation. "
            "You will continue to have access until the end of your current billing period."
        ),
    )
    
@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.WEBHOOK_KEY,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_id = event["id"]
    event_type = event["type"]

    async with AsyncSessionLocal() as db:
        if await _webhook_already_processed(db, event_id):
            return {"received": True}

        if event_type == "checkout.session.completed":
            session = event["data"]["object"]
            customer_id = session["customer"]
            subscription_id = session["subscription"]
            
            user_id = session["metadata"]["user_id"]
            plan = session["metadata"]["plan"]

            if not user_id or plan not in ("basic", "pro"):
                logger.warning("Checkout completed without valid metadata")
                await _mark_webhook_processed(db, event_id)
                await db.commit()
                return {"received": True}
            stripe_sub = None
            if subscription_id:
                stripe_sub = await _retrieve_stripe_subscription(subscription_id)

            await _upsert_subscription(
                db,
                user_id=int(user_id),
                plan=plan,
                stripe_customer_id=customer_id or "",
                subscription_id=subscription_id or "",
                product_id=PLAN_CONFIG[plan]["product_id"],
                active=True,
                stripe_subscription=stripe_sub,
            )
            await apply_plan_credits(int(user_id), plan, db)

        elif event_type == "customer.subscription.updated":
            subscription = event["data"]["object"]
            customer_id = subscription["customer"]
            stripe_status = subscription["status"]
            price_id = subscription["items"]["data"][0]["price"]["id"]
            new_plan = _plan_from_price_id(price_id)

            sub_row = await _get_subscription_by_customer(db, customer_id)
            if sub_row and new_plan:
                old_plan = sub_row.plan
                _apply_stripe_subscription_fields(sub_row, subscription)

                if stripe_status in ("active", "trialing"):
                    sub_row.status = True
                    if old_plan != new_plan and old_plan in PLAN_CREDITS:
                        await adjust_credits_for_plan_change(
                            sub_row.user_id, old_plan, new_plan, db
                        )
                elif stripe_status in ("canceled", "unpaid", "past_due"):
                    sub_row.status = False

        elif event_type == "customer.subscription.deleted":
            subscription = event["data"]["object"]
            customer_id = subscription["customer"]
            sub_row = await _get_subscription_by_customer(db, customer_id)
            if sub_row:
                sub_row.status = False

        elif event_type == "invoice.payment_succeeded":
            invoice = event["data"]["object"]
            billing_reason = invoice["billing_reason"]
            if billing_reason == "subscription_cycle":
                customer_id = invoice["customer"]
                sub_row = await _get_subscription_by_customer(db, customer_id)
                if sub_row and sub_row.status and sub_row.plan in ("basic", "pro"):
                    await apply_plan_credits(sub_row.user_id, sub_row.plan, db)

        await _mark_webhook_processed(db, event_id)
        await db.commit()

    return {"received": True}
