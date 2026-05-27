# app/schemas/product_schema.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class ProductCreate(BaseModel):
    """Payload saat Admin menambahkan barang baru"""
    sku: str = Field(..., description="Kode unik produk")
    name: str = Field(..., description="Nama lengkap produk")
    brand: Optional[str] = None
    category: str = Field(..., description="Kategori produk")
    price: float = Field(..., gt=0, description="Harga harus lebih dari 0")
    stock: int = Field(0, ge=0)
    unit: Optional[str] = Field("pcs", description="Satuan barang")
    
    description: Optional[str] = None
    # Menampung spesifikasi dinamis (Contoh: Kuat Tekan, Voltase)
    specifications: Optional[Dict[str, Any]] = Field(default_factory=dict)
    # Menampung tag untuk pencarian manual
    tags: Optional[List[str]] = Field(default_factory=list)

class ProductResponse(ProductCreate):
    """Balasan setelah produk berhasil masuk ke Database"""
    id: int
    is_active: bool

    class Config:
        from_attributes = True