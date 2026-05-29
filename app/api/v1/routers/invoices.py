# app/api/v1/routers/invoices.py
"""
Router untuk modul Riwayat Transaksi (Invoice).
Menyediakan dua kelompok endpoint:
  1. Endpoint berbasis database (GET /me, GET /{invoice_id}) — riwayat transaksi tersimpan.
  2. Endpoint berbasis LangGraph State (POST /generate-invoice) — menarik state live dari
     MemorySaver untuk membuat preview invoice sebelum disimpan ke database.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.models.users import User
from app.schemas.invoice_schema import InvoiceResponse
from app.schemas.common_schema import BaseResponse
from app.services import invoice_service

# Import graf LangGraph yang sudah dikompilasi beserta MemorySaver-nya
from app.agents.graph_builder import app_graph

router = APIRouter()
logger = logging.getLogger(__name__)

# ============================================================
# KONSTANTA
# ============================================================
DEFAULT_PRICE_FALLBACK = 0.0  # Harga satuan default jika tidak ada di state item


# ============================================================
# 1. ENDPOINT RIWAYAT INVOICE (DATABASE)
# ============================================================

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


# ============================================================
# 2. SCHEMA REQUEST — GENERATE INVOICE DARI LANGGRAPH STATE
# ============================================================

class InvoiceRequest(BaseModel):
    conversation_id: str
    company_name: str


# ============================================================
# 3. ENDPOINT GENERATE INVOICE (LANGGRAPH STATE)
# ============================================================

@router.post(
    "/generate-invoice",
    status_code=status.HTTP_200_OK
)
async def generate_invoice_from_state(request: InvoiceRequest):
    """
    Menarik state terakhir dari MemorySaver LangGraph berdasarkan `conversation_id`,
    lalu menghitung kalkulasi invoice (subtotal, diskon, grand total) dan mengembalikan
    JSON terstruktur yang siap dirender oleh frontend sebagai invoice/print preview.

    - `conversation_id` : thread_id LangGraph yang digunakan selama sesi negosiasi.
    - `company_name`    : Nama klien/perusahaan yang akan dicantumkan di invoice.
    """
    logger.info("=" * 70)
    logger.info("🧾 [INVOICE-GEN] Menerima permintaan generate invoice.")
    logger.info(f"   📌 conversation_id : '{request.conversation_id}'")
    logger.info(f"   🏢 company_name    : '{request.company_name}'")

    # ------------------------------------------------------------------
    # 1. Tarik state dari MemorySaver LangGraph
    # ------------------------------------------------------------------
    config = {"configurable": {"thread_id": request.conversation_id}}

    try:
        state_snapshot = app_graph.get_state(config)
        state_values = state_snapshot.values
        logger.info("✅ [INVOICE-GEN] State LangGraph berhasil ditarik.")
    except Exception as e:
        logger.error(f"💥 [INVOICE-GEN] Gagal mengambil state dari LangGraph: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengakses memori sesi negosiasi: {str(e)}"
        )

    # ------------------------------------------------------------------
    # 2. Validasi — state tidak boleh kosong
    # ------------------------------------------------------------------
    if not state_values:
        logger.warning(
            f"⚠️ [INVOICE-GEN] State kosong untuk thread_id='{request.conversation_id}'. "
            "Sesi mungkin belum dimulai atau conversation_id salah."
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Sesi negosiasi dengan conversation_id '{request.conversation_id}' "
                "tidak ditemukan atau belum memiliki data. Pastikan ID percakapan sudah benar."
            )
        )

    # ------------------------------------------------------------------
    # 3. Ekstrak variabel mutlak dari state
    # ------------------------------------------------------------------
    rab_items: list = state_values.get("rab_items", [])
    final_agreed_discount: float = float(state_values.get("final_agreed_discount", 0.0))

    logger.info(f"   📦 rab_items            : {len(rab_items)} item ditemukan.")
    logger.info(f"   💰 final_agreed_discount : {final_agreed_discount}%")

    if not rab_items:
        logger.warning("⚠️ [INVOICE-GEN] rab_items kosong. Invoice tidak dapat digenerate.")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Data RAB (rab_items) kosong dalam sesi ini. "
                "Pastikan dokumen RAB sudah diunggah dan diproses sebelum membuat invoice."
            )
        )

    # ------------------------------------------------------------------
    # 4. Iterasi rab_items — hitung total per baris
    # ------------------------------------------------------------------
    invoice_line_items = []
    subtotal = 0.0

    for idx, item in enumerate(rab_items):
        item_name = item.get("name") or item.get("item_name") or item.get("description") or f"Item {idx + 1}"
        quantity = float(item.get("quantity") or item.get("qty") or 1.0)
        unit = item.get("unit") or item.get("satuan") or "unit"

        # Fallback harga jika tidak tersedia di state item
        price = item.get("price") or item.get("harga") or item.get("unit_price")
        if price is None:
            price = DEFAULT_PRICE_FALLBACK
            logger.warning(
                f"   ⚠️  Item [{idx + 1}] '{item_name}' tidak memiliki 'price'. "
                f"Menggunakan fallback: Rp {DEFAULT_PRICE_FALLBACK:,.0f}"
            )
        price = float(price)

        line_total = quantity * price
        subtotal += line_total

        invoice_line_items.append({
            "no": idx + 1,
            "description": item_name,
            "quantity": quantity,
            "unit": unit,
            "unit_price": price,
            "line_total": round(line_total, 2),
        })

        logger.info(
            f"   ✅ Item [{idx + 1}] '{item_name}' | "
            f"Qty: {quantity} {unit} × Rp {price:,.0f} = Rp {line_total:,.0f}"
        )

    # ------------------------------------------------------------------
    # 5. Hitung ringkasan kalkulasi
    # ------------------------------------------------------------------
    discount_amount = subtotal * (final_agreed_discount / 100.0)
    grand_total = subtotal - discount_amount

    logger.info(f"   🧮 Subtotal         : Rp {subtotal:,.2f}")
    logger.info(f"   🏷️  Diskon ({final_agreed_discount}%)   : Rp {discount_amount:,.2f}")
    logger.info(f"   💵 Grand Total      : Rp {grand_total:,.2f}")

    # ------------------------------------------------------------------
    # 6. Susun nomor invoice otomatis dan tanggal
    # ------------------------------------------------------------------
    invoice_number = f"INV-QHOME-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    invoice_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    logger.info(f"   🔖 Nomor Invoice    : {invoice_number}")
    logger.info("✅ [INVOICE-GEN] Invoice berhasil digenerate. Mengembalikan respons ke frontend.")
    logger.info("=" * 70)

    # ------------------------------------------------------------------
    # 7. Kembalikan JSON invoice terstruktur
    # ------------------------------------------------------------------
    return {
        "status": "success",
        "message": "Invoice berhasil digenerate dari data sesi negosiasi.",
        "data": {
            "invoice_number": invoice_number,
            "invoice_date": invoice_date,
            "client": {
                "company_name": request.company_name,
                "conversation_id": request.conversation_id,
            },
            "items": invoice_line_items,
            "summary": {
                "subtotal": round(subtotal, 2),
                "discount_percentage": final_agreed_discount,
                "discount_amount": round(discount_amount, 2),
                "grand_total": round(grand_total, 2),
            },
        },
    }
