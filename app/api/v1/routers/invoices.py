# app/api/v1/routers/invoices.py
"""
Router untuk modul Riwayat Transaksi (Invoice).
Menyediakan endpoint asinkron bagi klien untuk melihat daftar dan rincian invoice mereka sendiri.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.models.users import User
from app.schemas.invoice_schema import InvoiceResponse
from app.schemas.common_schema import BaseResponse
from app.services import invoice_service

router = APIRouter()

@router.get(
    "/me", 
    response_model=BaseResponse[List[InvoiceResponse]], 
    status_code=status.HTTP_200_OK
)
async def get_my_invoices(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> BaseResponse[List[InvoiceResponse]]:
    """
    Mengambil daftar riwayat transaksi (invoice) untuk klien/kontraktor yang sedang login.
    """
    invoices = await invoice_service.get_invoices_by_user(db, user_id=current_user.id)
    invoice_responses = [InvoiceResponse.model_validate(inv) for inv in invoices]
    
    return BaseResponse(
        status="success",
        message="Daftar invoice Anda berhasil diambil",
        data=invoice_responses
    )

@router.get(
    "/{invoice_id}", 
    response_model=BaseResponse[InvoiceResponse], 
    status_code=status.HTTP_200_OK
)
async def get_invoice_by_id(
    invoice_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> BaseResponse[InvoiceResponse]:
    """
    Mengambil detail lengkap satu invoice spesifik berdasarkan ID.
    Dilengkapi pengecekan kepemilikan data untuk menjaga keamanan akses antar klien.
    """
    invoice = await invoice_service.get_invoice_detail(
        db, 
        invoice_id=invoice_id, 
        user_id=current_user.id
    )
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice tidak ditemukan atau Anda tidak memiliki hak akses atas data tersebut"
        )
        
    return BaseResponse(
        status="success",
        message="Detail invoice berhasil ditemukan",
        data=InvoiceResponse.model_validate(invoice)
    )
