# app/services/product_service.py
"""
Lapisan Layanan (Service Layer) untuk Manajemen Katalog Produk.
Bertanggung jawab untuk berinteraksi dengan database secara asinkron guna mengambil
dan menghapus data produk.
"""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.product_catalog import Product

async def get_products(
    db: AsyncSession, 
    skip: int = 0, 
    limit: int = 100
) -> List[Product]:
    """
    Mengambil daftar seluruh produk yang aktif dari database dengan dukungan pagination.

    Args:
        db: Sesi database asinkron (AsyncSession).
        skip: Jumlah baris data awal yang dilewati (offset).
        limit: Batas maksimal jumlah baris data yang diambil.

    Returns:
        Daftar objek Product yang memenuhi kriteria pencarian.
    """
    stmt = (
        select(Product)
        .where(Product.is_active == True)
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())

async def delete_product(
    db: AsyncSession, 
    product_id: int
) -> bool:
    """
    Menghapus produk dari database berdasarkan ID yang diberikan.

    Args:
        db: Sesi database asinkron (AsyncSession).
        product_id: ID produk yang ingin dihapus.

    Returns:
        Boolean yang menandakan apakah proses penghapusan berhasil.
    """
    stmt = select(Product).where(Product.id == product_id)
    result = await db.execute(stmt)
    product = result.scalar_one_or_none()
    
    if not product:
        return False
        
    await db.delete(product)
    await db.commit()
    return True
