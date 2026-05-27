# app/api/v1/routers/products.py
"""
Router untuk modul Manajemen Katalog Produk.
Menyediakan endpoint untuk mengambil daftar produk dengan pagination dan menghapus produk.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.dependencies import get_current_user, get_admin_user
from app.models.users import User
from app.schemas.product_schema import ProductResponse
from app.schemas.common_schema import BaseResponse
from app.services import product_service

router = APIRouter()

@router.get(
    "", 
    response_model=BaseResponse[List[ProductResponse]], 
    status_code=status.HTTP_200_OK
)
async def get_all_products(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> BaseResponse[List[ProductResponse]]:
    """
    Mengambil daftar seluruh produk yang aktif dengan dukungan pagination (skip & limit).
    Hanya dapat diakses oleh pengguna terautentikasi.
    """
    products = await product_service.get_products(db, skip=skip, limit=limit)
    product_responses = [ProductResponse.model_validate(p) for p in products]
    
    return BaseResponse(
        status="success",
        message="Daftar produk berhasil diambil",
        data=product_responses
    )

@router.delete(
    "/{product_id}", 
    status_code=status.HTTP_204_NO_CONTENT
)
async def delete_existing_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_admin_user)
) -> None:
    """
    Menghapus produk dari katalog berdasarkan ID produk.
    Hanya dapat diakses oleh Admin.
    Mengembalikan status 204 No Content jika sukses.
    """
    success = await product_service.delete_product(db, product_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Produk tidak ditemukan atau gagal dihapus"
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
