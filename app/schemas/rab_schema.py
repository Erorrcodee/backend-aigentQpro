# app/schemas/rab_schema.py
from pydantic import BaseModel, Field
from typing import List, Optional

class RABItem(BaseModel):
    item_name: str = Field(..., description="Nama barang dari dokumen")
    quantity: float
    unit: str
    price_per_unit: float
    total_price: float
    is_suspicious: bool = Field(..., description="True jika harga dinilai terlalu mahal/markup dari harga pasar wajar")

class RABExtractionResult(BaseModel):
    project_name: Optional[str] = Field(None, description="Nama proyek jika tertulis di dokumen")
    contractor_name: Optional[str] = Field(None, description="Nama kontraktor jika tertulis di dokumen")
    items: List[RABItem]
    total_budget: float
    fraud_analysis_summary: str = Field(..., description="Analisis AI terkait indikasi markup harga. Kosongkan jika aman.")