<<<<<<< HEAD
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index, Integer, String, UniqueConstraint, func
=======
from __future__ import annotations
from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, Integer, String, UniqueConstraint, func, text
>>>>>>> 2b0b6827a9596f2791e6bbe9448959c8a4b0d5c2
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class StoreInstallation(Base):
    __tablename__ = "store_installations"
    __table_args__ = (
        UniqueConstraint("store_id", name="uq_store_installations_store_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    access_token: Mapped[str] = mapped_column(String, nullable=False)
    scope: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class StoreSettings(Base):
    __tablename__ = "store_settings"
<<<<<<< HEAD

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)

    plan: Mapped[str] = mapped_column(String, nullable=False, server_default="dev")
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default="true")
    display_enabled: Mapped[bool] = mapped_column(nullable=False, server_default="true")
    display_period: Mapped[str] = mapped_column(String, nullable=False, server_default="30d")
    minimum_sales_to_show: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    count_mode: Mapped[str] = mapped_column(String, nullable=False, server_default="product")
    message_template: Mapped[str] = mapped_column(
        String,
        nullable=False,
        server_default="{count} vendas nos últimos {period}",
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
=======
    __table_args__ = (
        UniqueConstraint("store_id", name="uq_store_settings_store_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[str] = mapped_column(String, index=True, nullable=False)

    plan: Mapped[str] = mapped_column(String, nullable=False, server_default="free")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    display_mode_strategy: Mapped[str] = mapped_column(
        String, nullable=False, server_default="auto", doc="auto | manual"
    )

    display_mode_window: Mapped[str] = mapped_column(
        String, nullable=False, server_default="last_24h", doc="last_1h | last_24h | last_7d | last_30d"
    )

    minimum_sales_to_display: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))

    show_on_product_page: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    show_on_cart_page: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    position: Mapped[str] = mapped_column(String, nullable=False, server_default="below_price")
    custom_selector: Mapped[str | None] = mapped_column(String, nullable=True)

    text_template: Mapped[str] = mapped_column(
        String, nullable=False, server_default="🔥 {count} vendas nas últimas {period}"
    )
    locale: Mapped[str] = mapped_column(String, nullable=False, server_default="pt-BR")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
>>>>>>> 2b0b6827a9596f2791e6bbe9448959c8a4b0d5c2
    )


class WebhookLog(Base):
    __tablename__ = "webhook_logs"
<<<<<<< HEAD

    id = Column(Integer, primary_key=True)
    store_id = Column(String, index=True)
    event = Column(String, index=True)
    resource_id = Column(String, index=True)
    status = Column(String, default="received")
    received_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

=======
>>>>>>> 2b0b6827a9596f2791e6bbe9448959c8a4b0d5c2
    __table_args__ = (
        UniqueConstraint("store_id", "event", "resource_id", name="uq_webhook_logs_store_event_resource"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    store_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    event: Mapped[str] = mapped_column(String, index=True, nullable=False)
    resource_id: Mapped[str] = mapped_column(String, index=True, nullable=False)

    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[str] = mapped_column(String, nullable=False, server_default="pending")
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        UniqueConstraint("store_id", "order_id", "product_id", name="uq_order_items_store_order_product"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    store_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    order_id: Mapped[str] = mapped_column(String, index=True, nullable=False)

    product_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))

    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ProductSalesBucketHourly(Base):
    __tablename__ = "product_sales_bucket_hourly"
    __table_args__ = (
        UniqueConstraint("store_id", "product_id", "bucket_start", name="uq_psbh_store_product_bucket_start"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    store_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    product_id: Mapped[str] = mapped_column(String, index=True, nullable=False)

    bucket_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)

    count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


<<<<<<< HEAD
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


class OrderPaidItem(Base):
    __tablename__ = "order_paid_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    order_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    product_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    variant_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False, server_default="webhook")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "store_id",
            "order_id",
            "product_id",
            "variant_id",
            name="uq_order_paid_item",
        ),
        Index("ix_order_paid_items_store_paid_at", "store_id", "paid_at"),
    )


class ProductSalesBucket(Base):
    __tablename__ = "product_sales_buckets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    product_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    granularity: Mapped[str] = mapped_column(String, nullable=False)  # hour|day
    bucket_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    sales_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "store_id",
            "product_id",
            "granularity",
            "bucket_start",
            name="uq_product_sales_bucket",
        ),
        Index("ix_product_sales_bucket_lookup", "store_id", "product_id", "granularity", "bucket_start"),
    )
=======
class ProductSalesBucketDaily(Base):
    __tablename__ = "product_sales_bucket_daily"
    __table_args__ = (
        UniqueConstraint("store_id", "product_id", "bucket_date", name="uq_psbd_store_product_bucket_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    store_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    product_id: Mapped[str] = mapped_column(String, index=True, nullable=False)

    bucket_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)

    count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
>>>>>>> 2b0b6827a9596f2791e6bbe9448959c8a4b0d5c2
