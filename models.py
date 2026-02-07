from datetime import datetime, timezone, date
from sqlalchemy import Column, String, Boolean, DateTime, Integer, UniqueConstraint, func, Index, JSON, text
from sqlalchemy.orm import Mapped, mapped_column
from db import Base
from sqlalchemy import  func, Date
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from typing import Optional

class StoreInstallation(Base):
    __tablename__ = "store_installations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    store_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    access_token: Mapped[str] = mapped_column(String, nullable=False)
    scope: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)




class StoreSettings(Base):
    __tablename__ = "store_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 1 linha por loja
    store_id: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)

    # Plano (por enquanto genérico)
    plan: Mapped[str] = mapped_column(String, nullable=False, server_default="dev")

    # Limite de números configuráveis (targets)
    max_targets: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")

    # Limites de mensagens por mês (custo)
    monthly_message_limit: Mapped[int] = mapped_column(Integer, nullable=False, server_default="300")
    monthly_message_used: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    # Mês ao qual o contador "used" se refere (primeiro dia do mês)
    # (Postgres: date_trunc('month', now()) -> timestamp; cast para date)
    usage_month: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        server_default=func.date_trunc("month", func.now()).cast(Date),
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    whatsapp_events_enabled: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[\"order/paid\"]'::jsonb"),
    )
    whatsapp_phone: Mapped[Optional[str]] = mapped_column(String, nullable=True)

class StoreNotificationTarget(Base):
    __tablename__ = "store_notification_targets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    store_id: Mapped[str] = mapped_column(String, index=True, nullable=False)

    # Formato E.164 ex: +5511999999999
    phone_e164: Mapped[str] = mapped_column(String, nullable=False)

    notify_order_created: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    notify_order_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    notify_order_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)\
    

class WebhookLog(Base):
    __tablename__ = "webhook_logs"

    id = Column(Integer, primary_key=True)
    store_id = Column(String, index=True)
    event = Column(String, index=True)
    resource_id = Column(String, index=True)  # order_id
    status = Column(String, default="received")
    received_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("store_id", "event", "resource_id", name="uq_webhook_idempotency"),
    )


class OrderSnapshot(Base):
    __tablename__ = "order_snapshots"

    id = Column(Integer, primary_key=True)

    store_id = Column(String, nullable=False, index=True)
    order_id = Column(String, nullable=False, index=True)
    event = Column(String, nullable=False, index=True)

    payload = Column(JSON, nullable=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_snapshot_store_order_event", "store_id", "order_id", "event"),
    )