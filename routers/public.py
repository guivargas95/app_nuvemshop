from __future__ import annotations

<<<<<<< HEAD
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import SessionLocal
from models import StoreSettings
from routers.settings import ALLOWED_PERIODS, get_or_create_store_settings
from services.sales_counter import get_product_sales_count_for_period, render_sales_message

router = APIRouter(prefix="/public", tags=["public"])

=======
from datetime import datetime, timedelta, timezone, date as date_type

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from db import SessionLocal
from models import StoreSettings, ProductSalesBucketHourly, ProductSalesBucketDaily

router = APIRouter(tags=["public"])
>>>>>>> 2b0b6827a9596f2791e6bbe9448959c8a4b0d5c2


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


<<<<<<< HEAD
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
=======
def _period_label(window: str) -> str:
    return {
        "last_1h": "1 hora",
        "last_24h": "24 horas",
        "last_7d": "7 dias",
        "last_30d": "30 dias",
    }.get(window, window)


def _render_message(template: str, count: int, period_label: str) -> str:
    # Mensagem pronta pro storefront (sem lógica no JS)
    return (template or "").replace("{count}", str(count)).replace("{period}", period_label)


def _resolve_window(settings: StoreSettings, counts: dict[str, int]) -> str:
    """
    - manual => usa display_mode_window
    - auto => escolhe a menor janela que atinge minimum_sales_to_display
    """
    if settings.display_mode_strategy == "manual":
        return settings.display_mode_window

    min_sales = settings.minimum_sales_to_display or 1
    for w in ("last_1h", "last_24h", "last_7d", "last_30d"):
        if counts.get(w, 0) >= min_sales:
            return w
    return "last_30d"


def _sum_hourly_since(db: Session, store_id: str, product_id: str, since: datetime) -> int:
    return int(
        db.execute(
            select(func.coalesce(func.sum(ProductSalesBucketHourly.count), 0))
            .where(ProductSalesBucketHourly.store_id == store_id)
            .where(ProductSalesBucketHourly.product_id == product_id)
            .where(ProductSalesBucketHourly.bucket_start >= since)
        ).scalar_one()
    )


def _sum_daily_since(db: Session, store_id: str, product_id: str, since_date: date_type) -> int:
    return int(
        db.execute(
            select(func.coalesce(func.sum(ProductSalesBucketDaily.count), 0))
            .where(ProductSalesBucketDaily.store_id == store_id)
            .where(ProductSalesBucketDaily.product_id == product_id)
            .where(ProductSalesBucketDaily.bucket_date >= since_date)
        ).scalar_one()
    )


@router.get("/public/stores/{store_id}/products/{product_id}/sales")
def get_product_sales(store_id: str, product_id: str, db: Session = Depends(get_db)):
    # Settings (cria defaults se não existir)
    settings = db.execute(select(StoreSettings).where(StoreSettings.store_id == store_id)).scalars().first()
    if not settings:
        settings = StoreSettings(store_id=store_id)
        db.add(settings)
        db.commit()
        db.refresh(settings)

    now = datetime.now(timezone.utc)

    # Calcula todas as janelas para suportar modo "auto"
    counts = {
        "last_1h": _sum_hourly_since(db, store_id, product_id, now - timedelta(hours=1)),
        "last_24h": _sum_hourly_since(db, store_id, product_id, now - timedelta(hours=24)),
        # Janela diária (calendar window) para social proof
        "last_7d": _sum_daily_since(db, store_id, product_id, now.date() - timedelta(days=6)),
        "last_30d": _sum_daily_since(db, store_id, product_id, now.date() - timedelta(days=29)),
    }

    window = _resolve_window(settings, counts)
    count = int(counts.get(window, 0))
    period_label = _period_label(window)

    min_sales = settings.minimum_sales_to_display or 1
    should_display = bool(settings.is_active) and bool(settings.show_on_product_page) and (count >= min_sales)

    message = _render_message(settings.text_template, count, period_label) if should_display else None

    return {
        "ok": True,
        "store_id": store_id,
        "product_id": product_id,
        "should_display": should_display,
        "message": message,  # <- ✅ pronto para o script injetar
        "window": window,
        "count": count,
        "period_label": period_label,
        "position": settings.position,
        "custom_selector": settings.custom_selector,
        "locale": settings.locale,
        "generated_at": now.isoformat(),
    }
>>>>>>> 2b0b6827a9596f2791e6bbe9448959c8a4b0d5c2
