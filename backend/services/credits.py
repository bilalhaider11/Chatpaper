import logging

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.redis_client import get_redis
from models.auth import User
from models.stripe import Subscription
logger = logging.getLogger(__name__)

PLAN_CREDITS: dict[str, int] = {
    "free": 100,
    "basic": 200,
    "pro": 400,
}

PLAN_TIER: dict[str, int] = {
    "free": 0,
    "basic": 1,
    "pro": 2,
}

CREDITS_KEY_PREFIX = "credits:"
CREDITS_DIRTY_SET = "credits:dirty"


class InsufficientCreditsError(HTTPException):
    def __init__(self, required: int, available: int):
        super().__init__(
            status_code=402,
            detail=f"Insufficient credits. Required: {required}, available: {available}",
        )


def _credits_key(user_id: int) -> str:
    return f"{CREDITS_KEY_PREFIX}{user_id}"

async def mark_subcription_end(user_id:int,db):
    await db.execute(
        update(Subscription)
        .where(Subscription.user_id == user_id)
        .values(status=False)
        
    )
    await db.commit()
   
    return

async def _load_credits_from_db(user_id: int, db: AsyncSession) -> int:

    result = await db.execute(select(User.credits).where(User.id == user_id))
    row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    return row[0] if row[0] is not None else 0


async def _ensure_redis_credits(user_id: int, db: AsyncSession) -> int:
    redis = get_redis()
    if redis is None:
        return await _load_credits_from_db(user_id, db)

    key = _credits_key(user_id)
    cached = await redis.get(key)
   
    if cached is not None:
        return int(cached)

    credits = await _load_credits_from_db(user_id, db)
    await redis.set(key, credits)
    return credits


async def get_credits(user_id: int, db: AsyncSession) -> int:
    return await _ensure_redis_credits(user_id, db)


async def set_credits(user_id: int, amount: int, db: AsyncSession) -> int:
    redis = get_redis()
    if redis is not None:
        await redis.set(_credits_key(user_id), amount)
        await redis.sadd(CREDITS_DIRTY_SET, user_id)

    await db.execute(
        update(User).where(User.id == user_id).values(credits=amount)
    )
    await db.commit()
    return amount


async def deduct_credits(user_id: int, amount: int, db: AsyncSession) -> int:
    if amount <= 0:
        return await get_credits(user_id, db)

    redis = get_redis()
    if redis is not None:
        current = await _ensure_redis_credits(user_id, db)
        if current < amount:
            raise InsufficientCreditsError(amount, current)

        new_balance = await redis.decrby(_credits_key(user_id), amount)
        if new_balance < 0:
            await redis.incrby(_credits_key(user_id), amount)
            raise InsufficientCreditsError(amount, current)

        await redis.sadd(CREDITS_DIRTY_SET, user_id)
        return int(new_balance)

    current = await _load_credits_from_db(user_id, db)
    if current < amount:
        raise InsufficientCreditsError(amount, current)

    new_balance = current - amount
    await db.execute(
        update(User).where(User.id == user_id).values(credits=new_balance)
    )
    await db.commit()
    return new_balance


async def apply_plan_credits(user_id: int, plan: str, db: AsyncSession) -> int:
    credits = PLAN_CREDITS.get(plan, PLAN_CREDITS["free"])
    return await set_credits(user_id, credits, db)


async def adjust_credits_for_plan_change(
    user_id: int,
    old_plan: str,
    new_plan: str,
    db: AsyncSession,
) -> int:
    current = await get_credits(user_id, db)
    old_cap = PLAN_CREDITS.get(old_plan, 0)
    new_cap = PLAN_CREDITS.get(new_plan, 0)
    delta = new_cap - old_cap
    new_balance = max(0, current + delta)
    return await set_credits(user_id, new_balance, db)
