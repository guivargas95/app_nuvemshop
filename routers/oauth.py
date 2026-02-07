import os
import secrets
from datetime import datetime, timezone
from sqlalchemy import select
from models import StoreSettings
import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from db import SessionLocal
from models import StoreInstallation

router = APIRouter(tags=["oauth"])

load_dotenv()
APP_ID = os.getenv("APP_ID")
API_BASE = "https://api.tiendanube.com/2025-03"
WEBHOOK_ORDERS_URL = "https://icebound-hollowly-rea.ngrok-free.dev/webhooks/orders"
USER_AGENT = f"Nuvemshop Notificacoes ({APP_ID})"
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

async def ensure_webhook(store_id: str, access_token: str, event: str, url: str) -> dict:
    headers = {
        "Authentication": f"bearer {access_token}",
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json",
    }
    base = f"{API_BASE}/{store_id}/webhooks"

    async with httpx.AsyncClient(timeout=25) as client:
        # 1) lista (ou filtra só por url para reduzir)
        r = await client.get(base, headers=headers, params={"url": url})
        if r.status_code != 200:
            return {"status": "check_failed", "http_status": r.status_code, "body": r.text}

        hooks = r.json()
        if not isinstance(hooks, list):
            hooks = []

        # 2) valida do seu lado: precisa bater EVENT + URL
        match = next((wh for wh in hooks if wh.get("event") == event and wh.get("url") == url), None)
        if match:
            return {"status": "exists", "data": match}

        # 3) cria
        r2 = await client.post(base, headers=headers, json={"event": event, "url": url})
        if r2.status_code not in (200, 201):
            return {"status": "create_failed", "http_status": r2.status_code, "body": r2.text}

        return {"status": "created", "data": r2.json()}

if not APP_ID or not CLIENT_SECRET or not REDIRECT_URI:
    raise RuntimeError("Faltou configurar APP_ID, CLIENT_SECRET e/ou REDIRECT_URI no .env")

AUTH_URL = f"https://www.tiendanube.com/apps/{APP_ID}/authorize"
TOKEN_URL = "https://www.tiendanube.com/apps/authorize/token"



# DEV: state em memória (em produção, Redis/DB)
STATE_STORE: set[str] = set()

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
    url = f"{AUTH_URL}?state={state}"
    return RedirectResponse(url, status_code=302)

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

    settings = db.execute(
    select(StoreSettings).where(StoreSettings.store_id == store_id)
).scalars().first()

    if not settings:
        db.add(StoreSettings(store_id=store_id, whatsapp_events_enabled=["order/paid"]))
    else:
    # compat: se existir mas estiver vazio/nulo
        if not settings.whatsapp_events_enabled:
            settings.whatsapp_events_enabled = ["order/paid"]

    # ✅ salva no banco ANTES de mexer com webhooks externos
    db.commit()

    # Cria/garante 3 webhooks (order/created , order/paid e order/fulfilled)
    wh1 = await ensure_webhook(store_id, access_token, "order/created", WEBHOOK_ORDERS_URL)
    wh2 = await ensure_webhook(store_id, access_token, "order/paid", WEBHOOK_ORDERS_URL)
    wh3 = await ensure_webhook(store_id,access_token, "order/fulfilled", WEBHOOK_ORDERS_URL)

    return {
        "ok": True,
        "store_id": store_id,
        "scope": scope,
        "webhooks": {
            "order_created": wh1,
            "order_paid": wh2,
            "order_fulfilled": wh3,
        }
    }
