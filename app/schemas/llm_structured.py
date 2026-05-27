# app/schemas/llm_structured.py
from pydantic import BaseModel, Field
from typing import List, Optional

# --- 1. SKEMA UNTUK VISION AGENT (Gemini Flash) ---
class ExtractedItem(BaseModel):
    sku: Optional[str] = Field(None, description="SKU produk jika tertulis di dokumen")
    name: str = Field(..., description="Nama material atau barang yang terbaca")
    qty: float = Field(..., description="Jumlah kuantitas barang")
    unit: str = Field(..., description="Satuan barang, misal: sak, batang, pcs")
    target_price: Optional[float] = Field(None, description="Harga target/satuan yang diminta kontraktor jika ada")

class VisionExtractionResult(BaseModel):
    """Format mutlak yang harus dikembalikan Gemini saat membaca RAB"""
    project_name: str = Field(..., description="Nama proyek yang terbaca dari dokumen")
    items: List[ExtractedItem] = Field(default_factory=list, description="Daftar material")
    is_fraud_detected: bool = Field(False, description="True jika harga/dokumen terlihat diedit atau manipulatif")
    fraud_reason: Optional[str] = Field(None, description="Penjelasan jika terdeteksi fraud")

# --- 2. SKEMA UNTUK RECOMMENDATION AGENT (Qwen) ---
class RecommendedProduct(BaseModel):
    sku: str
    name: str
    reason: str = Field(..., description="Alasan singkat mengapa barang ini cocok untuk cross-selling")

class CrossSellResult(BaseModel):
    """Format rekomendasi barang pelengkap"""
    recommendations: List[RecommendedProduct]