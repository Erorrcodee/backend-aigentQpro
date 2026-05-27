import logging
from app.agents.state import B2BNegotiationState
from app.services.maut_calculator import MAUTCalculator
from app.services.recommendation_engine import recommendation_engine

# Import dependencies untuk database jika dibutuhkan (opsional tergantung desain)

from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

# Instansiasi MAUT
maut_engine = MAUTCalculator()

async def execute_pricing_node(state: B2BNegotiationState) -> dict:
    """
    Node LangGraph untuk mengeksekusi perhitungan MAUT dan MBA.
    """
    logger.info("[NODE] Memasuki Pricing Node...")
    
    # 1. Tarik metrik proyek dari State
    metrics = state.get("project_metrics", {})
    rab_items = state.get("rab_items", [])
    
    # 2. Panggil MAUT Service
    allowed_discount = maut_engine.calculate_max_allowed_discount(
        project_metrics=metrics,
        max_discount_cap=12.0
    )
    
    cross_sell_opps = []
    
    # 3. Panggil MBA Service secara proaktif
    if rab_items:
        # Karena kita butuh AsyncSession untuk pgvector di MBA, kita buka koneksi singkat
        async with AsyncSessionLocal() as db:
            mba_analysis = await recommendation_engine.analyze_rab_basket(rab_items, db)
            cross_sell_opps = mba_analysis.get("cross_sell_opportunities", [])

    logger.info(f"[NODE] Pricing Selesai. Max Diskon: {allowed_discount}%, Cross-sell: {len(cross_sell_opps)} item.")
    
    # 4. Kembalikan data untuk di-update ke dalam State
    return {
        "maut_allowed_discount": allowed_discount,
        "mba_cross_sell_opportunities": cross_sell_opps
    }