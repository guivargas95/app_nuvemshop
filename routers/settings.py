from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func, delete
from sqlalchemy.orm import Session

from db import SessionLocal
from models import StoreSettings, StoreNotificationTarget

router = APIRouter(tags=["settings"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------- Helpers ----------

SUPPORTED_WA_EVENTS = {"order/created", "order/paid", "order/fulfilled"}
DEFAULT_WA_EVENTS = ["order/paid"]


def normalize_whatsapp_phone(raw: str) -> str:
    """
    Normaliza e valida telefone no formato E.164:
    Ex: +5511999999999

    - Remove espaços, parênteses, hífens, etc.
    - Exige que comece com '+'
    - Valida comprimento (8 a 15 dígitos após '+')
    """
    s = raw.strip()
    s = re.sub(r"[^\d+]", "", s)

    if not s.startswith("+"):
        raise ValueError("Telefone deve estar no formato E.164, ex: +5511999999999")

    if not re.fullmatch(r"\+\d{8,15}", s):
        raise ValueError("Telefone inválido. Use E.164, ex: +5511999999999")

    return s


def coerce_events(value: Any) -> list[str]:
    """
    Garante que o campo de eventos seja uma lista válida.
    """
    if value is None:
        return DEFAULT_WA_EVENTS.copy()

    if not isinstance(value, list):
        raise ValueError('whatsapp_events_enabled deve ser uma lista, ex: ["order/paid"]')

    events: list[str] = []
    for e in value:
        if not isinstance(e, str):
            raise ValueError("Todos os eventos devem ser strings.")
        events.append(e)

    invalid = [e for e in events if e not in SUPPORTED_WA_EVENTS]
    if invalid:
        raise ValueError(f"Eventos inválidos: {invalid}. Permitidos: {sorted(SUPPORTED_WA_EVENTS)}")

    return events


def get_or_create_store_settings(db: Session, store_id: str) -> StoreSettings:
    row = db.execute(select(StoreSettings).where(StoreSettings.store_id == store_id)).scalars().first()
    if row:
        # compat: se existir mas estiver vazio/nulo, força default
        try:
            if not getattr(row, "whatsapp_events_enabled", None):
                row.whatsapp_events_enabled = DEFAULT_WA_EVENTS.copy()
                db.commit()
                db.refresh(row)
        except Exception:
            # Se por algum motivo a coluna ainda não existir no schema,
            # não vamos quebrar o GET.
            pass

        return row

    # cria usando defaults do banco (server_default) e defaults do app quando necessário
    row = StoreSettings(store_id=store_id)
    # se seu model já tiver server_default ['order/paid'], isso aqui é redundante,
    # mas mantém consistência mesmo em ambientes sem migration/ddl perfeito.
    try:
        row.whatsapp_events_enabled = DEFAULT_WA_EVENTS.copy()
    except Exception:
        pass

    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ---------- Store Settings (global) ----------

class StoreSettingsOut(BaseModel):
    store_id: str
    plan: str
    max_targets: int
    monthly_message_limit: int
    monthly_message_used: int
    usage_month: date

    whatsapp_phone: str | None = None
    whatsapp_events_enabled: list[str] = Field(default_factory=lambda: DEFAULT_WA_EVENTS.copy())


class StoreSettingsPatch(BaseModel):
    plan: str | None = None
    max_targets: int | None = None
    monthly_message_limit: int | None = None

    # ✅ NOVOS CAMPOS
    whatsapp_phone: str | None = Field(
        default=None,
        description="Telefone do WhatsApp do seller em E.164. Ex: +5511999999999. Use string vazia para limpar.",
    )
    whatsapp_events_enabled: list[str] | None = Field(
        default=None,
        description='Eventos habilitados. Ex: ["order/paid","order/fulfilled"].',
    )


@router.get("/stores/{store_id}/settings", response_model=StoreSettingsOut)
def get_store_settings(store_id: str, db: Session = Depends(get_db)):
    row = get_or_create_store_settings(db, store_id)

    # compat segura caso a coluna ainda não exista (ou esteja nula)
    events = getattr(row, "whatsapp_events_enabled", None) or DEFAULT_WA_EVENTS.copy()
    phone = getattr(row, "whatsapp_phone", None)

    return StoreSettingsOut(
        store_id=row.store_id,
        plan=row.plan,
        max_targets=row.max_targets,
        monthly_message_limit=row.monthly_message_limit,
        monthly_message_used=row.monthly_message_used,
        usage_month=row.usage_month,
        whatsapp_phone=phone,
        whatsapp_events_enabled=events,
    )


@router.patch("/stores/{store_id}/settings", response_model=StoreSettingsOut)
def patch_store_settings(store_id: str, body: StoreSettingsPatch, db: Session = Depends(get_db)):
    row = get_or_create_store_settings(db, store_id)

    if body.plan is not None:
        row.plan = body.plan

    if body.max_targets is not None:
        if body.max_targets < 1:
            raise HTTPException(400, "max_targets must be >= 1")
        row.max_targets = body.max_targets

    if body.monthly_message_limit is not None:
        if body.monthly_message_limit < 0:
            raise HTTPException(400, "monthly_message_limit must be >= 0")
        row.monthly_message_limit = body.monthly_message_limit

    # ----- WhatsApp settings -----
    if body.whatsapp_phone is not None:
        if body.whatsapp_phone == "":
            # permitir limpar
            row.whatsapp_phone = None
        else:
            try:
                row.whatsapp_phone = normalize_whatsapp_phone(body.whatsapp_phone)
            except ValueError as e:
                raise HTTPException(422, str(e))

    if body.whatsapp_events_enabled is not None:
        try:
            row.whatsapp_events_enabled = coerce_events(body.whatsapp_events_enabled)
        except ValueError as e:
            raise HTTPException(422, str(e))

    db.commit()
    db.refresh(row)

    events = getattr(row, "whatsapp_events_enabled", None) or DEFAULT_WA_EVENTS.copy()
    phone = getattr(row, "whatsapp_phone", None)

    return StoreSettingsOut(
        store_id=row.store_id,
        plan=row.plan,
        max_targets=row.max_targets,
        monthly_message_limit=row.monthly_message_limit,
        monthly_message_used=row.monthly_message_used,
        usage_month=row.usage_month,
        whatsapp_phone=phone,
        whatsapp_events_enabled=events,
    )


@router.delete("/stores/{store_id}/settings")
def delete_store_settings(store_id: str, db: Session = Depends(get_db)):
    """
    Remove a linha de settings da loja.
    No próximo GET /settings, ela será recriada com defaults.
    """
    row = db.execute(select(StoreSettings).where(StoreSettings.store_id == store_id)).scalars().first()
    if not row:
        raise HTTPException(404, "Store settings not found")

    db.execute(delete(StoreSettings).where(StoreSettings.store_id == store_id))
    db.commit()
    return {"ok": True}


# ---------- Notification Targets (numbers) ----------

class TargetIn(BaseModel):
    phone_e164: str
    notify_order_created: bool = True
    notify_order_paid: bool = True
    notify_order_sent: bool = True


class TargetUpdate(BaseModel):
    phone_e164: str | None = None
    notify_order_created: bool | None = None
    notify_order_paid: bool | None = None
    notify_order_sent: bool | None = None


@router.get("/stores/{store_id}/targets")
def list_targets(store_id: str, db: Session = Depends(get_db)):
    rows = db.execute(
        select(StoreNotificationTarget)
        .where(StoreNotificationTarget.store_id == store_id)
        .where(StoreNotificationTarget.deleted_at.is_(None))
        .order_by(StoreNotificationTarget.created_at.asc())
    ).scalars().all()

    return [
        {
            "id": r.id,
            "store_id": r.store_id,
            "phone_e164": r.phone_e164,
            "notify_order_created": r.notify_order_created,
            "notify_order_paid": r.notify_order_paid,
            "notify_order_sent": r.notify_order_sent,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
        }
        for r in rows
    ]


@router.post("/stores/{store_id}/targets")
def create_target(store_id: str, body: TargetIn, db: Session = Depends(get_db)):
    settings = get_or_create_store_settings(db, store_id)

    active_count = db.execute(
        select(func.count())
        .select_from(StoreNotificationTarget)
        .where(StoreNotificationTarget.store_id == store_id)
        .where(StoreNotificationTarget.deleted_at.is_(None))
    ).scalar_one()

    if active_count >= settings.max_targets:
        raise HTTPException(400, f"Max targets reached ({settings.max_targets}).")

    target = StoreNotificationTarget(
        store_id=store_id,
        phone_e164=body.phone_e164,
        notify_order_created=body.notify_order_created,
        notify_order_paid=body.notify_order_paid,
        notify_order_sent=body.notify_order_sent,
    )
    db.add(target)
    db.commit()
    db.refresh(target)

    return {"ok": True, "id": target.id}


@router.put("/stores/{store_id}/settings", response_model=StoreSettingsOut)
def put_store_settings(store_id: str, body: StoreSettingsPatch, db: Session = Depends(get_db)):
    """
    Compat: mantém o PUT antigo, reaproveitando a mesma lógica do PATCH.
    (Atualiza apenas os campos enviados no body.)
    """
    return patch_store_settings(store_id=store_id, body=body, db=db)


@router.delete("/stores/{store_id}/targets/{target_id}")
def delete_target(store_id: str, target_id: int, db: Session = Depends(get_db)):
    target = db.execute(
        select(StoreNotificationTarget)
        .where(StoreNotificationTarget.id == target_id)
        .where(StoreNotificationTarget.store_id == store_id)
        .where(StoreNotificationTarget.deleted_at.is_(None))
    ).scalars().first()

    if not target:
        raise HTTPException(404, "Target not found")

    target.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}
