from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
<<<<<<< HEAD
from sqlalchemy import delete, select
=======
from sqlalchemy import select, delete
>>>>>>> 2b0b6827a9596f2791e6bbe9448959c8a4b0d5c2
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


<<<<<<< HEAD

=======
>>>>>>> 2b0b6827a9596f2791e6bbe9448959c8a4b0d5c2
def get_or_create_store_settings(db: Session, store_id: str) -> StoreSettings:
    row = db.execute(select(StoreSettings).where(StoreSettings.store_id == store_id)).scalars().first()
    if row:
        return row

<<<<<<< HEAD
    row = StoreSettings(store_id=store_id)
=======
    row = StoreSettings(store_id=store_id)  # defaults via server_default
>>>>>>> 2b0b6827a9596f2791e6bbe9448959c8a4b0d5c2
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


<<<<<<< HEAD
=======
# ---------- Schemas ----------

>>>>>>> 2b0b6827a9596f2791e6bbe9448959c8a4b0d5c2
class StoreSettingsOut(BaseModel):
    store_id: str
    plan: str
    is_active: bool
<<<<<<< HEAD
    display_enabled: bool
    display_period: str
    minimum_sales_to_show: int
    count_mode: str
    message_template: str
=======

    display_mode_strategy: str = Field(description="auto | manual")
    display_mode_window: str = Field(description="last_1h | last_24h | last_7d | last_30d")

    minimum_sales_to_display: int

    show_on_product_page: bool
    show_on_cart_page: bool

    position: str = Field(description="below_price | above_buy_button | below_buy_button | custom_selector")
    custom_selector: str | None

    text_template: str
    locale: str
>>>>>>> 2b0b6827a9596f2791e6bbe9448959c8a4b0d5c2


class StoreSettingsPatch(BaseModel):
    plan: str | None = None
    is_active: bool | None = None
<<<<<<< HEAD
    display_enabled: bool | None = None
    display_period: str | None = None
    minimum_sales_to_show: int | None = None
    count_mode: str | None = None
    message_template: str | None = Field(default=None, min_length=1)
=======

    display_mode_strategy: str | None = Field(default=None, description="auto | manual")
    display_mode_window: str | None = Field(default=None, description="last_1h | last_24h | last_7d | last_30d")
>>>>>>> 2b0b6827a9596f2791e6bbe9448959c8a4b0d5c2

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
<<<<<<< HEAD
    return StoreSettingsOut.model_validate(row, from_attributes=True)
=======

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
>>>>>>> 2b0b6827a9596f2791e6bbe9448959c8a4b0d5c2


@router.patch("/stores/{store_id}/settings", response_model=StoreSettingsOut)
def patch_store_settings(store_id: str, body: StoreSettingsPatch, db: Session = Depends(get_db)):
    row = get_or_create_store_settings(db, store_id)

    if body.plan is not None:
        row.plan = body.plan
<<<<<<< HEAD
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
=======

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
>>>>>>> 2b0b6827a9596f2791e6bbe9448959c8a4b0d5c2

    db.commit()
    db.refresh(row)
    return StoreSettingsOut.model_validate(row, from_attributes=True)

<<<<<<< HEAD

@router.put("/stores/{store_id}/settings", response_model=StoreSettingsOut)
def put_store_settings(store_id: str, body: StoreSettingsPatch, db: Session = Depends(get_db)):
    return patch_store_settings(store_id=store_id, body=body, db=db)
=======
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
>>>>>>> 2b0b6827a9596f2791e6bbe9448959c8a4b0d5c2


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
<<<<<<< HEAD
    return {"ok": True}
=======
    return {"ok": True}
>>>>>>> 2b0b6827a9596f2791e6bbe9448959c8a4b0d5c2
