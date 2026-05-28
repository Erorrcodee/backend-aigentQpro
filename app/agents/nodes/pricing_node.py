import logging

from sqlalchemy import select

from app.agents.state import B2BNegotiationState
from app.core.database import AsyncSessionLocal
from app.models.product_catalog import Product
from app.services.maut_calculator import MAUTCalculator
from app.services.recommendation_engine import recommendation_engine

logger = logging.getLogger(__name__)

# Instansiasi MAUT
maut_engine = MAUTCalculator()


async def execute_pricing_node(state: B2BNegotiationState) -> dict:
    """
    Node LangGraph untuk:
    1. Memvalidasi item RAB terhadap katalog produk riil di PostgreSQL.
    2. Mengeksekusi MBA (Market Basket Analysis) secara proaktif.
    3. Menghitung diskon maksimal via MAUT berdasarkan metrik riil.
    4. Menghasilkan product_catalog_facts & negotiation_directives
       untuk mengunci perilaku LLM pada node negosiator berikutnya.
    """
    logger.info("[NODE] Memasuki Pricing Node...")

    rab_items = state.get("rab_items", [])
    existing_metrics = state.get("project_metrics", {})

    # ================================================================
    # BAGIAN 2 & 3: Blok Database — Validasi Katalog + Eksekusi MBA
    # ================================================================
    total_hpp_riil = 0.0
    total_volume_riil = 0.0
    validated_facts: list[str] = []
    negotiation_directives: list[str] = []
    cross_sell_opps: list[dict] = []

    async with AsyncSessionLocal() as db:
        # --- Bagian 2: Iterasi RAB & Validasi terhadap Katalog ---
        for item in rab_items:
            item_name = item.get("name") or item.get("item_name") or ""
            item_qty = float(item.get("quantity", item.get("qty", 0)))
            item_unit = item.get("unit", "pcs")

            if not item_name:
                continue

            # Query produk dengan ILIKE untuk pencarian fleksibel
            stmt = (
                select(Product)
                .where(Product.name.ilike(f"%{item_name}%"))
                .where(Product.is_active == True)
                .limit(1)
            )
            result = await db.execute(stmt)
            product = result.scalar_one_or_none()

            if product:
                # --- PRODUK DITEMUKAN: Akumulasi metrik riil ---
                hpp_line = product.price * item_qty
                total_hpp_riil += hpp_line
                total_volume_riil += item_qty

                # Susun fakta spesifikasi dari DB
                spec_text = ""
                if product.specifications:
                    spec_entries = [
                        f"{k}: {v}"
                        for k, v in product.specifications.items()
                    ]
                    spec_text = "; ".join(spec_entries)

                validated_facts.append(
                    f"[TERSEDIA] {product.name} (SKU: {product.sku}) | "
                    f"Harga: Rp{product.price:,.0f}/{product.unit or item_unit} | "
                    f"Stok: {product.stock} {product.unit or item_unit} | "
                    f"Brand: {product.brand or '-'} | "
                    f"Spesifikasi: {spec_text or 'Tidak ada data spesifikasi'}"
                )

                # Instruksi tiering diskon berdasarkan kuantitas
                if item_qty >= 100:
                    tier_label = "TIER-3 (Volume Besar)"
                elif item_qty >= 50:
                    tier_label = "TIER-2 (Volume Sedang)"
                else:
                    tier_label = "TIER-1 (Volume Kecil)"

                negotiation_directives.append(
                    f"Untuk '{product.name}': Kuantitas {item_qty} {item_unit} "
                    f"masuk kategori {tier_label}. "
                    f"HPP riil per unit: Rp{product.price:,.0f}. "
                    f"Jangan berikan diskon di bawah HPP."
                )
            else:
                # --- PRODUK TIDAK DITEMUKAN ---
                validated_facts.append(
                    f"[TIDAK TERSEDIA] '{item_name}' tidak ditemukan "
                    f"di katalog produk QHome."
                )
                negotiation_directives.append(
                    f"Barang '{item_name}' TIDAK ADA di katalog. "
                    f"Kamu WAJIB jujur bahwa barang ini tidak tersedia. "
                    f"DILARANG KERAS mengarang spesifikasi atau harga."
                )

        # --- Bagian 3: Eksekusi MBA di dalam sesi database ---
        if rab_items:
            mba_analysis = await recommendation_engine.analyze_rab_basket(
                rab_items, db
            )
            cross_sell_opps = mba_analysis.get("cross_sell_opportunities", [])

    # ================================================================
    # BAGIAN 4: Eksekusi MAUT & Kompilasi Direktif (Di Luar Sesi DB)
    # ================================================================

    # Susun metrik riil dari hasil validasi katalog
    real_project_metrics = {
        "total_hpp_estimated": total_hpp_riil,
        "total_volume": total_volume_riil,
        "client_loyalty_score": existing_metrics.get(
            "client_loyalty_score",
            existing_metrics.get("loyalty_score", 0.0),
        ),
        # Pertahankan metrik existing yang relevan untuk kalkulasi MAUT
        "profit_rupiah": existing_metrics.get("profit_rupiah", total_hpp_riil * 0.15),
        "total_items": total_volume_riil,
        "payment_term_score": existing_metrics.get("payment_term_score", 0.5),
        "loyalty_score": existing_metrics.get("loyalty_score", 0.0),
        "ai_strategic_value": existing_metrics.get("ai_strategic_value", 0.0),
    }

    # Kalkulasi MAUT dengan metrik riil
    allowed_discount = maut_engine.calculate_max_allowed_discount(
        project_metrics=real_project_metrics,
        max_discount_cap=12.0,
    )

    # Kompilasi direktif akhir dengan aturan utama anti-halusinasi
    negotiation_directives.append(
        "ATURAN UTAMA: Baca spesifikasi HANYA dari Fakta Katalog. "
        "Dilarang merekayasa spesifikasi."
    )

    logger.info(
        f"[NODE] Pricing Selesai. HPP Riil: Rp{total_hpp_riil:,.0f}, "
        f"Volume: {total_volume_riil}, Max Diskon: {allowed_discount}%, "
        f"Cross-sell: {len(cross_sell_opps)} item."
    )

    # ================================================================
    # BAGIAN 5: Pengembalian State
    # ================================================================
    return {
        "project_metrics": real_project_metrics,
        "maut_allowed_discount": allowed_discount,
        "mba_cross_sell_opportunities": cross_sell_opps,
        "product_catalog_facts": "\n".join(validated_facts),
        "negotiation_directives": "\n".join(negotiation_directives),
    }