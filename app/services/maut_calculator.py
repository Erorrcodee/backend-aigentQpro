# app/services/maut_calculator.py
import logging
from typing import Dict, Any

# Konfigurasi Logging yang sangat jelas
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - MAUT_ENGINE - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

class MAUTCalculator:
    def __init__(self, admin_weights: Dict[str, float] = None):
        """
        Bobot default jika Admin belum mengatur di database.
        Total harus 1.0 (100%)
        """
        self.weights = admin_weights or {
            "profit_margin": 0.40,
            "volume_tier": 0.20,
            "payment_term": 0.15,
            "loyalty_history": 0.15,
            "ai_strategic_value": 0.10 # <-- Ruang dinamis dari obrolan
        }
        
        # Validasi keamanan matematika: Total bobot harus 1.0
        total_weight = sum(self.weights.values())
        if not (0.99 <= total_weight <= 1.01):
            logger.critical(f"FATAL MATH ERROR: Total bobot MAUT tidak 1.0 (Total: {total_weight})")
            raise ValueError("Bobot MAUT tidak valid.")

    def _normalize_utility(self, value: float, min_val: float, max_val: float) -> float:
        """
        Normalisasi angka riil ke skala 0.0 - 1.0 (Teori Utilitas MAUT)
        """
        if value <= min_val:
            return 0.0
        if value >= max_val:
            return 1.0
        return (value - min_val) / (max_val - min_val)

    def calculate_max_allowed_discount(self, project_metrics: Dict[str, float], max_discount_cap: float = 10.0) -> float:
        """
        Fungsi utama untuk menghitung berapa persentase diskon maksimal yang boleh diberikan AI.
        """
        logger.info(f"--- MEMULAI KALKULASI MAUT ---")
        logger.info(f"Metrik Masuk: {project_metrics}")

        # 1. Hitung Utilitas Profit Margin (Min 5 Juta, Max 50 Juta)
        margin_utility = self._normalize_utility(project_metrics.get("profit_rupiah", 0), 5000000, 50000000)
        
        # 2. Hitung Utilitas Volume Pembelian (Min 10 item, Max 1000 item)
        volume_utility = self._normalize_utility(project_metrics.get("total_items", 0), 10, 1000)
        
        # 3. Hitung Utilitas Termin Pembayaran (Skala 0-1. Cash = 1.0, Tempo 30 = 0.3)
        payment_utility = project_metrics.get("payment_term_score", 0.5) 
        
        # 4. Hitung Utilitas Loyalitas (0 = Pelanggan Baru, 1.0 = Pelanggan VIP)
        loyalty_utility = project_metrics.get("loyalty_score", 0.0)
        
        # 5. Hitung Utilitas Strategis dari Chat AI (0.0 - 1.0)
        strategic_utility = project_metrics.get("ai_strategic_value", 0.0)

        # KALKULASI AKHIR MAUT (Σ Utility * Weight)
        final_maut_score = (
            (margin_utility * self.weights["profit_margin"]) +
            (volume_utility * self.weights["volume_tier"]) +
            (payment_utility * self.weights["payment_term"]) +
            (loyalty_utility * self.weights["loyalty_history"]) +
            (strategic_utility * self.weights["ai_strategic_value"])
        )

        # Terjemahkan Skor MAUT (0.0 - 1.0) menjadi Persentase Diskon
        # Contoh: Jika max_discount_cap dari Admin adalah 8.5%, dan skor MAUT 0.5
        # Maka allowed_discount = 4.25%
        allowed_discount = final_maut_score * max_discount_cap
        
        # Pastikan tidak ada bug diskon minus
        allowed_discount = max(0.0, round(allowed_discount, 2))

        logger.info(f"[DETAIL UTILITAS] Margin: {margin_utility:.2f}, Volume: {volume_utility:.2f}, "
                    f"Payment: {payment_utility:.2f}, Loyalty: {loyalty_utility:.2f}, AI_Dynamic: {strategic_utility:.2f}")
        logger.info(f"[SKOR AKHIR MAUT]: {final_maut_score:.4f} (Max Diskon Diizinkan: {allowed_discount}%)")
        logger.info(f"--- KALKULASI MAUT SELESAI ---")

        return allowed_discount