# app/services/recommendation_engine.py
import logging
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.product_catalog import Product
from app.models.analytics import AssociationRule
from app.services.embedding_service import generate_product_vector

logger = logging.getLogger(__name__)

class RecommendationEngine:
    def __init__(self):
        """
        Di tahap production, rules ini dihasilkan oleh Algoritma FP-Growth dari datawarehouse.
        Saat ini, rules mendefinisikan 'Makna Kategori' (bukan SKU mati), 
        yang nantinya akan diterjemahkan oleh pgvector secara dinamis.
        """
        self.logical_rules = {
            # Jika beli Semen/Keramik, probabilitas tinggi butuh Nat atau Perekat
            "semen": ["Semen instan perekat", "Pasir beton kualitas tinggi"],
            "keramik": ["Semen nat keramik anti jamur", "Semen instan perekat keramik"],
            "cat": ["Kuas roller set", "Thinner cat", "Dempul tembok"],
            "bata ringan": ["Semen mortar perekat bata ringan", "Besi beton tulangan praktis"]
        }

    async def get_alternative_products(self, base_item_name: str, db: AsyncSession, limit: int = 3) -> List[Dict]:
        """
        PENGGUNAAN PGVECTOR #1: Mencari Substitusi (Alternatif)
        Jika barang di RAB habis/tidak ada, cari barang paling mirip secara semantik.
        """
        logger.info(f"[ENGINE] Mencari substitusi via pgvector untuk: {base_item_name}")
        query_vector = await generate_product_vector(base_item_name)
        distance_col = Product.embedding.cosine_distance(query_vector).label("distance")
        
        stmt = (
            select(Product, distance_col)
            .filter(Product.is_active == True)
            .order_by(distance_col)
            .limit(limit)
        )
        
        result = await db.execute(stmt)
        matches = result.all()
        
        alternatives = []
        for product, dist in matches:
            similarity = (1 - dist) * 100
            if similarity >= 40.0:  # Toleransi lebih rendah untuk alternatif
                alternatives.append({
                    "sku": product.sku,
                    "name": product.name,
                    "price": product.price,
                    "similarity": round(similarity, 2)
                })
        return alternatives

    async def get_dynamic_cross_sell(self, target_semantic_query: str, db: AsyncSession) -> Dict:
        """
        PENGGUNAAN PGVECTOR #2: Resolusi MBA Dinamis
        Menerjemahkan aturan logika (contoh: "Semen nat keramik") menjadi 
        produk fisik yang benar-benar ada di stok gudang saat ini.
        """
        query_vector = await generate_product_vector(target_semantic_query)
        distance_col = Product.embedding.cosine_distance(query_vector).label("distance")
        
        stmt = (
            select(Product, distance_col)
            .filter(Product.is_active == True)
            .order_by(distance_col)
            .limit(1)  # Ambil 1 produk paling relevan untuk di-bundling
        )
        
        result = await db.execute(stmt)
        match = result.first()
        
        if match:
            product, dist = match
            if (1 - dist) * 100 >= 50.0:
                return {
                    "sku": product.sku,
                    "name": product.name,
                    "price": product.price,
                    "logical_reason": target_semantic_query
                }
        return {}

    async def analyze_rab_basket(self, rab_items: List[Dict], db: AsyncSession) -> Dict[str, Any]:
        """
        ANALISIS PROAKTIF (BASKET ANALYSIS) DINAMIS
        Membaca seluruh keranjang RAB klien secara proaktif, mencocokkannya dengan
        aturan asosiasi dinamis (FP-Growth) di database yang memiliki lift > 1.2,
        dan memecahkan nama rekomendasi menggunakan pgvector ke SKU produk fisik QHome.
        
        Args:
            rab_items: Daftar item dalam RAB saat ini.
            db: Sesi database asinkron.

        Returns:
            Dictionary berisi peluang lintas penjualan (cross-sell opportunities).
        """
        logger.info(f"[ENGINE] Membedah {len(rab_items)} item di keranjang RAB secara dinamis...")

        # 1. Ekstrak nama barang dalam RAB dalam huruf kecil untuk pencocokan set
        rab_names_set = set()
        for item in rab_items:
            name = item.get("name") or item.get("item_name")
            if name:
                rab_names_set.add(name.strip().lower())

        strategic_recommendations = []
        recommended_skus = set()

        # 2. Ambil aturan asosiasi dengan lift > 1.2 diurutkan dari confidence tertinggi
        stmt = (
            select(AssociationRule)
            .where(AssociationRule.lift > 1.2)
            .order_by(AssociationRule.confidence.desc())
        )
        result = await db.execute(stmt)
        rules = result.scalars().all()

        logger.info(f"[ENGINE] Ditemukan {len(rules)} aturan asosiasi aktif di database.")

        # 3. Evaluasi setiap aturan asosiasi secara berurutan
        for rule in rules:
            # Batasi rekomendasi maksimal 5 untuk menghindari overloading
            if len(strategic_recommendations) >= 5:
                break

            # Ekstrak item antecedent dan consequent (bisa berupa multi-item separated by comma)
            rule_antecedents = {x.strip().lower() for x in rule.antecedent.split(",")}
            rule_consequents = [x.strip().lower() for x in rule.consequent.split(",")]

            # Aturan terpicu jika seluruh item antecedent ada di dalam keranjang belanja (rab_names_set)
            if rule_antecedents.issubset(rab_names_set):
                
                # Cek consequent satu per satu
                for consequent_item in rule_consequents:
                    if len(strategic_recommendations) >= 5:
                        break

                    # Lewatkan jika barang rekomendasi sudah ada di dalam keranjang belanja saat ini
                    if consequent_item in rab_names_set:
                        continue

                    # Resolusi semantik via pgvector untuk mengubah nama barang menjadi SKU fisik di database
                    actual_product = await self.get_dynamic_cross_sell(consequent_item, db)
                    if actual_product:
                        sku = actual_product.get("sku")
                        
                        # Lewatkan jika SKU ini sudah pernah direkomendasikan dalam sesi analisis ini
                        if sku in recommended_skus:
                            continue

                        recommended_skus.add(sku)
                        strategic_recommendations.append({
                            "trigger_found_in_rab": rule.antecedent,
                            "confidence": round(rule.confidence, 4),
                            "lift": round(rule.lift, 4),
                            "suggested_product": actual_product
                        })

        return {
            "total_items_analyzed": len(rab_items),
            "cross_sell_opportunities": strategic_recommendations
        }

recommendation_engine = RecommendationEngine()