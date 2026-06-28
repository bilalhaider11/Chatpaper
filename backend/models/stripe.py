from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func

from core.database import Base


class Subscription(Base):
    __tablename__ = "subscription"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    plan = Column(String(20), nullable=False)
    stripe_customer_id = Column(Text(), nullable=True)
    product_id = Column(Text(), nullable=True)
    subscription_id = Column(Text(), nullable=True)
    stripe_subscription_item_id = Column(Text(), nullable=True)
    stripe_price_id = Column(Text(), nullable=True)
    current_period_start = Column(DateTime(timezone=False), nullable=True)
    current_period_end = Column(DateTime(timezone=False), nullable=True)
    status = Column(Boolean(), nullable=False, server_default="true")


class StripeWebhookEvent(Base):
    __tablename__ = "stripe_webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(255), nullable=False, unique=True)
    processed_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)
