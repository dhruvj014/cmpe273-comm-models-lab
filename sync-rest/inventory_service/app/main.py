
import asyncio
import logging
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from app.models import InventoryReserveRequest, InventoryResponse, ErrorResponse, ErrorDetail
from app.store import store
from app.config import INVENTORY_DELAY_MS, INVENTORY_FAIL_MODE
from common import ids

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("inventory_service")

app = FastAPI()

@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-Id")
    if not correlation_id:
        correlation_id = ids.generate_correlation_id()
    
    # Store in request state
    request.state.correlation_id = correlation_id
    
    response = await call_next(request)
    response.headers["X-Correlation-Id"] = correlation_id
    return response

@app.get("/health")
def health():
    return {"status": "ok", "service": "inventory"}

@app.get("/inventory/{item_id}")
def get_inventory(item_id: str):
    """Debug endpoint to check inventory"""
    return {"item_id": item_id, "count": store.get_stock(item_id)}

@app.post("/reserve", response_model=InventoryResponse)
async def reserve(request: Request, reserve_req: InventoryReserveRequest):
    correlation_id = request.state.correlation_id
    logger.info(f"Reserve request for {reserve_req.item_id} x {reserve_req.quantity}, order {reserve_req.order_id}, correlation {correlation_id}")

    # Failure Mode Check
    if INVENTORY_FAIL_MODE:
        logger.error(f"Forced failure active. Failing request for order {reserve_req.order_id}")
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="INVENTORY_FAILURE",
                    message="Forced failure mode enabled",
                    order_id=reserve_req.order_id,
                    correlation_id=correlation_id
                )
            ).dict()
        )

    # Artificial Delay
    if INVENTORY_DELAY_MS > 0:
        delay_sec = INVENTORY_DELAY_MS / 1000.0
        logger.info(f"Injecting delay of {INVENTORY_DELAY_MS}ms")
        await asyncio.sleep(delay_sec)

    # Process Reservation
    success, remaining, available = store.reserve(reserve_req.item_id, reserve_req.quantity)

    if success:
        logger.info(f"Reserved {reserve_req.item_id}. Remaining: {remaining}")
        return InventoryResponse(reserved=True, remaining=remaining)
    else:
        logger.warning(f"Out of stock for {reserve_req.item_id}. Available: {available}")
        return JSONResponse(
            status_code=409,
            content=InventoryResponse(
                reserved=False, 
                reason="out_of_stock", 
                available=available
            ).dict()
        )
