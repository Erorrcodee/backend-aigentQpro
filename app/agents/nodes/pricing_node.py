import logging
from sqlalchemy import select, or_, func

from app.agents.state import B2BNegotiationState
from app.core.database import AsyncSessionLocal
from app.models.product_catalog import Product
from app.services.maut_calculator import MAUTCalculator
from app.services.recommendation_engine import recommendation_engine
from app.services.embedding_service import generate_product_vector

logger = logging.getLogger(__name__)

# Instansiasi MAUT
maut_engine = MAUTCalculator()

async def execute_pricing_node(state: B2BNegotiationState) -> dict:
    """
    Node LangGraph untuk:
    1. Menangkap item dari dokumen RAB dan pesan obrolan.
    2. Memvalidasi item menggunakan Ultimate Hybrid Search (Trigram Typo-Tolerance + Vector).
    3. Mengeksekusi MBA (Market Basket Analysis) secara proaktif.
    4. Menghitung diskon maksimal via MAUT berdasarkan metrik riil.
    """
    logger.info("[NODE] Memasuki Pricing Node (Ultimate Hybrid Search Mode)...")

    rab_items = state.get("rab_items", [])
    mentioned_products = state.get("mentioned_products", [])
    existing_metrics = state.get("project_metrics", {})

    # Lewati node jika tidak ada target pencarian dari RAB maupun obrolan
    if not rab_items and not mentioned_products:
        logger.info("[PRICING] Tidak ada target pencarian. Melewati node.")
        return {"product_catalog_facts": "", "negotiation_directives": ""}

    total_hpp_riil = 0.0
    total_volume_riil = 0.0
    validated_facts: list[str] = []
    negotiation_directives: list[str] = []
    cross_sell_opps: list[dict] = []

    # ==========================================
    # 1. KONSOLIDASI TARGET PENCARIAN
    # ==========================================
    search_targets = {}
    
    for item in rab_items:
        name = item.get("name") or item.get("item_name") or ""
        if name:
            search_targets[name.lower()] = float(item.get("quantity", item.get("qty", 0)))
            
    for mp in mentioned_products:
        if mp.lower() not in search_targets:
            search_targets[mp.lower()] = 0.0 

    # ==========================================
    # 2. EKSEKUSI PENCARIAN HIBRIDA TINGKAT LANJUT
    # ==========================================
    async with AsyncSessionLocal() as db:
        for query_name, item_qty in search_targets.items():
            try:
                # Kalkulasi Vektor untuk Pencarian Makna (Semantic)
                query_vector = await generate_product_vector(query_name)
                vector_distance = Product.embedding.cosine_distance(query_vector).label("vector_distance")
                
                # Kalkulasi Trigram untuk Toleransi Salah Ketik (Typo)
                text_similarity = func.similarity(Product.name, query_name).label("text_similarity")
                
                # PENCARIAN HIBRIDA: Lolos jika teks mirip secara ketikan ATAU makna vektor mendekati
                stmt = (
                    select(Product, vector_distance, text_similarity)
                    .where(Product.is_active == True)
                    .where(
                        or_(
                            text_similarity > 0.25,  # Toleransi salah ketik moderat
                            vector_distance <= 0.45  # Toleransi makna semantik (55% similarity)
                        )
                    )
                    # Prioritaskan teks yang paling mirip secara ketikan, baru kemudian kemiripan makna
                    .order_by(text_similarity.desc(), vector_distance.asc())
                    .limit(1)
                )
                
                result = await db.execute(stmt)
                row = result.first()

                if row:
                    product, v_dist, t_sim = row
                    
                    # PRODUK VALID
                    hpp_line = product.price * item_qty
                    total_hpp_riil += hpp_line
                    total_volume_riil += item_qty

                    spec_text = ""
                    if product.specifications:
                        spec_entries = [f"{k}: {v}" for k, v in product.specifications.items()]
                        spec_text = "; ".join(spec_entries)

                    # Fakta untuk AI Negosiator
                    validated_facts.append(
                        f"[TERSEDIA] Kueri '{query_name}' dikaitkan dengan: {product.name} (SKU: {product.sku}) | "
                        f"Harga: Rp{product.price:,.0f}/{product.unit} | "
                        f"Stok: {product.stock} {product.unit} | "
                        f"Spesifikasi: {spec_text or 'Tidak ada data spesifikasi'}"
                    )

                    if item_qty > 0:
                        tier_label = "TIER-3 (Volume Besar)" if item_qty >= 100 else "TIER-2 (Volume Sedang)" if item_qty >= 50 else "TIER-1 (Volume Kecil)"
                        negotiation_directives.append(
                            f"Untuk '{product.name}': Kuantitas {item_qty} masuk {tier_label}. "
                            f"HPP riil: Rp{product.price:,.0f}. Jangan berikan diskon di bawah HPP."
                        )
                else:
                    # SAMA SEKALI TIDAK DITEMUKAN
                    validated_facts.append(f"[TIDAK TERSEDIA] Barang '{query_name}' tidak ditemukan di katalog.")
                    negotiation_directives.append(f"WAJIB jujur bahwa '{query_name}' sedang kosong/tidak tersedia.")
                    
            except Exception as e:
                logger.error(f"Gagal memproses kueri hibrida untuk '{query_name}': {str(e)}")

        # ==========================================
        # 3. EKSEKUSI MARKET BASKET ANALYSIS (MBA)
        # ==========================================
        if rab_items:
            mba_analysis = await recommendation_engine.analyze_rab_basket(rab_items, db)
            cross_sell_opps = mba_analysis.get("cross_sell_opportunities", [])

    # ==========================================
    # 4. KALKULASI DISKON MAUT
    # ==========================================
    real_project_metrics = {
        "total_hpp_estimated": total_hpp_riil,
        "total_volume": total_volume_riil,
        "client_loyalty_score": existing_metrics.get("client_loyalty_score", existing_metrics.get("loyalty_score", 0.0)),
        "profit_rupiah": existing_metrics.get("profit_rupiah", total_hpp_riil * 0.15),
        "total_items": total_volume_riil,
        "payment_term_score": existing_metrics.get("payment_term_score", 0.5),
        "loyalty_score": existing_metrics.get("loyalty_score", 0.0),
        "ai_strategic_value": existing_metrics.get("ai_strategic_value", 0.0),
    }

    allowed_discount = maut_engine.calculate_max_allowed_discount(
        project_metrics=real_project_metrics,
        max_discount_cap=12.0,
    )

    negotiation_directives.append(
        "ATURAN UTAMA: Baca spesifikasi dan stok HANYA dari Fakta Katalog. Dilarang merekayasa spesifikasi atau harga."
    )

    logger.info(
        f"[NODE] Pricing Selesai. HPP Riil: Rp{total_hpp_riil:,.0f}, "
        f"Volume: {total_volume_riil}, Max Diskon: {allowed_discount}%"
    )

    # ==========================================
    # 5. PENGEMBALIAN STATE LANGGRAPH
    # ==========================================
    return {
        "project_metrics": real_project_metrics,
        "maut_allowed_discount": allowed_discount,
        "mba_cross_sell_opportunities": cross_sell_opps,
        "product_catalog_facts": "\n".join(validated_facts),
        "negotiation_directives": "\n".join(negotiation_directives),
    }