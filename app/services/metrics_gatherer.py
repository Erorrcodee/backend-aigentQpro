# app/services/metrics_gatherer.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.b2b_projects import B2BProject, ProjectStatus

async def calculate_loyalty_score(db: AsyncSession, user_id: int) -> float:
    """
    Menghitung total belanja kontraktor yang sudah DEAL (APPROVED) di masa lalu.
    """
    # 1. Query ke database: Jumlahkan (SUM) semua total_budget_final milik user ini
    stmt = select(func.sum(B2BProject.total_budget_final)).where(
        B2BProject.user_id == user_id,
        B2BProject.status == ProjectStatus.APPROVED
    )
    result = await db.execute(stmt)
    total_spent = result.scalar() or 0.0

    # 2. Terjemahkan total uang ke Skor Utilitas Loyalitas MAUT (0.0 - 1.0)
    if total_spent >= 100_000_000:
        return 1.0  # VIP Mutlak
    elif total_spent >= 50_000_000:
        return 0.7
    elif total_spent >= 10_000_000:
        return 0.4
    else:
        return 0.0  # User Baru atau Belanja Kecil

def parse_payment_term_score(term_string: str) -> float:
    """
    Menerjemahkan teks dari Frontend/AI menjadi Skor Utilitas Termin.
    """
    term = term_string.strip().lower()
    
    if "cash" in term or "tunai" in term:
        return 1.0
    elif "7 hari" in term or "seminggu" in term:
        return 0.8
    elif "14 hari" in term or "dua minggu" in term:
        return 0.5
    elif "30 hari" in term or "sebulan" in term:
        return 0.1
    
    return 0.3 # Default jika tidak terdeteksi jelas