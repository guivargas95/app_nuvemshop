from __future__ import annotations

from datetime import datetime, timezone, date as date_type

from fastapi import APIRouter, Depends
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db import SessionLocal
from models import (
    WebhookLog,
    StoreInstallation,
    OrderItem,
    ProductSalesBucketHourly,
    ProductSalesBucketDaily,
)
from services.orders import fetch_order_for_buckets  # <-- vamos criar/ajustar esse service

router = APIRouter(tags=["webhooks"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _to_hour_bucket(dt: datetime) -> datetime:
    # dt deve ser timezone-aware
    return dt.replace(minute=0, second=0, microsecond=0)


def _to_day_bucket(dt: datetime) -> date_type:
    # dt deve ser timezone-aware
    return dt.date()


@router.post("/webhooks/orders")
async def orders_webhook(payload: dict, db: Session = Depends(get_db)):
    store_id = str(payload.get("store_id") or "")
    event = payload.get("event")
    order_id = str(payload.get("id") or "")

    if not store_id or not event or not order_id:
        return {"ok": False}

    # Para este produto, só faz sentido processar order/paid.
    # Outros eventos a gente só registra no log.
    should_process = event == "order/paid"

    # 1) Idempotência via WebhookLog (agora com UniqueConstraint store_id+event+resource_id)
    try:
        db.add(WebhookLog(store_id=store_id, event=event, resource_id=order_id, status="pending"))
        db.commit()
    except IntegrityError:
        db.rollback()
        # Já processamos/registramos antes
        return {"ok": True}

    # Se não for order/paid, só loga e encerra
    if not should_process:
        db.execute(
            update(WebhookLog)
            .where(WebhookLog.store_id == store_id, WebhookLog.event == event, WebhookLog.resource_id == order_id)
            .values(status="processed", processed_at=datetime.now(timezone.utc))
        )
        db.commit()
        return {"ok": True}

    # 2) Buscar token ativo
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
        # Não temos como consultar o pedido; ainda assim marcamos como failed pra auditoria
        db.execute(
            update(WebhookLog)
            .where(WebhookLog.store_id == store_id, WebhookLog.event == event, WebhookLog.resource_id == order_id)
            .values(status="failed", error_message="No active installation for store", processed_at=datetime.now(timezone.utc))
        )
        db.commit()
        return {"ok": True}

    try:
        # 3) Buscar apenas o necessário do pedido (paid_at + items)
        # Esperado do service:
        # {
        #   "paid_at": datetime (tz-aware),
        #   "items": [{"product_id": "123", "quantity": 2}, ...]
        # }
        order_data = await fetch_order_for_buckets(
            store_id=store_id,
            order_id=order_id,
            access_token=installation.access_token,
        )

        paid_at: datetime = order_data["paid_at"]
        items: list[dict] = order_data.get("items", [])

        if paid_at.tzinfo is None:
            # garante tz-aware (preferível UTC)
            paid_at = paid_at.replace(tzinfo=timezone.utc)

        hour_bucket = _to_hour_bucket(paid_at)
        day_bucket = _to_day_bucket(paid_at)

        # 4) Persistência enxuta + buckets (UPSERT atômico)
        # Fazemos tudo em transação.
        for it in items:
            product_id = str(it.get("product_id") or "")
            quantity = int(it.get("quantity") or 0)

            if not product_id or quantity <= 0:
                continue

            # 4.1) OrderItem (fonte mínima / idempotente via UniqueConstraint)
            # Inserção simples; se duplicar, ignore.
            try:
                db.add(
                    OrderItem(
                        store_id=store_id,
                        order_id=order_id,
                        product_id=product_id,
                        quantity=quantity,
                        paid_at=paid_at,
                    )
                )
                db.flush()
            except IntegrityError:
                db.rollback()
                # já existe esse item; não incrementa bucket de novo
                # (importantíssimo para não inflar contador)
                continue

            # 4.2) Bucket HOURLY: store_id+product_id+bucket_start
            stmt_hour = pg_insert(ProductSalesBucketHourly).values(
                store_id=store_id,
                product_id=product_id,
                bucket_start=hour_bucket,
                count=quantity,
            )
            stmt_hour = stmt_hour.on_conflict_do_update(
                index_elements=["store_id", "product_id", "bucket_start"],
                set_={"count": ProductSalesBucketHourly.count + quantity, "updated_at": datetime.now(timezone.utc)},
            )
            db.execute(stmt_hour)

            # 4.3) Bucket DAILY: store_id+product_id+bucket_date
            stmt_day = pg_insert(ProductSalesBucketDaily).values(
                store_id=store_id,
                product_id=product_id,
                bucket_date=day_bucket,
                count=quantity,
            )
            stmt_day = stmt_day.on_conflict_do_update(
                index_elements=["store_id", "product_id", "bucket_date"],
                set_={"count": ProductSalesBucketDaily.count + quantity, "updated_at": datetime.now(timezone.utc)},
            )
            db.execute(stmt_day)

        # 5) Atualiza WebhookLog como processed
        db.execute(
            update(WebhookLog)
            .where(WebhookLog.store_id == store_id, WebhookLog.event == event, WebhookLog.resource_id == order_id)
            .values(status="processed", processed_at=datetime.now(timezone.utc), error_message=None)
        )

        db.commit()
        return {"ok": True}

    except Exception as e:
        db.rollback()
        db.execute(
            update(WebhookLog)
            .where(WebhookLog.store_id == store_id, WebhookLog.event == event, WebhookLog.resource_id == order_id)
            .values(status="failed", error_message=str(e)[:500], processed_at=datetime.now(timezone.utc))
        )
        db.commit()
        return {"ok": True}


def _safe_resource_id(payload: dict) -> str:
    return str(
        payload.get("event_launch_ts")
        or payload.get("service_id")
        or payload.get("concept_code")
        or "billing"
    )


@router.post("/webhooks/app/suspended")
async def app_suspended_webhook(payload: dict, db: Session = Depends(get_db)):
    store_id = str(payload.get("store_id") or payload.get("user_id") or "unknown")
    event = "app/suspended"
    resource_id = _safe_resource_id(payload)

    try:
        db.add(WebhookLog(store_id=store_id, event=event, resource_id=resource_id, status="processed",
                          processed_at=datetime.now(timezone.utc)))
        db.commit()
    except IntegrityError:
        db.rollback()

    return {"ok": True}


@router.post("/webhooks/app/resumed")
async def app_resumed_webhook(payload: dict, db: Session = Depends(get_db)):
    store_id = str(payload.get("store_id") or payload.get("user_id") or "unknown")
    event = "app/resumed"
    resource_id = _safe_resource_id(payload)

    try:
        db.add(WebhookLog(store_id=store_id, event=event, resource_id=resource_id, status="processed",
                          processed_at=datetime.now(timezone.utc)))
        db.commit()
    except IntegrityError:
        db.rollback()

    return {"ok": True}


@router.post("/webhooks/subscription/updated")
async def subscription_updated_webhook(payload: dict, db: Session = Depends(get_db)):
    store_id = str(payload.get("store_id") or payload.get("user_id") or "unknown")
    event = "subscription/updated"
    resource_id = _safe_resource_id(payload)

    try:
        db.add(WebhookLog(store_id=store_id, event=event, resource_id=resource_id, status="processed",
                          processed_at=datetime.now(timezone.utc)))
        db.commit()
    except IntegrityError:
        db.rollback()

    return {"ok": True}