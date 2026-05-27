# app/schemas/maut_schema.py
"""
Skema Pydantic (DTO) untuk Manajemen Konfigurasi Bobot MAUT.
Bertanggung jawab atas validasi payload pembuatan/pembaruan bobot kriteria MAUT.
"""

from pydantic import BaseModel, Field, model_validator
from typing import Optional
from datetime import datetime

class MautWeightConfigCreate(BaseModel):
    """Skema payload untuk membuat atau memperbarui konfigurasi bobot MAUT."""
    profit_margin: float = Field(
        0.40, 
        ge=0.0, 
        le=1.0, 
        description="Bobot utilitas profit margin (0.0 - 1.0)"
    )
    volume_tier: float = Field(
        0.20, 
        ge=0.0, 
        le=1.0, 
        description="Bobot utilitas volume pembelian (0.0 - 1.0)"
    )
    payment_term: float = Field(
        0.15, 
        ge=0.0, 
        le=1.0, 
        description="Bobot utilitas termin pembayaran (0.0 - 1.0)"
    )
    loyalty_history: float = Field(
        0.15, 
        ge=0.0, 
        le=1.0, 
        description="Bobot utilitas loyalitas pelanggan (0.0 - 1.0)"
    )
    ai_strategic_value: float = Field(
        0.10, 
        ge=0.0, 
        le=1.0, 
        description="Bobot utilitas nilai strategis AI (0.0 - 1.0)"
    )

    @model_validator(mode="after")
    def validate_total_weight_is_one(self) -> "MautWeightConfigCreate":
        """
        Validasi matematika: Jumlah total dari kelima bobot kriteria
        wajib tepat bernilai 1.0. Toleransi presisi float 1e-5 diizinkan.
        """
        total = (
            self.profit_margin + 
            self.volume_tier + 
            self.payment_term + 
            self.loyalty_history + 
            self.ai_strategic_value
        )
        if abs(total - 1.0) > 1e-5:
            raise ValueError(
                f"Total seluruh bobot kriteria wajib bernilai 1.0. Total saat ini: {total}"
            )
        return self

class MautWeightConfigResponse(BaseModel):
    """Skema balasan lengkap data konfigurasi bobot MAUT."""
    id: int = Field(..., description="ID unik konfigurasi bobot")
    profit_margin: float
    volume_tier: float
    payment_term: float
    loyalty_history: float
    ai_strategic_value: float
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
