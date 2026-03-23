from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

API_BASE = "https://api.tiendanube.com/2025-03"


def _headers(access_token: str, user_agent: str) -> dict[str, str]:
    return {
        "Authentication": f"bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": user_agent,
    }



def parse_api_datetime(value: str | dict[str, Any] | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)

    if isinstance(value, dict):
        value = value.get("date")
        if not value:
            return datetime.now(timezone.utc)

    normalized = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S.%f"):
            try:
                dt = datetime.strptime(value, fmt)
                break
            except ValueError:
                dt = None
        if dt is None:
            return datetime.now(timezone.utc)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


async def fetch_order_snapshot(
    store_id: str,
    order_id: str,
    access_token: str,
    user_agent: str,
) -> dict[str, Any]:
    url = f"{API_BASE}/{store_id}/orders/{order_id}"
    params = {"aggregates": "fulfillment_orders"}

    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(url, headers=_headers(access_token, user_agent), params=params)
        r.raise_for_status()
        return r.json()


def _is_last_page_response(response: httpx.Response) -> bool:
    if response.status_code != 404:
        return False

    try:
        payload = response.json()
    except ValueError:
        return False

    if not isinstance(payload, dict):
        return False

    message = str(payload.get("message") or "").strip().lower()
    description = str(payload.get("description") or "")
    return message == "not found" and description.startswith("Last page is ")


async def fetch_paid_orders_last_days(
    store_id: str,
    access_token: str,
    user_agent: str,
    days: int = 30,
    page_size: int = 200,
) -> list[dict[str, Any]]:
    url = f"{API_BASE}/{store_id}/orders"
    created_from_dt = datetime.now(timezone.utc) - timedelta(days=days)
    created_from = created_from_dt.isoformat()
    page = 1
    results: list[dict[str, Any]] = []
    seen_order_ids: set[str] = set()

    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            params = {
                "payment_status": "paid",
                "created_at_min": created_from,
                "per_page": page_size,
                "page": page,
            }
            r = await client.get(url, headers=_headers(access_token, user_agent), params=params)

            if _is_last_page_response(r):
                break

            r.raise_for_status()
            payload = r.json()
            if not isinstance(payload, list) or not payload:
                break

            page_added = 0
            for order in payload:
                order_id = str(order.get("id") or "")
                if not order_id or order_id in seen_order_ids:
                    continue

                created_at_raw = order.get("created_at")
                created_at = parse_api_datetime(created_at_raw)
                if created_at < created_from_dt:
                    continue

                seen_order_ids.add(order_id)
                results.append(order)
                page_added += 1

            if len(payload) < page_size:
                break

            if page_added == 0 and all(str(order.get("id") or "") in seen_order_ids for order in payload):
                break

            page += 1

    return results
