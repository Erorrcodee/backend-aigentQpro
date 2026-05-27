# app/models/analytics.py
"""
Model SQLAlchemy untuk tabel `association_rules`.
Menyimpan aturan asosiasi produk dinamis hasil analisis market basket (FP-Growth).
"""

import uuid
from sqlalchemy import Column, String, Float, DateTime
from sqlalchemy.sql import func
from app.models.base import Base

class AssociationRule(Base):
    """
    Representasi skema tabel penyimpanan aturan asosiasi lintas penjualan.
    Digunakan untuk mencocokkan item belanja saat ini (antecedent)
    dengan rekomendasi item tambahan (consequent) berbasis statistik confidence & lift.
    """
    __tablename__ = "association_rules"

    # ID unik berbentuk UUID
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Pemicu/antecedent (nama barang belanjaan dalam huruf kecil)
    antecedent = Column(String(255), nullable=False, index=True)

    # Hasil/consequent (nama barang tambahan yang direkomendasikan dalam huruf kecil)
    consequent = Column(String(255), nullable=False)

    # Tingkat keyakinan/confidence dari aturan asosiasi (0.0 - 1.0)
    confidence = Column(Float, nullable=False)

    # Nilai kekuatan asosiasi/lift (> 1.0 menandakan hubungan positif)
    lift = Column(Float, nullable=False)

    # Waktu pembuatan aturan
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<AssociationRule(id={self.id}, "
            f"antecedent='{self.antecedent}', consequent='{self.consequent}', "
            f"confidence={self.confidence}, lift={self.lift})>"
        )
