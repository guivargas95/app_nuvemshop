from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from db import SessionLocal
from models import StoreSettings

router = APIRouter(tags=["settings"])

ALLOWED_PERIODS = {"24h", "7d", "30d"}
ALLOWED_COUNT_MODES = {"product", "variant"}



def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



def get_or_create_store_settings(db: Session, store_id: str) -> StoreSettings:
    row = db.execute(select(StoreSettings).where(StoreSettings.store_id == store_id)).scalars().first()
    if row:
        return row

    row = StoreSettings(store_id=store_id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


class StoreSettingsOut(BaseModel):
    store_id: str
    plan: str
    is_active: bool
    display_enabled: bool
    display_period: str
    minimum_sales_to_show: int
    count_mode: str
    message_template: str


class StoreSettingsPatch(BaseModel):
    plan: str | None = None
    is_active: bool | None = None
    display_enabled: bool | None = None
    display_period: str | None = None
    minimum_sales_to_show: int | None = None
    count_mode: str | None = None
    message_template: str | None = Field(default=None, min_length=1)


@router.get("/stores/{store_id}/settings", response_model=StoreSettingsOut)
def get_store_settings(store_id: str, db: Session = Depends(get_db)):
    row = get_or_create_store_settings(db, store_id)
    return StoreSettingsOut.model_validate(row, from_attributes=True)


@router.patch("/stores/{store_id}/settings", response_model=StoreSettingsOut)
def patch_store_settings(store_id: str, body: StoreSettingsPatch, db: Session = Depends(get_db)):
    row = get_or_create_store_settings(db, store_id)

    if body.plan is not None:
        row.plan = body.plan
    if body.is_active is not None:
        row.is_active = body.is_active
    if body.display_enabled is not None:
        row.display_enabled = body.display_enabled
    if body.display_period is not None:
        if body.display_period not in ALLOWED_PERIODS:
            raise HTTPException(422, f"display_period inválido. Use um de: {sorted(ALLOWED_PERIODS)}")
        row.display_period = body.display_period
    if body.minimum_sales_to_show is not None:
        if body.minimum_sales_to_show < 0:
            raise HTTPException(422, "minimum_sales_to_show deve ser >= 0")
        row.minimum_sales_to_show = body.minimum_sales_to_show
    if body.count_mode is not None:
        if body.count_mode not in ALLOWED_COUNT_MODES:
            raise HTTPException(422, f"count_mode inválido. Use um de: {sorted(ALLOWED_COUNT_MODES)}")
        row.count_mode = body.count_mode
    if body.message_template is not None:
        row.message_template = body.message_template

    db.commit()
    db.refresh(row)
    return StoreSettingsOut.model_validate(row, from_attributes=True)


@router.put("/stores/{store_id}/settings", response_model=StoreSettingsOut)
def put_store_settings(store_id: str, body: StoreSettingsPatch, db: Session = Depends(get_db)):
    return patch_store_settings(store_id=store_id, body=body, db=db)


@router.delete("/stores/{store_id}/settings")
def delete_store_settings(store_id: str, db: Session = Depends(get_db)):
    row = db.execute(select(StoreSettings).where(StoreSettings.store_id == store_id)).scalars().first()
    if not row:
        raise HTTPException(404, "Store settings not found")

    db.execute(delete(StoreSettings).where(StoreSettings.store_id == store_id))
    db.commit()
    return {"ok": True}
