
import asyncio
import logging
from typing import Dict, Tuple

logger = logging.getLogger("inventory_store")

class InventoryStore:
    def __init__(self):
        self._inventory: Dict[str, int] = {
            "burger": 50,
            "pizza": 50,
            "sushi": 50
        }

    def get_stock(self, item_id: str) -> int:
        return self._inventory.get(item_id, 0)

    def reserve(self, item_id: str, quantity: int) -> Tuple[bool, int, int]:
        """
        Returns (success, remaining, available_before_reservation)
        """
        current_stock = self._inventory.get(item_id, 0)
        if current_stock >= quantity:
            self._inventory[item_id] = current_stock - quantity
            return True, self._inventory[item_id], current_stock
        else:
            return False, current_stock, current_stock

store = InventoryStore()
