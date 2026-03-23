from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models import StoreInstallation, WebhookEventLog, OrderSnapshot
from services.orders import fetch_order_by_id
from services.sales_counter import (
    extract_paid_items_from_order,
    rebuild_product_buckets_for_store,
    replace_order_paid_items,
)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _verify_webhook_signature(raw_body: bytes, signature: str | None) -> bool:
    if not settings.app_secret:
        return True

    if not signature:
        return False

    digest = hmac.new(
        settings.app_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(digest, signature)


def _extract_order_id(payload: dict[str, Any]) -> str | None:
    order_id = payload.get("id") or payload.get("order_id")
    if order_id is None:
        return None
    return str(order_id)


def _extract_store_id(payload: dict[str, Any], request_headers: dict[str, str]) -> str | None:
    candidates = [
        payload.get("store_id"),
        payload.get("store"),
        request_headers.get("x-linkedstoreid"),
        request_headers.get("x-store-id"),
        request_headers.get("x-tiendanube-store-id"),
    ]

    for value in candidates:
        if value is not None and str(value).strip():
            return str(value)

    return None


@router.post("")
async def receive_webhook(
    request: Request,
    x_linkedstoreid: str | None = Header(default=None),
    x_event: str | None = Header(default=None),
    x_signature_sha256: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    raw_body = await request.body()

    if not _verify_webhook_signature(raw_body, x_signature_sha256):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    headers_map = {
        "x-linkedstoreid": x_linkedstoreid,
        "x-event": x_event,
        "x-signature-sha256": x_signature_sha256,
    }

    store_id = _extract_store_id(payload, headers_map)
    order_id = _extract_order_id(payload)
    event = (x_event or payload.get("event") or "").strip()

    db.add(
        WebhookEventLog(
            store_id=store_id or "",
            event=event or "unknown",
            payload=json.dumps(payload, ensure_ascii=False),
            resource_id=order_id,
        )
    )
    db.flush()

    if not store_id:
        db.commit()
        raise HTTPException(status_code=400, detail="Missing store_id")

    if not order_id:
        db.commit()
        raise HTTPException(status_code=400, detail="Missing order_id")

    installation = (
        db.query(StoreInstallation)
        .filter(StoreInstallation.store_id == store_id)
        .first()
    )
    if not installation:
        db.commit()
        raise HTTPException(status_code=404, detail="Store installation not found")

    if event == "order/paid":
        order_payload = await fetch_order_by_id(
            store_id=store_id,
            order_id=order_id,
            access_token=installation.access_token,
        )

        db.add(
            OrderSnapshot(
                store_id=store_id,
                order_id=order_id,
                payload=json.dumps(order_payload, ensure_ascii=False),
            )
        )
        db.flush()

        items = extract_paid_items_from_order(order_payload)

        replace_order_paid_items(
            db=db,
            store_id=store_id,
            order_id=order_id,
            items=items,
            source="webhook",
        )
        db.flush()

        rebuild_product_buckets_for_store(db, store_id)

    db.commit()
    return {"ok": True}