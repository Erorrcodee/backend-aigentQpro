# app/models/invoice.py
"""
Model SQLAlchemy untuk tabel `invoices`.
Setiap baris mewakili satu transaksi negosiasi yang telah dikunci (deal locked).
"""
import uuid
from sqlalchemy import Column, String, Float, DateTime, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.models.base import Base


class Invoice(Base):
    """
    Skema tabel penyimpan catatan transaksi B2B yang telah disepakati.
    Dibuat satu kali per sesi negosiasi yang berhasil mencapai deal.
    """
    __tablename__ = "invoices"

    # Primary key berbasis UUID agar tidak mudah diprediksi (lebih aman dari Integer)
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True
    )

    # Nomor invoice yang dapat dibaca manusia, bersifat unik (contoh: INV-20260526-001)
    invoice_number = Column(String(50), unique=True, nullable=False, index=True)

    # ID Pengguna (User) yang berasosiasi dengan invoice ini
    user_id = Column(Integer, nullable=False, index=True)

    # Daftar item RAB yang disepakati, disimpan sebagai JSONB agar fleksibel dan dapat di-query
    items = Column(JSONB, nullable=False, default=list)

    # Persentase diskon final yang disetujui oleh kedua pihak
    discount_applied = Column(Float, nullable=False, default=0.0)

    # Tautan unduhan dokumen PDF dari Cloudinary (diisi setelah upload berhasil)
    download_url = Column(String(500), nullable=True)

    # Status siklus hidup invoice: ISSUED, PAID, CANCELLED
    status = Column(String(20), nullable=False, default="ISSUED")

    # Waktu pembuatan invoice, diisi otomatis oleh server database
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<Invoice(invoice_number='{self.invoice_number}', status='{self.status}')>"
