import logging
from sqlalchemy import select

from app.agents.state import B2BNegotiationState
from app.core.database import AsyncSessionLocal
from app.models.product_catalog import Product
from app.services.maut_calculator import MAUTCalculator
from app.services.recommendation_engine import recommendation_engine
# Import service pembuat vektor
from app.services.embedding_service import generate_product_vector

logger = logging.getLogger(__name__)

# Instansiasi MAUT
maut_engine = MAUTCalculator()

async def execute_pricing_node(state: B2BNegotiationState) -> dict:
    """
    Node LangGraph untuk:
    1. Menangkap item dari dokumen RAB dan pesan obrolan (mentioned_products).
    2. Memvalidasi item menggunakan Semantic Search (Vector) ke PostgreSQL.
    3. Mengeksekusi MBA (Market Basket Analysis) secara proaktif.
    4. Menghitung diskon maksimal via MAUT berdasarkan metrik riil.
    """
    logger.info("[NODE] Memasuki Pricing Node (Vector Search Mode)...")

    rab_items = state.get("rab_items", [])
    mentioned_products = state.get("mentioned_products", [])
    existing_metrics = state.get("project_metrics", {})

    # Jika tidak ada RAB dan tidak ada barang yang disebut di chat, lewati pencarian
    if not rab_items and not mentioned_products:
        logger.info("[PRICING] Tidak ada target pencarian. Melewati node.")
        return {"product_catalog_facts": "", "negotiation_directives": ""}

    total_hpp_riil = 0.0
    total_volume_riil = 0.0
    validated_facts: list[str] = []
    negotiation_directives: list[str] = []
    cross_sell_opps: list[dict] = []

    # 1. KONSOLIDASI TARGET PENCARIAN
    # Gabungkan item dari RAB dan obrolan agar tidak ada duplikasi query
    search_targets = {}
    
    for item in rab_items:
        name = item.get("name") or item.get("item_name") or ""
        if name:
            search_targets[name.lower()] = float(item.get("quantity", item.get("qty", 0)))
            
    for mp in mentioned_products:
        if mp.lower() not in search_targets:
            search_targets[mp.lower()] = 0.0 # Kuantitas 0 karena hanya ditanyakan di chat

    # 2. EKSEKUSI PENCARIAN VEKTOR DI DATABASE
    async with AsyncSessionLocal() as db:
        for query_name, item_qty in search_targets.items():
            try:
                # Ubah teks pencarian menjadi vektor
                query_vector = await generate_product_vector(query_name)
                
                # Hitung jarak kosinus
                distance_col = Product.embedding.cosine_distance(query_vector).label("distance")
                
                stmt = (
                    select(Product, distance_col)
                    .where(Product.is_active == True)
                    .order_by(distance_col)
                    .limit(1)
                )
                
                result = await db.execute(stmt)
                row = result.first()

                if row:
                    product, dist = row
                    similarity = (1 - dist) * 100
                    
                    # Batas Kemiripan Ketat (Minimal 82%)
                    if similarity >= 82.0:
                        # PRODUK DITEMUKAN & VALID
                        hpp_line = product.price * item_qty
                        total_hpp_riil += hpp_line
                        total_volume_riil += item_qty

                        spec_text = ""
                        if product.specifications:
                            spec_entries = [f"{k}: {v}" for k, v in product.specifications.items()]
                            spec_text = "; ".join(spec_entries)

                        validated_facts.append(
                            f"[TERSEDIA] Kueri '{query_name}' cocok dengan: {product.name} (SKU: {product.sku}) | "
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
                        # DITEMUKAN TAPI TIDAK MIRIP (Mencegah Halusinasi)
                        validated_facts.append(f"[TIDAK TERSEDIA] Barang '{query_name}' tidak ditemukan di katalog.")
                        negotiation_directives.append(f"WAJIB jujur bahwa '{query_name}' sedang kosong/tidak tersedia.")
                else:
                    # SAMA SEKALI TIDAK ADA DI DATABASE
                    validated_facts.append(f"[TIDAK TERSEDIA] Barang '{query_name}' tidak ditemukan di katalog.")
                    
            except Exception as e:
                logger.error(f"Gagal memproses kueri vektor untuk '{query_name}': {str(e)}")

        # 3. EKSEKUSI MARKET BASKET ANALYSIS (MBA)
        if rab_items:
            mba_analysis = await recommendation_engine.analyze_rab_basket(rab_items, db)
            cross_sell_opps = mba_analysis.get("cross_sell_opportunities", [])

    # 4. KALKULASI DISKON MAUT
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
        "ATURAN UTAMA: Baca spesifikasi HANYA dari Fakta Katalog. Dilarang merekayasa spesifikasi atau harga."
    )

    logger.info(
        f"[NODE] Pricing Selesai. HPP Riil: Rp{total_hpp_riil:,.0f}, "
        f"Volume: {total_volume_riil}, Max Diskon: {allowed_discount}%"
    )

    # 5. PENGEMBALIAN STATE LANGGRAPH
    return {
        "project_metrics": real_project_metrics,
        "maut_allowed_discount": allowed_discount,
        "mba_cross_sell_opportunities": cross_sell_opps,
        "product_catalog_facts": "\n".join(validated_facts),
        "negotiation_directives": "\n".join(negotiation_directives),
    }