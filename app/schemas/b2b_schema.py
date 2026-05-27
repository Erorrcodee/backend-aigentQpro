# app/schemas/b2b_schema.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class ProjectItemDetail(BaseModel):
    sku: Optional[str] = None
    name: str
    qty: float
    unit_price: float
    subtotal: float

class B2BProjectResponse(BaseModel):
    """Data yang dikirim ke Frontend untuk merender Dashboard Proyek B2B"""
    id: int
    project_name: str
    status: str
    total_budget_initial: float
    total_budget_final: Optional[float] = None
    extracted_items: List[ProjectItemDetail] = []
    created_at: datetime

    class Config:
        from_attributes = True  # Pydantic V2 pengganti orm_mode=True

class ChatMessageRequest(BaseModel):
    """Payload saat user mengirim pesan di kolom chat negosiasi"""
    message: str = Field(..., description="Pesan dari user")
    
class ChatMessageResponse(BaseModel):
    """Balasan dari Agen AI ke Frontend"""
    reply: str
    is_deal_reached: bool = False
    needs_admin_approval: bool = False