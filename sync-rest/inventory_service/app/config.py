
import os

INVENTORY_DELAY_MS = int(os.getenv("INVENTORY_DELAY_MS", "0"))
INVENTORY_FAIL_MODE = os.getenv("INVENTORY_FAIL_MODE", "false").lower() == "true"
