
import pytest
import httpx
import uuid

BASE_URL = "http://localhost:8000"
INVENTORY_URL = "http://localhost:8001"

@pytest.mark.asyncio
async def test_order_happy_path():
    order_payload = {
        "user_id": "u123",
        "item_id": "burger",
        "quantity": 1
    }
    
    # 1. Check initial inventory (optional but good)
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{INVENTORY_URL}/inventory/burger")
        assert r.status_code == 200
        initial_stock = r.json()["count"]

    # 2. Place Order
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{BASE_URL}/order", json=order_payload)
        
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "CONFIRMED"
    assert "order_id" in data
    
    # 3. Verify Inventory Decrement
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{INVENTORY_URL}/inventory/burger")
        assert r.status_code == 200
        new_stock = r.json()["count"]
        
    assert new_stock == initial_stock - 1
