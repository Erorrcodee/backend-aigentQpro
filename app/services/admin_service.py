# app/services/admin_service.py
"""
Lapisan Layanan (Service Layer) untuk Dasbor Analitik Admin.
Menyediakan kalkulasi metrik bisnis secara asinkron dari database.
"""

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.invoice import Invoice
from app.models.b2b_projects import B2BProject

logger = logging.getLogger(__name__)

async def get_deal_conversion_rate(db: AsyncSession) -> float:
    """
    Menghitung persentase invoice dengan status "ISSUED" berbanding
    dengan estimasi total sesi negosiasi (jumlah proyek B2B keseluruhan).

    Args:
        db: Sesi database asinkron (AsyncSession).

    Returns:
        Nilai persentase konversi deal dalam format float (0.0 - 100.0).
    """
    # 1. Hitung total invoice yang berstatus ISSUED
    stmt_issued = select(func.count(Invoice.id)).where(Invoice.status == "ISSUED")
    result_issued = await db.execute(stmt_issued)
    issued_count = result_issued.scalar() or 0

    # 2. Hitung total sesi negosiasi (seluruh proyek B2B)
    stmt_total_projects = select(func.count(B2BProject.id))
    result_projects = await db.execute(stmt_total_projects)
    total_projects = result_projects.scalar() or 0

    # 3. Hitung persentase konversi
    if total_projects == 0:
        return 0.0
        
    conversion_rate = (issued_count / total_projects) * 100.0
    return round(conversion_rate, 2)

async def get_average_margin_discount(db: AsyncSession) -> float:
    """
    Menghitung rata-rata persentase dari kolom discount_applied pada semua
    invoice yang telah diterbitkan (mencapai kesepakatan).

    Args:
        db: Sesi database asinkron (AsyncSession).

    Returns:
        Nilai rata-rata persentase diskon yang disepakati (float).
    """
    stmt = select(func.avg(Invoice.discount_applied))
    result = await db.execute(stmt)
    average_discount = result.scalar()
    
    if average_discount is None:
        return 0.0
        
    return round(float(average_discount), 2)
