
import logging
from fastapi import FastAPI, Request
from app.models import NotificationRequest, NotificationResponse
from common import ids

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("notification_service")

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
    return {"status": "ok", "service": "notification"}

@app.post("/send", response_model=NotificationResponse)
async def send_notification(request: Request, notif_req: NotificationRequest):
    correlation_id = request.state.correlation_id
    
    # Log the message as required
    logger.info(f"Sending notification for order {notif_req.order_id}, correlation {correlation_id}. Message: {notif_req.message}")
    
    return NotificationResponse(sent=True)
