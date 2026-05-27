# app/schemas/admin_schema.py
from pydantic import BaseModel, Field
from typing import Any, Optional

class ConfigUpdateRequest(BaseModel):
    """Payload saat Admin mengubah batas diskon atau prompt AI"""
    config_value: Any = Field(..., description="Bisa berupa angka, string, atau JSON object")
    description: Optional[str] = None

class AdminApprovalRequest(BaseModel):
    """Payload saat Admin menekan tombol Approve/Counter di Dashboard"""
    action: str = Field(..., description="Isi dengan: 'APPROVE', 'COUNTER', atau 'REJECT'")
    counter_discount_percent: Optional[float] = Field(None, description="Jika action=COUNTER, masukkan angka diskon baru")
    admin_notes: Optional[str] = Field(None, description="Pesan admin yang akan diteruskan AI ke user")

class ROIAnalyticsResponse(BaseModel):
    """Data metrik performa AI untuk Juri / Admin"""
    total_projects_handled: int
    ai_win_rate_percent: float
    total_margin_saved_rupiah: float
    fraud_attempts_prevented: int

class DealConversionResponse(BaseModel):
    """Skema balasan untuk persentase konversi negosiasi."""
    conversion_rate_percent: float = Field(..., description="Persentase deal konversi (0.0 - 100.0)")

class AverageMarginResponse(BaseModel):
    """Skema balasan untuk rata-rata persentase diskon margin."""
    average_discount_percent: float = Field(..., description="Rata-rata persentase diskon yang disetujui")