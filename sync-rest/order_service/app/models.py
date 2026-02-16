
from pydantic import BaseModel
from typing import Optional, Dict, Any

class OrderRequest(BaseModel):
    user_id: str
    item_id: str
    quantity: int

class OrderResponse(BaseModel):
    order_id: str
    status: str

class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    order_id: Optional[str] = None
    correlation_id: Optional[str] = None

class ErrorResponse(BaseModel):
    error: ErrorDetail
