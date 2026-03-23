from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import SessionLocal
from models import StoreSettings
from routers.settings import ALLOWED_PERIODS, get_or_create_store_settings
from services.sales_counter import get_product_sales_count_for_period, render_sales_message

router = APIRouter(prefix="/public", tags=["public"])



def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class PublicSalesCountOut(BaseModel):
    store_id: str
    product_id: str
    variant_id: str | None = None
    count: int
    period: str
    minimum_sales_to_show: int
    should_show: bool
    message: str | None = None


@router.get("/stores/{store_id}/products/{product_id}/sales-count", response_model=PublicSalesCountOut)
def get_public_product_sales_count(
    store_id: str,
    product_id: str,
    period: str | None = Query(default=None, description="24h, 7d ou 30d"),
    variant_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    settings = get_or_create_store_settings(db, store_id)

    if not settings.is_active:
        raise HTTPException(status_code=404, detail="Store is inactive")

    if not settings.display_enabled:
        return PublicSalesCountOut(
            store_id=store_id,
            product_id=product_id,
            variant_id=variant_id,
            count=0,
            period=period or settings.display_period,
            minimum_sales_to_show=settings.minimum_sales_to_show,
            should_show=False,
            message=None,
        )

    effective_period = period or settings.display_period
    if effective_period not in ALLOWED_PERIODS:
        raise HTTPException(422, f"period inválido. Use um de: {sorted(ALLOWED_PERIODS)}")

    if settings.count_mode == "variant" and not variant_id:
        raise HTTPException(422, "variant_id é obrigatório quando count_mode=variant")

    count = get_product_sales_count_for_period(
        db=db,
        store_id=store_id,
        product_id=product_id,
        period=effective_period,
        count_mode=settings.count_mode,
        variant_id=variant_id,
    )

    should_show = count >= settings.minimum_sales_to_show
    message = None
    if should_show:
        message = render_sales_message(
            template=settings.message_template,
            count=count,
            period=effective_period,
        )

    return PublicSalesCountOut(
        store_id=store_id,
        product_id=product_id,
        variant_id=variant_id,
        count=count,
        period=effective_period,
        minimum_sales_to_show=settings.minimum_sales_to_show,
        should_show=should_show,
        message=message,
    )
