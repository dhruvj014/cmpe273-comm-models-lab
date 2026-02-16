
from pydantic import BaseModel
from typing import Optional

class NotificationRequest(BaseModel):
    order_id: str
    user_id: str
    message: str

class NotificationResponse(BaseModel):
    sent: bool
