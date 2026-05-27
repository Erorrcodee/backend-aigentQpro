# app/models/maut_weight_config.py
"""
Model SQLAlchemy untuk tabel `maut_weight_configs`.
Menyimpan konfigurasi bobot utilitas multi-attribute utility theory (MAUT) untuk kalkulasi diskon B2B.
"""

from sqlalchemy import Column, Integer, Float, Boolean, DateTime
from sqlalchemy.sql import func
from app.models.base import Base

class MautWeightConfig(Base):
    """
    Representasi skema tabel penyimpanan bobot kriteria MAUT.
    Kombinasi total seluruh bobot kriteria wajib bernilai 1.0.
    """
    __tablename__ = "maut_weight_configs"

    id = Column(Integer, primary_key=True, index=True)

    # Bobot finansial (profit margin)
    profit_margin = Column(Float, nullable=False, default=0.40)

    # Bobot volume pembelian (volume tier)
    volume_tier = Column(Float, nullable=False, default=0.20)

    # Bobot metode termin pembayaran (payment term)
    payment_term = Column(Float, nullable=False, default=0.15)

    # Bobot riwayat belanja dan loyalitas (loyalty history)
    loyalty_history = Column(Float, nullable=False, default=0.15)

    # Bobot kepentingan strategis dari AI (ai strategic value)
    ai_strategic_value = Column(Float, nullable=False, default=0.10)

    # Status aktif konfigurasi (hanya boleh ada satu konfigurasi aktif dalam satu waktu)
    is_active = Column(Boolean, nullable=False, default=True)

    # Waktu pembuatan konfigurasi
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Waktu pembaruan konfigurasi
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<MautWeightConfig(id={self.id}, "
            f"profit={self.profit_margin}, volume={self.volume_tier}, "
            f"payment={self.payment_term}, loyalty={self.loyalty_history}, "
            f"ai_strategic={self.ai_strategic_value}, active={self.is_active})>"
        )
