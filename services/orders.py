import httpx

API_BASE = "https://api.tiendanube.com/2025-03"

async def fetch_order_snapshot(
    store_id: str,
    order_id: str,
    access_token: str,
) -> dict:
    url = f"{API_BASE}/{store_id}/orders/{order_id}"
    params = {"aggregates": "fulfillment_orders"}

    headers = {
        "Authentication": f"bearer {access_token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(url, headers=headers, params=params)
        r.raise_for_status()
        return r.json()