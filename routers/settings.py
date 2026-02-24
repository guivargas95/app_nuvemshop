from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from db import SessionLocal
from models import StoreSettings

router = APIRouter(tags=["settings"])


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

    row = StoreSettings(store_id=store_id)  # defaults via server_default
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ---------- Schemas ----------

class StoreSettingsOut(BaseModel):
    store_id: str
    plan: str
    is_active: bool

    display_mode_strategy: str = Field(description="auto | manual")
    display_mode_window: str = Field(description="last_1h | last_24h | last_7d | last_30d")

    minimum_sales_to_display: int

    show_on_product_page: bool
    show_on_cart_page: bool

    position: str = Field(description="below_price | above_buy_button | below_buy_button | custom_selector")
    custom_selector: str | None

    text_template: str
    locale: str


class StoreSettingsPatch(BaseModel):
    plan: str | None = None
    is_active: bool | None = None

    display_mode_strategy: str | None = Field(default=None, description="auto | manual")
    display_mode_window: str | None = Field(default=None, description="last_1h | last_24h | last_7d | last_30d")

    minimum_sales_to_display: int | None = None

    show_on_product_page: bool | None = None
    show_on_cart_page: bool | None = None

    position: str | None = Field(default=None, description="below_price | above_buy_button | below_buy_button | custom_selector")
    custom_selector: str | None = None

    text_template: str | None = None
    locale: str | None = None


# ---------- Endpoints ----------

@router.get("/stores/{store_id}/settings", response_model=StoreSettingsOut)
def get_store_settings(store_id: str, db: Session = Depends(get_db)):
    row = get_or_create_store_settings(db, store_id)

    return StoreSettingsOut(
        store_id=row.store_id,
        plan=row.plan,
        is_active=row.is_active,
        display_mode_strategy=row.display_mode_strategy,
        display_mode_window=row.display_mode_window,
        minimum_sales_to_display=row.minimum_sales_to_display,
        show_on_product_page=row.show_on_product_page,
        show_on_cart_page=row.show_on_cart_page,
        position=row.position,
        custom_selector=row.custom_selector,
        text_template=row.text_template,
        locale=row.locale,
    )


@router.patch("/stores/{store_id}/settings", response_model=StoreSettingsOut)
def patch_store_settings(store_id: str, body: StoreSettingsPatch, db: Session = Depends(get_db)):
    row = get_or_create_store_settings(db, store_id)

    if body.plan is not None:
        row.plan = body.plan

    if body.is_active is not None:
        row.is_active = body.is_active

    if body.display_mode_strategy is not None:
        if body.display_mode_strategy not in ("auto", "manual"):
            raise HTTPException(422, "display_mode_strategy must be 'auto' or 'manual'")
        row.display_mode_strategy = body.display_mode_strategy

    if body.display_mode_window is not None:
        if body.display_mode_window not in ("last_1h", "last_24h", "last_7d", "last_30d"):
            raise HTTPException(422, "display_mode_window must be one of last_1h|last_24h|last_7d|last_30d")
        row.display_mode_window = body.display_mode_window

    if body.minimum_sales_to_display is not None:
        if body.minimum_sales_to_display < 1:
            raise HTTPException(422, "minimum_sales_to_display must be >= 1")
        row.minimum_sales_to_display = body.minimum_sales_to_display

    if body.show_on_product_page is not None:
        row.show_on_product_page = body.show_on_product_page

    if body.show_on_cart_page is not None:
        row.show_on_cart_page = body.show_on_cart_page

    if body.position is not None:
        if body.position not in ("below_price", "above_buy_button", "below_buy_button", "custom_selector"):
            raise HTTPException(422, "position invalid")
        row.position = body.position

    # custom_selector só faz sentido quando position=custom_selector
    if body.custom_selector is not None:
        if row.position != "custom_selector":
            raise HTTPException(422, "custom_selector can only be set when position='custom_selector'")
        if body.custom_selector.strip() == "":
            row.custom_selector = None
        else:
            row.custom_selector = body.custom_selector.strip()

    if body.text_template is not None:
        if "{count}" not in body.text_template or "{period}" not in body.text_template:
            raise HTTPException(422, "text_template must include {count} and {period}")
        row.text_template = body.text_template

    if body.locale is not None:
        row.locale = body.locale

    db.commit()
    db.refresh(row)

    return StoreSettingsOut(
        store_id=row.store_id,
        plan=row.plan,
        is_active=row.is_active,
        display_mode_strategy=row.display_mode_strategy,
        display_mode_window=row.display_mode_window,
        minimum_sales_to_display=row.minimum_sales_to_display,
        show_on_product_page=row.show_on_product_page,
        show_on_cart_page=row.show_on_cart_page,
        position=row.position,
        custom_selector=row.custom_selector,
        text_template=row.text_template,
        locale=row.locale,
    )


@router.put("/stores/{store_id}/settings", response_model=StoreSettingsOut)
def put_store_settings(store_id: str, body: StoreSettingsPatch, db: Session = Depends(get_db)):
    # Compat: reaproveita PATCH (atualiza apenas campos enviados)
    return patch_store_settings(store_id=store_id, body=body, db=db)


@router.delete("/stores/{store_id}/settings")
def delete_store_settings(store_id: str, db: Session = Depends(get_db)):
    row = db.execute(select(StoreSettings).where(StoreSettings.store_id == store_id)).scalars().first()
    if not row:
        raise HTTPException(404, "Store settings not found")

    db.execute(delete(StoreSettings).where(StoreSettings.store_id == store_id))
    db.commit()
    return {"ok": True}