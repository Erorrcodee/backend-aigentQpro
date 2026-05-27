# app/api/v1/router/admin.py
import json
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.users import User
from app.models.product_catalog import Product
from app.api.dependencies import get_current_admin, get_admin_user
from app.schemas.product_schema import ProductCreate, ProductResponse
from app.schemas.common_schema import BaseResponse
from app.schemas.admin_schema import DealConversionResponse, AverageMarginResponse
from app.schemas.maut_schema import MautWeightConfigCreate, MautWeightConfigResponse
from app.services.embedding_service import generate_product_vector
from app.services import admin_service, maut_config_service

router = APIRouter()

@router.post("/products", response_model=BaseResponse[ProductResponse], status_code=status.HTTP_201_CREATED)
async def create_product(
    product_in: ProductCreate,
    db: AsyncSession = Depends(get_db),
    # SATPAM AKTIF: Endpoint ini otomatis akan menolak request jika token JWT bukan milik ADMIN
    current_admin: User = Depends(get_current_admin) 
):
    """(Khusus Admin) Menambahkan produk ke Katalog & Generate Vector AI"""
    
    # 1. Cek apakah SKU sudah ada (Cegah Duplikat)
    stmt = select(Product).where(Product.sku == product_in.sku)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="SKU produk sudah terdaftar!")

    # 2. Meracik "Kalimat Pengetahuan" untuk AI
    # Kita gabungkan spesifikasi JSON yang dinamis menjadi satu kalimat bermakna
    specs_str = json.dumps(product_in.specifications) if product_in.specifications else ""
    tags_str = ", ".join(product_in.tags) if product_in.tags else ""
    
    text_to_embed = (
        f"Nama Produk: {product_in.name}. "
        f"Merek/Brand: {product_in.brand}. "
        f"Kategori: {product_in.category}. "
        f"Deskripsi: {product_in.description}. "
        f"Spesifikasi Lengkap: {specs_str}. "
        f"Kata Kunci: {tags_str}"
    )

    # 3. Panggil API LLM untuk mengubah Kalimat -> Vektor Angka
    try:
        embedding_vector = await generate_product_vector(text_to_embed)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sistem AI gagal memproses vektor produk: {str(e)}")

    # 4. Simpan Produk ke Database Neon Tech (bersama Vektornya)
    new_product = Product(
        sku=product_in.sku,
        name=product_in.name,
        brand=product_in.brand,
        category=product_in.category,
        price=product_in.price,
        stock=product_in.stock,
        unit=product_in.unit,
        description=product_in.description,
        specifications=product_in.specifications,
        tags=product_in.tags,
        embedding=embedding_vector # The Magic Bullet! 🔫
    )
    
    db.add(new_product)
    await db.commit()
    await db.refresh(new_product)

    return BaseResponse(
        status="success",
        message=f"Produk {new_product.name} berhasil ditambahkan dan diindeks oleh AI",
        data=ProductResponse.model_validate(new_product)
    )

@router.get(
    "/analytics/deals",
    response_model=BaseResponse[DealConversionResponse],
    status_code=status.HTTP_200_OK
)
async def get_deals_analytics(
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_admin_user)
) -> BaseResponse[DealConversionResponse]:
    """
    (Khusus Admin) Mengambil tingkat persentase konversi negosiasi deal (ISSUED)
    berbanding dengan total estimasi sesi negosiasi.
    """
    rate = await admin_service.get_deal_conversion_rate(db)
    return BaseResponse(
        status="success",
        message="Data analitik konversi deal berhasil dihitung",
        data=DealConversionResponse(conversion_rate_percent=rate)
    )

@router.get(
    "/analytics/margins",
    response_model=BaseResponse[AverageMarginResponse],
    status_code=status.HTTP_200_OK
)
async def get_margins_analytics(
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_admin_user)
) -> BaseResponse[AverageMarginResponse]:
    """
    (Khusus Admin) Mengambil rata-rata persentase diskon margin yang disepakati
    pada seluruh invoice sukses.
    """
    avg_discount = await admin_service.get_average_margin_discount(db)
    return BaseResponse(
        status="success",
        message="Data analitik rata-rata diskon margin berhasil dihitung",
        data=AverageMarginResponse(average_discount_percent=avg_discount)
    )

@router.get(
    "/maut-weights",
    response_model=BaseResponse[MautWeightConfigResponse],
    status_code=status.HTTP_200_OK
)
async def get_active_weights(
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_admin_user)
) -> BaseResponse[MautWeightConfigResponse]:
    """
    (Khusus Admin) Mengambil konfigurasi bobot kriteria MAUT yang saat ini sedang aktif.
    """
    active_config = await maut_config_service.get_active_maut_config(db)
    return BaseResponse(
        status="success",
        message="Konfigurasi bobot MAUT aktif berhasil diambil",
        data=MautWeightConfigResponse.model_validate(active_config)
    )

@router.put(
    "/maut-weights",
    response_model=BaseResponse[MautWeightConfigResponse],
    status_code=status.HTTP_200_OK
)
async def update_active_weights(
    config_in: MautWeightConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_admin_user)
) -> BaseResponse[MautWeightConfigResponse]:
    """
    (Khusus Admin) Menyimpan konfigurasi bobot MAUT baru dan menonaktifkan
    konfigurasi lama. Menjamin hanya satu konfigurasi yang aktif.
    """
    updated_config = await maut_config_service.upsert_maut_config(db, config_in)
    return BaseResponse(
        status="success",
        message="Konfigurasi bobot MAUT berhasil diperbarui dan diaktifkan",
        data=MautWeightConfigResponse.model_validate(updated_config)
    )

@router.delete(
    "/maut-weights/{config_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
async def delete_weights_config(
    config_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_admin_user)
) -> None:
    """
    (Khusus Admin) Menghapus konfigurasi bobot MAUT berdasarkan ID.
    Mengembalikan status 204 No Content jika sukses.
    """
    success = await maut_config_service.delete_maut_config(db, config_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Konfigurasi bobot MAUT tidak ditemukan atau gagal dihapus"
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)