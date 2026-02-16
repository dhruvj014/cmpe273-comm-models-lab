
from pydantic import BaseModel
from typing import Optional, Dict, Any

class InventoryReserveRequest(BaseModel):
    order_id: str
    item_id: str
    quantity: int

class InventoryResponse(BaseModel):
    reserved: bool
    remaining: Optional[int] = None
    reason: Optional[str] = None
    available: Optional[int] = None

class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    order_id: Optional[str] = None
    correlation_id: Optional[str] = None

class ErrorResponse(BaseModel):
    error: ErrorDetail
