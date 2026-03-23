from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from models import OrderPaidItem, ProductSalesBucket
from services.orders import parse_api_datetime

BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")


def hour_bucket_start(dt: datetime) -> datetime:
    dt = dt.astimezone(BRAZIL_TZ)
    return dt.replace(minute=0, second=0, microsecond=0)


def day_bucket_start(dt: datetime) -> datetime:
    dt = dt.astimezone(BRAZIL_TZ)
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def extract_paid_items_from_order(order_payload: dict[str, Any]) -> list[dict[str, Any]]:
    order_id = str(order_payload.get("id") or "")
    store_id = str(order_payload.get("store_id") or "")
    payment_status = str(order_payload.get("payment_status") or "").lower()
    paid_at_raw = order_payload.get("paid_at")

    if payment_status != "paid" or not paid_at_raw:
        return []

    paid_at = parse_api_datetime(paid_at_raw)

    items: list[dict[str, Any]] = []
    for product in order_payload.get("products") or []:
        product_id = product.get("product_id")
        if product_id is None:
            continue

        try:
            quantity = int(product.get("quantity") or 0)
        except (TypeError, ValueError):
            quantity = 0

        if quantity <= 0:
            continue

        variant_id = product.get("variant_id")
        items.append(
            {
                "store_id": store_id,
                "order_id": order_id,
                "product_id": str(product_id),
                "variant_id": str(variant_id) if variant_id is not None else None,
                "quantity": quantity,
                "paid_at": paid_at,
            }
        )

    return items


def rebuild_product_buckets_for_store(db: Session, store_id: str) -> None:
    db.flush()

    db.execute(
        delete(ProductSalesBucket).where(ProductSalesBucket.store_id == store_id)
    )

    items = db.execute(
        select(OrderPaidItem).where(OrderPaidItem.store_id == store_id)
    ).scalars().all()

    grouped: dict[tuple[str, str, str, datetime], int] = defaultdict(int)
    for item in items:
        grouped[(store_id, item.product_id, "hour", hour_bucket_start(item.paid_at))] += int(item.quantity or 0)
        grouped[(store_id, item.product_id, "day", day_bucket_start(item.paid_at))] += int(item.quantity or 0)

    for (bucket_store_id, product_id, granularity, bucket_start), sales_count in grouped.items():
        db.add(
            ProductSalesBucket(
                store_id=bucket_store_id,
                product_id=product_id,
                granularity=granularity,
                bucket_start=bucket_start,
                sales_count=sales_count,
            )
        )

    db.flush()


def replace_order_paid_items(
    db: Session,
    store_id: str,
    order_id: str,
    items: list[dict[str, Any]],
    source: str,
) -> int:
    db.execute(
        delete(OrderPaidItem)
        .where(OrderPaidItem.store_id == store_id)
        .where(OrderPaidItem.order_id == order_id)
    )

    inserted = 0
    for item in items:
        db.add(
            OrderPaidItem(
                store_id=store_id,
                order_id=order_id,
                product_id=item["product_id"],
                variant_id=item["variant_id"],
                quantity=item["quantity"],
                paid_at=item["paid_at"],
                source=source,
            )
        )
        inserted += 1

    return inserted


def get_product_sales_count_for_period(
    db: Session,
    store_id: str,
    product_id: str,
    period: str,
    count_mode: str = "product",
    variant_id: str | None = None,
) -> int:
    now = datetime.now(BRAZIL_TZ)

    if count_mode == "variant":
        if not variant_id:
            return 0

        starts_at = _period_starts_at(now, period)
        items = db.execute(
            select(OrderPaidItem)
            .where(OrderPaidItem.store_id == store_id)
            .where(OrderPaidItem.product_id == product_id)
            .where(OrderPaidItem.variant_id == variant_id)
            .where(OrderPaidItem.paid_at >= starts_at)
        ).scalars().all()
        return sum(int(item.quantity or 0) for item in items)

    granularity, starts_at = _bucket_query_window(now, period)
    buckets = db.execute(
        select(ProductSalesBucket)
        .where(ProductSalesBucket.store_id == store_id)
        .where(ProductSalesBucket.product_id == product_id)
        .where(ProductSalesBucket.granularity == granularity)
        .where(ProductSalesBucket.bucket_start >= starts_at)
        .where(ProductSalesBucket.bucket_start <= now)
    ).scalars().all()

    return sum(int(bucket.sales_count or 0) for bucket in buckets)


def _period_starts_at(now: datetime, period: str) -> datetime:
    if period == "24h":
        return now - timedelta(hours=24)
    if period == "7d":
        return now - timedelta(days=7)
    if period == "30d":
        return now - timedelta(days=30)
    raise ValueError(f"Unsupported period: {period}")


def _bucket_query_window(now: datetime, period: str) -> tuple[str, datetime]:
    if period == "24h":
        return "hour", hour_bucket_start(now - timedelta(hours=23))
    if period == "7d":
        return "day", day_bucket_start(now - timedelta(days=6))
    if period == "30d":
        return "day", day_bucket_start(now - timedelta(days=29))
    raise ValueError(f"Unsupported period: {period}")


def render_sales_message(template: str, count: int, period: str) -> str:
    safe_template = template or "{count} vendas nos últimos {period}"
    return safe_template.replace("{count}", str(count)).replace("{period}", period)