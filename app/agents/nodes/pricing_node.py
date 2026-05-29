import logging
import traceback
from sqlalchemy import select, or_, func

from app.agents.state import B2BNegotiationState
from app.core.database import AsyncSessionLocal
from app.models.product_catalog import Product
from app.services.maut_calculator import MAUTCalculator
from app.services.recommendation_engine import recommendation_engine
from app.services.embedding_service import generate_product_vector

# Setup Logger khusus untuk modul Pricing
logger = logging.getLogger(__name__)

# Instansiasi MAUT
maut_engine = MAUTCalculator()

async def execute_pricing_node(state: B2BNegotiationState) -> dict:
    logger.info("==========================================================================")
    logger.info("🏢 [PRICING - START] Memulai Eksekusi Node Validasi Katalog & Harga")
    logger.info("==========================================================================")

    rab_items = state.get("rab_items", [])
    mentioned_products = state.get("mentioned_products", [])
    existing_metrics = state.get("project_metrics", {})
    messages = state.get("messages", [])

    logger.info(f"📥 [PRICING - INPUT] Item RAB: {len(rab_items)} item | Produk dari Chat: {mentioned_products}")

    # Lapis Pertahanan Darurat: Jika Gateway kosong, tapi ada riwayat obrolan
    if not mentioned_products and not rab_items and messages:
        last_msg = messages[-1].content
        word_count = len(last_msg.split())
        if 1 < word_count <= 10:
            logger.warning("🛟 [PRICING - FALLBACK] Gateway kosong! Mengekstrak pesan terakhir sebagai kueri cadangan.")
            mentioned_products = [last_msg]
            logger.info(f"   ↳ Kueri diselamatkan: {mentioned_products}")

    # Lewati node jika benar-benar tidak ada target
    if not rab_items and not mentioned_products:
        logger.info("⏩ [PRICING - SKIP] Tidak ada target spesifik. Memberikan konteks katalog umum ke AI.")
        
        general_facts = (
            "[INFO UMUM QHOME] QHome adalah penyedia material B2B. "
            "Katalog kami mencakup: Semen, Besi Baja, Keramik, Granit, Pasir, Bata, dan Cat."
        )
        general_directives = "Sambut user dengan ramah. Beritahu mereka katalog kita secara singkat."
        
        return {
            "product_catalog_facts": general_facts, 
            "negotiation_directives": general_directives
        }

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

    logger.info(f"📋 [PRICING - TARGET] Daftar akhir yang akan dicari di database: {search_targets}")

    # ==========================================
    # 2. EKSEKUSI PENCARIAN HIBRIDA TINGKAT LANJUT
    # ==========================================
    async with AsyncSessionLocal() as db:
        for query_name, item_qty in search_targets.items():
            logger.info(f"🔍 [PRICING - SEARCH] Memproses kueri: '{query_name}' (Qty: {item_qty})")
            try:
                # Kalkulasi Vektor untuk Pencarian Makna
                logger.info("   ↳ Generate vektor semantik (Google Gemini)...")
                query_vector = await generate_product_vector(query_name)
                vector_distance = Product.embedding.cosine_distance(query_vector).label("vector_distance")
                
                # Kalkulasi Trigram untuk Toleransi Salah Ketik
                text_similarity = func.similarity(Product.name, query_name).label("text_similarity")
                
                stmt = (
                    select(Product, vector_distance, text_similarity)
                    .where(Product.is_active == True)
                    .where(
                        or_(
                            text_similarity > 0.25,  
                            vector_distance <= 0.45  
                        )
                    )
                    .order_by(text_similarity.desc(), vector_distance.asc())
                    .limit(1)
                )
                
                result = await db.execute(stmt)
                row = result.first()

                if row:
                    product, v_dist, t_sim = row
                    logger.info(f"✅ [PRICING - MATCH] Berhasil! '{query_name}' ➔ '{product.name}' (SKU: {product.sku})")
                    logger.info(f"   📊 Skor Evaluasi - Trigram: {t_sim:.2f} | Jarak Vektor: {v_dist:.2f}")
                    
                    hpp_line = product.price * item_qty
                    total_hpp_riil += hpp_line
                    total_volume_riil += item_qty

                    spec_text = ""
                    if product.specifications:
                        spec_entries = [f"{k}: {v}" for k, v in product.specifications.items()]
                        spec_text = "; ".join(spec_entries)

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
                    logger.warning(f"❌ [PRICING - MISS] Kueri '{query_name}' ditolak oleh database!")
                    logger.warning("   ↳ Alasan: Tidak memenuhi ambang batas Trigram (>0.25) maupun Vektor (<=0.45).")
                    
                    validated_facts.append(f"[TIDAK TERSEDIA] Barang '{query_name}' tidak ditemukan di katalog.")
                    negotiation_directives.append(f"WAJIB jujur bahwa '{query_name}' sedang kosong/tidak tersedia.")
                    
            except Exception as e:
                logger.error(f"💥 [PRICING - FATAL_ERROR] Kueri SQL atau Vektor gagal untuk '{query_name}'!")
                logger.error(f"   Detail Pesan: {str(e)}")
                logger.error(f"   Stack Trace:\n{traceback.format_exc()}")

        # ==========================================
        # 3. EKSEKUSI MARKET BASKET ANALYSIS (MBA)
        # ==========================================
        if rab_items:
            logger.info("🛒 [PRICING - MBA] Menjalankan algoritma Market Basket Analysis...")
            mba_analysis = await recommendation_engine.analyze_rab_basket(rab_items, db)
            cross_sell_opps = mba_analysis.get("cross_sell_opportunities", [])
            logger.info(f"   ↳ Ditemukan {len(cross_sell_opps)} peluang cross-selling.")

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

    logger.info("==========================================================================")
    logger.info("📈 [PRICING - SUMMARY] Hasil Akhir Kalkulasi Node:")
    logger.info(f"   💰 Total HPP Riil : Rp{total_hpp_riil:,.0f}")
    logger.info(f"   📦 Total Volume   : {total_volume_riil}")
    logger.info(f"   🎯 Diskon Maks MAUT: {allowed_discount}%")
    logger.info("💾 [PRICING - END_STATE] Mengirimkan hasil ke Negotiator Node.")
    logger.info("==========================================================================")

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