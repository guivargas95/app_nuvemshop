from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

API_BASE = "https://api.tiendanube.com/2025-03"


def _parse_dt(value: Any) -> datetime:
    """
    Converte string ISO 8601 (ou datetime) em datetime timezone-aware (UTC).
    Aceita formatos comuns com 'Z' e offsets.
    """
    if value is None:
        raise ValueError("Missing paid_at in order payload")

    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        s = value.strip()
        # Python não parseia 'Z' direto no fromisoformat em algumas versões
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
    else:
        raise ValueError(f"Invalid paid_at type: {type(value)}")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    # Normaliza para UTC
    return dt.astimezone(timezone.utc)


def _extract_items(order_payload: dict) -> list[dict]:
    """
    Extrai itens no formato: [{"product_id": "...", "quantity": N}, ...]
    Faz o melhor esforço com chaves mais comuns.
    """
    items = order_payload.get("products") or order_payload.get("items") or []
    out: list[dict] = []

    if not isinstance(items, list):
        return out

    for it in items:
        if not isinstance(it, dict):
            continue

        # Tiendanube/Nuvemshop costuma trazer product_id (ou product.id em alguns payloads)
        product_id = it.get("product_id")
        if not product_id and isinstance(it.get("product"), dict):
            product_id = it["product"].get("id")

        qty = it.get("quantity", 1)

        try:
            qty_i = int(qty)
        except Exception:
            qty_i = 0

        if product_id is None or qty_i <= 0:
            continue

        out.append({"product_id": str(product_id), "quantity": qty_i})

    return out


async def fetch_order_for_buckets(
    store_id: str,
    order_id: str,
    access_token: str,
    user_agent: str | None = None,
) -> dict:
    """
    Busca pedido e retorna somente dados necessários para buckets:
      {
        "paid_at": datetime (UTC, tz-aware),
        "items": [{"product_id": str, "quantity": int}, ...]
      }
    """
    url = f"{API_BASE}/{store_id}/orders/{order_id}"

    headers = {
        "Authentication": f"bearer {access_token}",
        "Content-Type": "application/json",
    }
    if user_agent:
        headers["User-Agent"] = user_agent

    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        payload = r.json()

    # paid_at (fallback: created_at se paid_at não vier — mas ideal é paid_at)
    paid_at_raw = payload.get("paid_at") or payload.get("paidAt")
    paid_at = _parse_dt(paid_at_raw)

    items = _extract_items(payload)

    return {"paid_at": paid_at, "items": items}