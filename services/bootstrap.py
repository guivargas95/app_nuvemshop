from __future__ import annotations

from sqlalchemy.orm import Session

from services.orders import fetch_paid_orders_last_days
from services.sales_counter import extract_paid_items_from_order, rebuild_product_buckets_for_store, replace_order_paid_items


async def bootstrap_paid_orders_for_store(
    db: Session,
    store_id: str,
    access_token: str,
    user_agent: str,
    days: int = 30,
) -> dict:
    orders = await fetch_paid_orders_last_days(
        store_id=store_id,
        access_token=access_token,
        user_agent=user_agent,
        days=days,
    )

    total_items = 0
    for order in orders:
        items = extract_paid_items_from_order(order)
        total_items += replace_order_paid_items(
            db=db,
            store_id=store_id,
            order_id=str(order.get("id") or ""),
            items=items,
            source="bootstrap",
        )

    rebuild_product_buckets_for_store(db, store_id)
    db.commit()

    return {
        "orders_found": len(orders),
        "items_processed": total_items,
        "days": days,
    }
