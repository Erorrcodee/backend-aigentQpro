# app/schemas/invoice_schema.py
"""
Skema Pydantic (DTO) untuk fitur Dasbor Riwayat Transaksi (Invoice).
Bertanggung jawab atas validasi dan penataan data saat mengirim respons terkait invoice.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class InvoiceItemResponse(BaseModel):
    """Skema untuk memvalidasi dan memformat data item di dalam invoice."""
    sku: Optional[str] = Field(None, description="Kode unik produk jika ada")
    name: Optional[str] = Field(None, description="Nama produk/barang")
    qty: float = Field(..., description="Jumlah kuantitas barang yang dipesan")
    unit: Optional[str] = Field("pcs", description="Satuan barang (contoh: sak, pcs)")
    price: float = Field(..., description="Harga satuan barang")

class InvoiceResponse(BaseModel):
    """Skema balasan lengkap untuk data Invoice."""
    id: str = Field(..., description="ID unik invoice berbasis UUID")
    invoice_number: str = Field(..., description="Nomor invoice unik untuk kebutuhan akuntansi")
    user_id: int = Field(..., description="ID pengguna pemilik transaksi")
    items: List[Dict[str, Any]] = Field(..., description="Daftar item RAB yang disepakati")
    discount_applied: float = Field(..., description="Persentase diskon final yang disetujui")
    download_url: Optional[str] = Field(None, description="Tautan dokumen PDF di Cloudinary")
    status: str = Field(..., description="Status invoice saat ini (contoh: ISSUED, PAID)")
    created_at: datetime = Field(..., description="Waktu penerbitan invoice")

    class Config:
        from_attributes = True
