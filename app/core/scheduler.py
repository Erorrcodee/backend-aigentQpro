# app/core/scheduler.py
"""
Sistem Penjadwalan Otomatis (Scheduler) menggunakan APScheduler.
Mengatur siklus hidup penjadwalan dan pemanggilan tugas data mining FP-Growth secara periodik harian.
"""

import logging
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.workers.mba_miner import run_fp_growth_miner

logger = logging.getLogger(__name__)

# Menginisialisasi AsyncIOScheduler untuk operasi asinkron non-blocking
scheduler = AsyncIOScheduler()

async def setup_scheduler(app: FastAPI) -> None:
    """
    Fungsi pengait (hook) startup untuk FastAPI.
    Menginisialisasi penjadwalan berkala aturan FP-Growth.

    Args:
        app: Instance dari FastAPI.
    """
    logger.info("[SCHEDULER] Memulai inisialisasi penjadwal otomatis...")

    # Menjadwalkan tugas berjalan setiap hari pada pukul 00:00 (tengah malam)
    scheduler.add_job(
        run_fp_growth_miner,
        trigger="cron",
        hour=0,
        minute=0,
        id="daily_fp_growth_mining",
        replace_existing=True
    )

    # Memulai eksekusi penjadwal
    scheduler.start()
    logger.info("[SCHEDULER] Penjadwal otomatis berhasil diaktifkan dan mendengarkan antrean.")

    # Menjalankan pemrosesan awal secara asinkron di latar belakang saat startup
    # agar aturan langsung terisi di database jika tabel kosong tanpa memblokir startup peladen.
    scheduler.add_job(
        run_fp_growth_miner,
        id="initial_fp_growth_mining_run"
    )

async def shutdown_scheduler() -> None:
    """
    Fungsi pengait (hook) shutdown untuk FastAPI.
    Menghentikan penjadwal otomatis dengan aman.
    """
    logger.info("[SCHEDULER] Menghentikan penjadwal otomatis secara aman...")
    scheduler.shutdown()
    logger.info("[SCHEDULER] Penjadwal otomatis berhasil dinonaktifkan.")
