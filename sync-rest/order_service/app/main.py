
import logging
import httpx
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from app.models import OrderRequest, OrderResponse, ErrorResponse, ErrorDetail
from app.client import reserve_inventory, send_notification
from common import ids

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("order_service")

app = FastAPI()

@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-Id")
    if not correlation_id:
        correlation_id = ids.generate_correlation_id()
    
    # Store in request state for access in endpoints
    request.state.correlation_id = correlation_id
    
    response = await call_next(request)
    response.headers["X-Correlation-Id"] = correlation_id
    return response

@app.get("/health")
def health():
    return {"status": "ok", "service": "order"}

@app.post("/order", response_model=OrderResponse)
async def create_order(request: Request, order_req: OrderRequest):
    correlation_id = request.state.correlation_id
    order_id = ids.generate_order_id()
    
    logger.info(f"Processing order {order_id} for user {order_req.user_id} with correlation_id {correlation_id}")

    # 1. Reserve Inventory
    try:
        inv_response = await reserve_inventory(order_id, order_req.item_id, order_req.quantity, correlation_id)
        
        if inv_response.status_code == 409:
            logger.warning(f"Inventory out of stock for order {order_id}")
            return JSONResponse(
                status_code=409,
                content=ErrorResponse(
                    error=ErrorDetail(
                        code="INVENTORY_OUT_OF_STOCK",
                        message="Item out of stock",
                        details=inv_response.json(),
                        order_id=order_id,
                        correlation_id=correlation_id
                    )
                ).dict()
            )
        
        if inv_response.status_code >= 500:
             logger.error(f"Inventory service error for order {order_id}: {inv_response.status_code}")
             return JSONResponse(
                status_code=502,
                content=ErrorResponse(
                    error=ErrorDetail(
                        code="INVENTORY_ERROR",
                        message="Inventory service returned an error",
                        details={"status": inv_response.status_code},
                        order_id=order_id,
                        correlation_id=correlation_id
                    )
                ).dict()
            )

        inv_response.raise_for_status()

    except httpx.TimeoutException:
        logger.error(f"Inventory service timeout for order {order_id}")
        return JSONResponse(
            status_code=504,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="INVENTORY_TIMEOUT",
                    message="Inventory service timed out",
                    order_id=order_id,
                    correlation_id=correlation_id
                )
            ).dict()
        )
    except httpx.RequestError as e:
        logger.error(f"Inventory service unreachable for order {order_id}: {e}")
        return JSONResponse(
            status_code=503,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="INVENTORY_UNREACHABLE",
                    message="Inventory service unreachable",
                    details={"error": str(e)},
                    order_id=order_id,
                    correlation_id=correlation_id
                )
            ).dict()
        )

    # 2. Send Notification
    try:
        notif_response = await send_notification(order_id, order_req.user_id, order_req.quantity, order_req.item_id, correlation_id)
        notif_response.raise_for_status()
    except Exception as e:
        # Note: In a real system we might want to rollback inventory here or use a queue.
        # For this lab, we just fail.
        logger.error(f"Notification service failure for order {order_id}: {e}")
        return JSONResponse(
            status_code=502,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="NOTIFICATION_FAILURE",
                    message="Failed to send notification",
                    details={"error": str(e)},
                    order_id=order_id,
                    correlation_id=correlation_id
                )
            ).dict()
        )

    logger.info(f"Order {order_id} confirmed")
    return OrderResponse(order_id=order_id, status="CONFIRMED")
