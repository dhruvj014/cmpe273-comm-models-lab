
import httpx
from app.config import (
    ORDER_INVENTORY_TIMEOUT_MS,
    ORDER_NOTIFICATION_TIMEOUT_MS,
    INVENTORY_SERVICE_URL,
    NOTIFICATION_SERVICE_URL
)

async def reserve_inventory(order_id: str, item_id: str, quantity: int, correlation_id: str):
    url = f"{INVENTORY_SERVICE_URL}/reserve"
    payload = {
        "order_id": order_id,
        "item_id": item_id,
        "quantity": quantity
    }
    headers = {"X-Correlation-Id": correlation_id}
    
    async with httpx.AsyncClient() as client:
        # Convert ms to seconds
        timeout_sec = ORDER_INVENTORY_TIMEOUT_MS / 1000.0
        response = await client.post(url, json=payload, headers=headers, timeout=timeout_sec)
        return response

async def send_notification(order_id: str, user_id: str, quantity: int, item_id: str, correlation_id: str):
    url = f"{NOTIFICATION_SERVICE_URL}/send"
    message = f"Order {order_id} confirmed for {quantity} x {item_id}"
    payload = {
        "order_id": order_id,
        "user_id": user_id,
        "message": message
    }
    headers = {"X-Correlation-Id": correlation_id}
    
    async with httpx.AsyncClient() as client:
        # Convert ms to seconds
        timeout_sec = ORDER_NOTIFICATION_TIMEOUT_MS / 1000.0
        response = await client.post(url, json=payload, headers=headers, timeout=timeout_sec)
        return response
