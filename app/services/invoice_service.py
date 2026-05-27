# app/services/invoice_service.py
"""
Lapisan Layanan (Service Layer) untuk fitur Deal Lock & Invoice.
Bertanggung jawab atas seluruh logika bisnis pembuatan invoice:
  1. Mengunci nomor invoice di database.
  2. Me-render dokumen PDF di dalam memori (tanpa menyentuh disk lokal).
  3. Mengunggah PDF ke Cloudinary.
  4. Memperbarui URL unduhan pada catatan database.
"""
import io
import uuid
import logging
from datetime import datetime

import cloudinary
import cloudinary.uploader
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.invoice import Invoice

logger = logging.getLogger(__name__)

# --- Konfigurasi SDK Cloudinary dari variabel lingkungan (tidak ada hardcode) ---
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True  # Selalu gunakan HTTPS
)


def _generate_invoice_number() -> str:
    """
    Membuat nomor invoice yang unik berbasis timestamp dan ID acak pendek.
    Format: INV-YYYYMMDD-XXXXXXXX (contoh: INV-20260526-A3F2)
    """
    date_str = datetime.now().strftime("%Y%m%d")
    unique_suffix = uuid.uuid4().hex[:8].upper()
    return f"INV-{date_str}-{unique_suffix}"


def _render_invoice_pdf(invoice_number: str, rab_items: list, final_discount: float) -> bytes:
    """
    Fungsi helper untuk me-render data invoice ke dalam file PDF menggunakan ReportLab.
    Semua operasi terjadi di dalam memori (BytesIO), tidak ada file yang tersimpan di disk.

    Args:
        invoice_number: Nomor invoice unik.
        rab_items: Daftar item RAB yang disepakati.
        final_discount: Persentase diskon yang telah disetujui.

    Returns:
        Konten PDF dalam bentuk bytes (biner).
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    story = []

    # --- Header Dokumen ---
    title_style = ParagraphStyle(
        "InvoiceTitle",
        parent=styles["Heading1"],
        fontSize=20,
        textColor=colors.HexColor("#1a365d"),
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "InvoiceSubtitle",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.grey,
    )

    story.append(Paragraph("QHome Intelligence System", title_style))
    story.append(Paragraph("Platform Pengadaan Material B2B Berbasis AI", subtitle_style))
    story.append(Spacer(1, 0.5 * cm))

    # --- Blok Informasi Invoice ---
    info_style = ParagraphStyle(
        "InfoStyle", parent=styles["Normal"], fontSize=9, leading=14
    )
    issued_at = datetime.now().strftime("%d %B %Y, %H:%M WIB")
    story.append(Paragraph(f"<b>Nomor Invoice:</b> {invoice_number}", info_style))
    story.append(Paragraph(f"<b>Tanggal Terbit:</b> {issued_at}", info_style))
    story.append(Paragraph(f"<b>Diskon Disepakati:</b> {final_discount:.2f}%", info_style))
    story.append(Spacer(1, 0.7 * cm))

    # --- Tabel RAB Items ---
    story.append(Paragraph("<b>Rincian Item RAB yang Disepakati</b>", styles["Heading3"]))
    story.append(Spacer(1, 0.2 * cm))

    # Baris header tabel
    table_data = [["No.", "Nama Item / Produk", "Qty", "Satuan", "Harga Satuan (Rp)", "Subtotal (Rp)"]]

    total_before_discount = 0.0
    for idx, item in enumerate(rab_items, start=1):
        name = item.get("name", item.get("item_name", "N/A"))
        qty = item.get("qty", item.get("quantity", 0))
        unit = item.get("unit", item.get("satuan", "unit"))
        price = item.get("price", item.get("harga_satuan", 0))
        subtotal = qty * price
        total_before_discount += subtotal

        table_data.append([
            str(idx),
            name,
            str(qty),
            unit,
            f"{price:,.0f}",
            f"{subtotal:,.0f}",
        ])

    # Baris total
    discount_amount = total_before_discount * (final_discount / 100)
    grand_total = total_before_discount - discount_amount
    table_data.append(["", "", "", "", "Total Sebelum Diskon:", f"{total_before_discount:,.0f}"])
    table_data.append(["", "", "", "", f"Potongan Diskon ({final_discount:.2f}%):", f"-{discount_amount:,.0f}"])
    table_data.append(["", "", "", "", "TOTAL AKHIR:", f"{grand_total:,.0f}"])

    col_widths = [1 * cm, 6.5 * cm, 1.2 * cm, 1.5 * cm, 3.5 * cm, 3.5 * cm]
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        # Header
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a365d")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        # Data
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -4), [colors.white, colors.HexColor("#f0f4f8")]),
        ("GRID", (0, 0), (-1, -4), 0.5, colors.lightgrey),
        # Baris total (3 baris terakhir)
        ("ALIGN", (4, -3), (-1, -1), "RIGHT"),
        ("FONTNAME", (4, -1), (-1, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (4, -1), (-1, -1), colors.HexColor("#1a365d")),
        ("LINEABOVE", (4, -3), (-1, -3), 1, colors.grey),
        ("LINEABOVE", (4, -1), (-1, -1), 1.5, colors.HexColor("#1a365d")),
    ]))
    story.append(table)
    story.append(Spacer(1, 1 * cm))

    # --- Catatan Kaki ---
    footer_style = ParagraphStyle(
        "Footer", parent=styles["Normal"], fontSize=8, textColor=colors.grey
    )
    story.append(Paragraph(
        "Dokumen ini diterbitkan secara otomatis oleh Sistem QHome AI dan merupakan bukti "
        "kesepakatan transaksi yang sah. Harap simpan dokumen ini sebagai arsip resmi.",
        footer_style
    ))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


async def process_new_deal(rab_items: list, final_discount: float) -> dict:
    """
    Fungsi utama layanan untuk memproses transaksi yang telah disepakati (deal lock).
    Menjalankan 4 fase secara berurutan dalam satu transaksi database yang aman.

    Args:
        rab_items: Daftar item RAB dari state LangGraph.
        final_discount: Persentase diskon final yang telah disetujui negotiator.

    Returns:
        Dictionary berisi: status, invoice_number, dan download_url.

    Raises:
        Exception: Diteruskan ke pemanggil (invoice_node) untuk ditangani.
    """
    invoice_number = _generate_invoice_number()
    logger.info(f"[INVOICE SERVICE] Memulai pemrosesan deal. Nomor Invoice: {invoice_number}")

    async with AsyncSessionLocal() as db:
        try:
            # =========================================================
            # FASE 1: Kunci nomor invoice di database (atomic lock)
            # =========================================================
            new_invoice = Invoice(
                id=str(uuid.uuid4()),
                invoice_number=invoice_number,
                items=rab_items,
                discount_applied=final_discount,
                status="ISSUED",
            )
            db.add(new_invoice)
            await db.flush()  # Kirim ke DB dan validasi constraint UNIQUE tanpa commit penuh
            logger.info(f"[FASE 1] Record invoice '{invoice_number}' berhasil dikunci di database.")

            # =========================================================
            # FASE 2: Render PDF di dalam memori (tanpa menyentuh disk)
            # =========================================================
            pdf_bytes = _render_invoice_pdf(invoice_number, rab_items, final_discount)
            logger.info(f"[FASE 2] PDF berhasil di-render di memori. Ukuran: {len(pdf_bytes)} bytes.")

            # =========================================================
            # FASE 3: Upload biner PDF ke Cloudinary
            # =========================================================
            upload_result = cloudinary.uploader.upload(
                pdf_bytes,
                resource_type="raw",               # Wajib untuk file non-gambar (PDF)
                folder="qhome/invoices",            # Folder tujuan di Cloudinary
                public_id=invoice_number,           # Gunakan nomor invoice sebagai nama file
                format="pdf",
                overwrite=False,                    # Tolak penimpaan jika ID sudah ada
            )
            secure_url = upload_result.get("secure_url", "")
            logger.info(f"[FASE 3] PDF berhasil diunggah ke Cloudinary. URL: {secure_url}")

            # =========================================================
            # FASE 4: Perbarui kolom download_url pada record database
            # =========================================================
            new_invoice.download_url = secure_url
            await db.commit()
            logger.info(f"[FASE 4] URL unduhan berhasil diperbarui. Transaksi database di-commit.")

            return {
                "status": "success",
                "invoice_number": invoice_number,
                "download_url": secure_url,
            }

        except Exception as e:
            await db.rollback()
            logger.error(f"[INVOICE SERVICE] Gagal memproses deal. Rollback dilakukan. Error: {str(e)}")
            raise


async def get_invoices_by_user(
    db: AsyncSession, 
    user_id: int
) -> List[Invoice]:
    """
    Mengambil daftar invoice berdasarkan ID pengguna (user_id).

    Args:
        db: Sesi database asinkron (AsyncSession).
        user_id: ID pengguna yang ingin dicari invoice-nya.

    Returns:
        Daftar objek Invoice milik pengguna tersebut.
    """
    stmt = select(Invoice).where(Invoice.user_id == user_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_invoice_detail(
    db: AsyncSession, 
    invoice_id: str, 
    user_id: int
) -> Optional[Invoice]:
    """
    Mengambil detail satu invoice spesifik berdasarkan ID invoice dan ID pengguna.
    Pemeriksaan user_id dilakukan untuk menjamin keamanan akses data antar klien.

    Args:
        db: Sesi database asinkron (AsyncSession).
        invoice_id: ID unik invoice yang dicari.
        user_id: ID pengguna pemilik invoice.

    Returns:
        Objek Invoice jika ditemukan dan sesuai kepemilikan, atau None jika tidak ditemukan.
    """
    stmt = select(Invoice).where(
        Invoice.id == invoice_id,
        Invoice.user_id == user_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

