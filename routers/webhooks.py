from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from models import WebhookLog, StoreInstallation, OrderSnapshot
from db import SessionLocal
from services.orders import fetch_order_snapshot

router = APIRouter(tags=["webhooks"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/webhooks/orders")
async def orders_webhook(payload: dict, db: Session = Depends(get_db)):
    store_id = str(payload.get("store_id"))
    event = payload.get("event")
    order_id = str(payload.get("id"))

    if not store_id or not event or not order_id:
        return {"ok": False}

    IDEMPOTENT_EVENTS = {"order/created", "order/paid"}

    # 1️⃣ Webhook log
    if event in IDEMPOTENT_EVENTS:
        try:
            db.add(
                WebhookLog(
                    store_id=store_id,
                    event=event,
                    resource_id=order_id,
                )
            )
            db.commit()
        except IntegrityError:
            db.rollback()
            return {"ok": True}
    else:
        # order/fulfilled → sempre registra
        db.add(
            WebhookLog(
                store_id=store_id,
                event=event,
                resource_id=order_id,
            )
        )
        db.commit()

    # 2️⃣ Buscar token ativo
    installation = (
        db.query(StoreInstallation)
        .filter(
            StoreInstallation.store_id == store_id,
            StoreInstallation.deleted_at.is_(None),
        )
        .order_by(StoreInstallation.created_at.desc())
        .first()
    )

    if not installation:
        return {"ok": True}

    # 3️⃣ GET pedido (com aggregates)
    order_payload = await fetch_order_snapshot(
        store_id=store_id,
        order_id=order_id,
        access_token=installation.access_token,
    )

    # 4️⃣ Criar snapshot (sempre)
    db.add(
        OrderSnapshot(
            store_id=store_id,
            order_id=order_id,
            event=event,
            payload=order_payload,
        )
    )
    db.commit()

    return {"ok": True}

