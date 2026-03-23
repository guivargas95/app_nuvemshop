import os
import secrets
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import SessionLocal
from models import StoreInstallation, StoreSettings
from services.bootstrap import bootstrap_paid_orders_for_store

router = APIRouter(tags=["oauth"])

APP_ID = os.getenv("APP_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL")
API_BASE = os.getenv("TIENDANUBE_API_BASE", "https://api.tiendanube.com/2025-03")
USER_AGENT = os.getenv("USER_AGENT", "Nuvemshop Social Proof (contato@exemplo.com)")
WEBHOOK_ORDERS_URL = os.getenv("WEBHOOK_ORDERS_URL") or (
    f"{PUBLIC_BASE_URL}/webhooks/orders" if PUBLIC_BASE_URL else "https://icebound-hollowly-rea.ngrok-free.dev/webhooks/orders"
)
WEBHOOK_APP_SUSPENDED_URL = os.getenv("WEBHOOK_APP_SUSPENDED_URL") or (
    f"{PUBLIC_BASE_URL}/webhooks/app/suspended" if PUBLIC_BASE_URL else "https://icebound-hollowly-rea.ngrok-free.dev/webhooks/app/suspended"
)
WEBHOOK_APP_RESUMED_URL = os.getenv("WEBHOOK_APP_RESUMED_URL") or (
    f"{PUBLIC_BASE_URL}/webhooks/app/resumed" if PUBLIC_BASE_URL else "https://icebound-hollowly-rea.ngrok-free.dev/webhooks/app/resumed"
)
WEBHOOK_SUBSCRIPTION_UPDATED_URL = os.getenv("WEBHOOK_SUBSCRIPTION_UPDATED_URL") or (
    f"{PUBLIC_BASE_URL}/webhooks/subscription/updated" if PUBLIC_BASE_URL else "https://icebound-hollowly-rea.ngrok-free.dev/webhooks/subscription/updated"
)

if not APP_ID or not CLIENT_SECRET or not REDIRECT_URI:
    raise RuntimeError("Faltou configurar APP_ID, CLIENT_SECRET e/ou REDIRECT_URI no .env")

AUTH_URL = f"https://www.tiendanube.com/apps/{APP_ID}/authorize"
TOKEN_URL = "https://www.tiendanube.com/apps/authorize/token"
STATE_STORE: set[str] = set()


async def ensure_webhook(store_id: str, access_token: str, event: str, url: str) -> dict:
    headers = {
        "Authentication": f"bearer {access_token}",
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json",
    }
    base = f"{API_BASE}/{store_id}/webhooks"

    async with httpx.AsyncClient(timeout=25) as client:
        r = await client.get(base, headers=headers, params={"url": url})
        if r.status_code != 200:
            return {"status": "check_failed", "http_status": r.status_code, "body": r.text}

        hooks = r.json()
        if not isinstance(hooks, list):
            hooks = []

        match = next((wh for wh in hooks if wh.get("event") == event and wh.get("url") == url), None)
        if match:
            return {"status": "exists", "data": match}

        r2 = await client.post(base, headers=headers, json={"event": event, "url": url})
        if r2.status_code not in (200, 201):
            return {"status": "create_failed", "http_status": r2.status_code, "body": r2.text}

        return {"status": "created", "data": r2.json()}



def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/install")
def install():
    state = secrets.token_urlsafe(24)
    STATE_STORE.add(state)
    return RedirectResponse(f"{AUTH_URL}?state={state}", status_code=302)


@router.get("/oauth/callback")
async def oauth_callback(code: str | None = None, state: str | None = None, db: Session = Depends(get_db)):
    if not code or not state:
        raise HTTPException(400, "Missing code/state. Start via /install.")
    if state not in STATE_STORE:
        raise HTTPException(400, "Invalid state")
    STATE_STORE.remove(state)

    payload = {
        "client_id": str(APP_ID),
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
    }

    async with httpx.AsyncClient(timeout=25) as client:
        resp = await client.post(TOKEN_URL, json=payload, headers={"Content-Type": "application/json"})

    if resp.status_code != 200:
        raise HTTPException(resp.status_code, f"Token exchange failed: {resp.text}")

    data = resp.json()
    access_token = data["access_token"]
    store_id = str(data["user_id"])
    scope = data.get("scope")

    active = db.execute(
        select(StoreInstallation)
        .where(StoreInstallation.store_id == store_id)
        .where(StoreInstallation.deleted_at.is_(None))
        .order_by(StoreInstallation.created_at.desc())
        .limit(1)
    ).scalars().first()

    if active:
        active.deleted_at = datetime.now(timezone.utc)

    db.add(StoreInstallation(store_id=store_id, access_token=access_token, scope=scope))

    settings = db.execute(select(StoreSettings).where(StoreSettings.store_id == store_id)).scalars().first()
    if not settings:
        db.add(StoreSettings(store_id=store_id))

    db.commit()

    wh_order_paid = await ensure_webhook(store_id, access_token, "order/paid", WEBHOOK_ORDERS_URL)
    wh_app_suspended = await ensure_webhook(store_id, access_token, "app/suspended", WEBHOOK_APP_SUSPENDED_URL)
    wh_app_resumed = await ensure_webhook(store_id, access_token, "app/resumed", WEBHOOK_APP_RESUMED_URL)
    wh_subscription_updated = await ensure_webhook(store_id, access_token, "subscription/updated", WEBHOOK_SUBSCRIPTION_UPDATED_URL)

    bootstrap_result = await bootstrap_paid_orders_for_store(
        db=db,
        store_id=store_id,
        access_token=access_token,
        user_agent=USER_AGENT,
        days=30,
    )

    return {
        "ok": True,
        "store_id": store_id,
        "scope": scope,
        "bootstrap": bootstrap_result,
        "webhooks": {
            "order_paid": wh_order_paid,
            "app_suspended": wh_app_suspended,
            "app_resumed": wh_app_resumed,
            "subscription_updated": wh_subscription_updated,
        },
    }
