# test_mba.py
"""
Script pengujian mandiri asinkron untuk fitur Rekomendasi Lintas Penjualan (Cross-Selling).
Alur pengujian:
1. Membuat data transaksi (invoice) simulasi berstatus ISSUED di database.
2. Menjalankan penambangan aturan FP-Growth menggunakan mba_miner.
3. Memverifikasi penyimpanan aturan di tabel AssociationRule.
4. Menguji analisis keranjang RAB proaktif pada RecommendationEngine.
"""

import asyncio
import logging
from sqlalchemy import select, delete
from app.core.database import AsyncSessionLocal
from app.models.invoice import Invoice
from app.models.analytics import AssociationRule
from app.models.product_catalog import Product
from app.workers.mba_miner import run_fp_growth_miner
from app.services.recommendation_engine import recommendation_engine

# Konfigurasi Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TEST_MBA")

async def prepare_simulation_data(db):
    """
    Menyiapkan data simulasi produk dan invoice berstatus ISSUED di database.
    Menciptakan pola belanja: orang yang membeli 'semen' cenderung membeli 'pasir'.
    """
    logger.info("1. Menyiapkan data simulasi...")

    # Pastikan ada produk 'semen' dan 'pasir' di katalog produk
    # Kita cari produk yang ada atau buat baru jika tidak ada
    result = await db.execute(select(Product))
    products = result.scalars().all()
    
    if len(products) < 2:
        logger.info("Membuat produk dummy jika katalog kosong...")
        p1 = Product(sku="PROD-SEMEN", name="Semen Gresik Super", price=65000.0, is_active=True)
        p2 = Product(sku="PROD-PASIR", name="Pasir Beton Super", price=150000.0, is_active=True)
        db.add_all([p1, p2])
        await db.commit()
    
    # Hapus invoice lama berstatus ISSUED untuk pengujian terkontrol
    await db.execute(delete(Invoice).where(Invoice.status == "ISSUED"))
    await db.commit()

    # Buat 20 transaksi tiruan berstatus ISSUED untuk melampaui min_support (5%)
    # Pola: 15 transaksi membeli semen + pasir (asosiasi kuat), 5 membeli semen saja
    invoices_to_add = []
    
    # 15 transaksi (semen + pasir)
    for i in range(15):
        inv = Invoice(
            id=f"test-invoice-both-{i}",
            invoice_number=f"INV/TEST/BOTH/{i:03d}",
            items=[
                {"name": "semen", "qty": 10, "price": 65000.0},
                {"name": "pasir", "qty": 1, "price": 150000.0}
            ],
            discount_applied=0.0,
            status="ISSUED"
        )
        invoices_to_add.append(inv)
        
    # 5 transaksi (semen saja)
    for i in range(5):
        inv = Invoice(
            id=f"test-invoice-semen-{i}",
            invoice_number=f"INV/TEST/SEMEN/{i:03d}",
            items=[
                {"name": "semen", "qty": 5, "price": 65000.0}
            ],
            discount_applied=0.0,
            status="ISSUED"
        )
        invoices_to_add.append(inv)

    db.add_all(invoices_to_add)
    await db.commit()
    logger.info(f"Berhasil menambahkan {len(invoices_to_add)} invoice simulasi.")

async def test_cross_sell_flow():
    async with AsyncSessionLocal() as db:
        try:
            # 1. Siapkan data simulasi
            await prepare_simulation_data(db)

            # 2. Jalankan Data Miner FP-Growth
            logger.info("2. Menjalankan FP-Growth Miner...")
            await run_fp_growth_miner(db)

            # 3. Verifikasi hasil aturan asosiasi yang disimpan
            logger.info("3. Memverifikasi aturan asosiasi di database...")
            result = await db.execute(select(AssociationRule))
            rules = result.scalars().all()
            
            logger.info(f"Ditemukan {len(rules)} aturan asosiasi hasil FP-Growth:")
            for rule in rules:
                logger.info(f"Aturan: [{rule.antecedent}] => [{rule.consequent}] | Confidence: {rule.confidence} | Lift: {rule.lift}")

            assert len(rules) > 0, "Aturan asosiasi gagal dibuat!"

            # 4. Uji coba modul rekomendasi analyze_rab_basket
            logger.info("4. Menguji analisis keranjang belanja RAB...")
            test_rab = [
                {"item_name": "semen", "qty": 8, "price": 65000.0}
            ]
            
            # Kita uji apakah 'pasir' disarankan saat memasukkan 'semen'
            recs = await recommendation_engine.analyze_rab_basket(test_rab, db)
            logger.info(f"Hasil Analisis Rekomendasi: {recs}")
            
            # Bersihkan data simulasi setelah sukses
            logger.info("5. Membersihkan data simulasi...")
            await db.execute(delete(Invoice).where(Invoice.status == "ISSUED"))
            await db.execute(delete(AssociationRule))
            await db.commit()
            
            logger.info("PENGUJIAN SELESAI DENGAN SUKSES!")

        except Exception as e:
            await db.rollback()
            logger.error(f"PENGUJIAN GAGAL: {str(e)}")
            raise

if __name__ == "__main__":
    asyncio.run(test_cross_sell_flow())
