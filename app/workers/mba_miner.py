# app/workers/mba_miner.py
"""
Pekerja Penambang Data (Data Mining Worker) untuk Market Basket Analysis (MBA).
Mengekstrak aturan asosiasi dinamis menggunakan algoritma FP-Growth dari data historis invoice.
Proses CPU-bound ditangani dalam thread pool agar tidak memblokir antrean event loop FastAPI.
"""

import asyncio
import logging
import uuid
import pandas as pd
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.core.database import AsyncSessionLocal
from app.models.invoice import Invoice
from app.models.analytics import AssociationRule

# Konfigurasi logger
logger = logging.getLogger(__name__)

def _mine_rules_cpu_bound(dataset: List[List[str]]) -> pd.DataFrame:
    """
    Fungsi internal sinkron untuk menjalankan algoritma FP-Growth dan pembuatan aturan asosiasi.
    Menghindari pemblokiran event loop karena dijalankan sebagai tugas CPU-bound.
    """
    from mlxtend.preprocessing import TransactionEncoder
    from mlxtend.frequent_patterns import fpgrowth, association_rules

    # 1. Mengubah transaksi menjadi representasi array boolean
    te = TransactionEncoder()
    te_ary = te.fit(dataset).transform(dataset)
    df = pd.DataFrame(te_ary, columns=te.columns_)

    # 2. Menjalankan algoritma FP-Growth dengan dukungan minimum 5%
    frequent_itemsets = fpgrowth(df, min_support=0.05, use_colnames=True)
    if frequent_itemsets.empty:
        logger.warning("[MBA MINER] Tidak ditemukan frequent itemset dengan minimum support 0.05.")
        return pd.DataFrame()

    # 3. Menghasilkan aturan asosiasi dengan minimum confidence 30%
    rules = association_rules(frequent_itemsets, metric="confidence", min_threshold=0.3)
    if rules.empty:
        logger.warning("[MBA MINER] Tidak ditemukan aturan asosiasi yang memenuhi threshold confidence 0.3.")
        return pd.DataFrame()

    # 4. Menyaring aturan dengan nilai lift > 1.0 (korelasi positif)
    filtered_rules = rules[rules["lift"] > 1.0]
    return filtered_rules

async def run_fp_growth_miner(db: AsyncSession = None) -> None:
    """
    Menjalankan proses penambangan aturan asosiasi baru secara berkala.
    Jika parameter `db` tidak disediakan, fungsi ini akan membuka sesi database tersendiri.

    Args:
        db: Sesi database asinkron (AsyncSession) opsional.
    """
    logger.info("[MBA MINER] Memulai pekerja penambangan data FP-Growth...")
    
    if db is None:
        async with AsyncSessionLocal() as session:
            await _execute_miner(session)
    else:
        await _execute_miner(db)

async def _execute_miner(db: AsyncSession) -> None:
    """Eksekusi logika penambangan data dalam sesi database yang valid."""
    try:
        # 1. Ambil data keranjang belanja (kolom items) dari invoice berstatus ISSUED
        stmt = select(Invoice).where(Invoice.status == "ISSUED")
        result = await db.execute(stmt)
        invoices = result.scalars().all()

        # 2. Ekstrak data menjadi list of lists nama produk (huruf kecil, tanpa spasi berlebih)
        dataset = []
        for inv in invoices:
            items_list = inv.items
            if not items_list or not isinstance(items_list, list):
                continue
            
            basket = []
            for item in items_list:
                if not isinstance(item, dict):
                    continue
                name = item.get("name") or item.get("item_name")
                if name:
                    basket.append(name.strip().lower())
            
            # Hanya simpan keranjang belanja yang memiliki lebih dari 1 item (market basket)
            if len(basket) > 1:
                dataset.append(basket)

        logger.info(f"[MBA MINER] Mengekstrak {len(dataset)} keranjang belanja valid dari {len(invoices)} invoice.")

        # Jika tidak ada transaksi yang valid untuk dianalisis, kosongkan tabel aturan dan selesai
        if not dataset or len(dataset) < 2:
            logger.warning("[MBA MINER] Data transaksi berstatus ISSUED terlalu sedikit. Mengosongkan aturan asosiasi lama.")
            await db.execute(delete(AssociationRule))
            await db.commit()
            return

        # 3. Jalankan fungsi penambangan CPU-bound di thread pool terpisah agar tidak memblokir FastAPI
        rules_df = await asyncio.to_thread(_mine_rules_cpu_bound, dataset)

        # 4. Hapus seluruh data aturan asosiasi lama
        await db.execute(delete(AssociationRule))

        # 5. Jika ada aturan baru yang ditemukan, simpan ke database
        if not rules_df.empty:
            total_rules = 0
            for _, row in rules_df.iterrows():
                # Ubah frozenset dari antecedent & consequent menjadi representasi teks/string terurut
                antecedent_str = ", ".join(sorted(list(row["antecedents"])))
                consequent_str = ", ".join(sorted(list(row["consequents"])))

                new_rule = AssociationRule(
                    id=str(uuid.uuid4()),
                    antecedent=antecedent_str,
                    consequent=consequent_str,
                    confidence=float(row["confidence"]),
                    lift=float(row["lift"])
                )
                db.add(new_rule)
                total_rules += 1

            await db.commit()
            logger.info(f"[MBA MINER] Sukses memperbarui aturan asosiasi. {total_rules} aturan baru disimpan.")
        else:
            await db.commit()
            logger.info("[MBA MINER] Tidak ada aturan baru yang disimpan karena tidak memenuhi kriteria penyaringan.")

    except Exception as e:
        await db.rollback()
        logger.error(f"[MBA MINER] Terjadi kesalahan saat menjalankan penambangan data FP-Growth: {str(e)}")
        raise
