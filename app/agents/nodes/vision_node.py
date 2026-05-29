import logging
import traceback
from app.agents.state import B2BNegotiationState

# Import langsung dari service yang sudah Anda buat
from app.services.vision_agent import extract_rab_from_file

# Setup Logger khusus untuk modul Vision
logger = logging.getLogger(__name__)

async def execute_vision_node(state: B2BNegotiationState) -> dict:
    """
    Node untuk mengeksekusi ekstraksi dokumen RAB.
    Mendelegasikan proses berat ke service vision_agent.
    """
    logger.info("==========================================================================")
    logger.info("👁️ [VISION - START] Memulai Eksekusi Node Pembaca Dokumen (RAB)")
    logger.info("==========================================================================")

    file_bytes = state.get("uploaded_file_bytes")
    mime_type = state.get("uploaded_file_mime_type")

    # Jika tidak ada file yang perlu diproses, langsung lewati node ini
    if not file_bytes or not mime_type:
        logger.info("⏩ [VISION - SKIP] State dokumen kosong. Melewati rute ekstraksi AI.")
        return {}

    # Lacak detail berkas yang masuk
    file_size_kb = len(file_bytes) / 1024
    logger.info("📥 [VISION - INPUT] Dokumen RAB terdeteksi di memori:")
    logger.info(f"   ↳ Tipe MIME : {mime_type}")
    logger.info(f"   ↳ Ukuran    : {file_size_kb:.2f} KB")

    try:
        logger.info("🔍 [VISION - PROCESS] Mengirim dokumen ke Vision API (Gemini/GPT-4o) untuk dianalisis...")
        
        # Panggil service ekstraksi
        extraction_result = await extract_rab_from_file(file_bytes, mime_type)
        
        extracted_items = extraction_result.get("items", [])
        logger.info(f"✅ [VISION - SUCCESS] Ekstraksi selesai! AI Vision menemukan {len(extracted_items)} item material.")
        
        # Intip data pertama untuk memastikan ekstraksi tidak halusinasi
        if extracted_items:
            first_item = extracted_items[0]
            item_name = first_item.get("name", first_item.get("item_name", "N/A"))
            item_qty = first_item.get("quantity", first_item.get("qty", 0))
            logger.info(f"   ↳ Sampel Data Teratas: '{item_name}' (Qty: {item_qty})")

        # Gabungkan item baru ini dengan item RAB yang mungkin sudah ada di state sebelumnya
        existing_rab = state.get("rab_items", [])
        merged_rab = existing_rab + extracted_items

        logger.info(f"🔄 [VISION - MERGE] Total RAB di memori saat ini menjadi: {len(merged_rab)} item.")
        logger.info("💾 [VISION - END_STATE] Menghapus cache dokumen dari State (Anti-Infinite Loop).")
        logger.info("==========================================================================")

        # Kembalikan data RAB yang sudah diperbarui
        # Reset state file WAJIB agar tidak diproses ulang di putaran (loop) berikutnya
        return {
            "rab_items": merged_rab,
            "uploaded_file_bytes": None,
            "uploaded_file_mime_type": None
        }

    except Exception as e:
        # Lacak kegagalan jika API Vision timeout atau file corrupt
        logger.error("💥 [VISION - FATAL_ERROR] AI Vision gagal membaca atau memproses dokumen!")
        logger.error(f"   ↳ Detail Pesan: {str(e)}")
        logger.error(f"   ↳ Stack Trace:\n{traceback.format_exc()}")
        
        logger.warning("🛟 [VISION - FALLBACK] Menghapus file rusak dari State agar sistem tidak terjebak (Stuck).")
        logger.info("==========================================================================")
        
        # Kosongkan penampung file agar tidak menyebabkan infinite loop pada LangGraph jika error
        return {
            "uploaded_file_bytes": None,
            "uploaded_file_mime_type": None
        }