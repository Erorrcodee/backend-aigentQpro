# app/services/maut_config_service.py
"""
Lapisan Layanan (Service Layer) untuk Manajemen Konfigurasi Bobot MAUT.
Bertanggung jawab atas operasi CRUD asinkron terhadap tabel maut_weight_configs.
"""

import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models.maut_weight_config import MautWeightConfig
from app.schemas.maut_schema import MautWeightConfigCreate

logger = logging.getLogger(__name__)

async def get_active_maut_config(db: AsyncSession) -> MautWeightConfig:
    """
    Mengambil konfigurasi bobot MAUT yang saat ini aktif.
    Jika belum ada konfigurasi aktif di database, sistem akan membuat
    konfigurasi default awal dan menyimpannya ke database.

    Args:
        db: Sesi database asinkron (AsyncSession).

    Returns:
        Objek MautWeightConfig yang aktif.
    """
    stmt = (
        select(MautWeightConfig)
        .where(MautWeightConfig.is_active == True)
        .order_by(MautWeightConfig.id.desc())
    )
    result = await db.execute(stmt)
    active_config = result.scalars().first()

    if not active_config:
        # Jika belum ada konfigurasi aktif, buat nilai bawaan default
        logger.info("[MAUT CONFIG SERVICE] Konfigurasi aktif tidak ditemukan. Membuat konfigurasi default baru.")
        active_config = MautWeightConfig(
            profit_margin=0.40,
            volume_tier=0.20,
            payment_term=0.15,
            loyalty_history=0.15,
            ai_strategic_value=0.10,
            is_active=True
        )
        db.add(active_config)
        await db.commit()
        await db.refresh(active_config)

    return active_config

async def upsert_maut_config(
    db: AsyncSession, 
    config_in: MautWeightConfigCreate
) -> MautWeightConfig:
    """
    Membuat konfigurasi bobot MAUT aktif yang baru (upsert/update).
    Untuk memastikan hanya ada satu konfigurasi aktif, fungsi ini akan terlebih
    dahulu menonaktifkan seluruh konfigurasi aktif lama sebelum menyimpan yang baru.

    Args:
        db: Sesi database asinkron (AsyncSession).
        config_in: Skema data input bobot MAUT yang baru.

    Returns:
        Objek MautWeightConfig baru yang telah diaktifkan dan disimpan.
    """
    # 1. Menonaktifkan semua konfigurasi aktif yang sudah ada
    stmt_deactivate = (
        update(MautWeightConfig)
        .where(MautWeightConfig.is_active == True)
        .values(is_active=False)
    )
    await db.execute(stmt_deactivate)

    # 2. Membuat konfigurasi aktif yang baru
    new_config = MautWeightConfig(
        profit_margin=config_in.profit_margin,
        volume_tier=config_in.volume_tier,
        payment_term=config_in.payment_term,
        loyalty_history=config_in.loyalty_history,
        ai_strategic_value=config_in.ai_strategic_value,
        is_active=True
    )
    db.add(new_config)
    await db.commit()
    await db.refresh(new_config)
    
    logger.info(f"[MAUT CONFIG SERVICE] Konfigurasi bobot MAUT baru dengan ID {new_config.id} berhasil diaktifkan.")
    return new_config

async def delete_maut_config(
    db: AsyncSession, 
    config_id: int
) -> bool:
    """
    Menghapus konfigurasi bobot MAUT dari database berdasarkan ID.

    Args:
        db: Sesi database asinkron (AsyncSession).
        config_id: ID konfigurasi bobot yang ingin dihapus.

    Returns:
        Boolean yang menandakan apakah proses penghapusan berhasil.
    """
    stmt = select(MautWeightConfig).where(MautWeightConfig.id == config_id)
    result = await db.execute(stmt)
    config = result.scalar_one_or_none()

    if not config:
        return False

    # Jika konfigurasi yang dihapus sedang aktif, pastikan sistem tetap menyisakan setidaknya 1 konfigurasi aktif
    was_active = config.is_active

    await db.delete(config)
    await db.commit()

    if was_active:
        # Jika yang dihapus adalah konfigurasi aktif, panggil get_active_maut_config untuk memicu pembuatan default baru
        await get_active_maut_config(db)

    logger.info(f"[MAUT CONFIG SERVICE] Konfigurasi bobot MAUT dengan ID {config_id} berhasil dihapus.")
    return True
