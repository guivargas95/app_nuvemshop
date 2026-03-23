from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db import SessionLocal
from models import OrderSnapshot, StoreInstallation, WebhookLog
from routers.oauth import USER_AGENT
from services.orders import fetch_order_snapshot
from services.sales_counter import extract_paid_items_from_order, rebuild_product_buckets_for_store, replace_order_paid_items

router = APIRouter(tags=["webhooks"])



def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/webhooks/orders")
async def orders_webhook(payload: dict, db: Session = Depends(get_db)):
    store_id = str(payload.get("store_id") or "")
    event = payload.get("event")
    order_id = str(payload.get("id") or "")

    if not store_id or not event or not order_id:
        return {"ok": False}

    try:
        db.add(WebhookLog(store_id=store_id, event=event, resource_id=order_id))
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"ok": True, "deduplicated": True}

    installation = (
        db.query(StoreInstallation)
        .filter(StoreInstallation.store_id == store_id, StoreInstallation.deleted_at.is_(None))
        .order_by(StoreInstallation.created_at.desc())
        .first()
    )
    if not installation:
        return {"ok": True}

    order_payload = await fetch_order_snapshot(
        store_id=store_id,
        order_id=order_id,
        access_token=installation.access_token,
        user_agent=USER_AGENT,
    )

    db.add(OrderSnapshot(store_id=store_id, order_id=order_id, event=event, payload=order_payload))

    if event == "order/paid":
        items = extract_paid_items_from_order(order_payload)
        replace_order_paid_items(
            db=db,
            store_id=store_id,
            order_id=order_id,
            items=items,
            source="webhook",
        )
        rebuild_product_buckets_for_store(db, store_id)

    db.commit()
    return {"ok": True}



def _safe_resource_id(payload: dict) -> str:
    return str(payload.get("event_launch_ts") or payload.get("service_id") or payload.get("concept_code") or "billing")


@router.post("/webhooks/app/suspended")
async def app_suspended_webhook(payload: dict, db: Session = Depends(get_db)):
    store_id = str(payload.get("store_id") or payload.get("user_id") or "unknown")
    try:
        db.add(WebhookLog(store_id=store_id, event="app/suspended", resource_id=_safe_resource_id(payload)))
        db.commit()
    except IntegrityError:
        db.rollback()
    return {"ok": True}


@router.post("/webhooks/app/resumed")
async def app_resumed_webhook(payload: dict, db: Session = Depends(get_db)):
    store_id = str(payload.get("store_id") or payload.get("user_id") or "unknown")
    try:
        db.add(WebhookLog(store_id=store_id, event="app/resumed", resource_id=_safe_resource_id(payload)))
        db.commit()
    except IntegrityError:
        db.rollback()
    return {"ok": True}


@router.post("/webhooks/subscription/updated")
async def subscription_updated_webhook(payload: dict, db: Session = Depends(get_db)):
    store_id = str(payload.get("store_id") or payload.get("user_id") or "unknown")
    try:
        db.add(WebhookLog(store_id=store_id, event="subscription/updated", resource_id=_safe_resource_id(payload)))
        db.commit()
    except IntegrityError:
        db.rollback()
    return {"ok": True}
