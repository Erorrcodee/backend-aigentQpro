import logging
from app.agents.state import B2BNegotiationState

# Import langsung dari service yang sudah Anda buat
from app.services.vision_agent import extract_rab_from_file

logger = logging.getLogger(__name__)

async def execute_vision_node(state: B2BNegotiationState) -> dict:
    """
    Node untuk mengeksekusi ekstraksi dokumen RAB.
    Mendelegasikan proses berat ke service vision_agent.
    """
    logger.info("[NODE] Memasuki Vision Node...")

    file_bytes = state.get("uploaded_file_bytes")
    mime_type = state.get("uploaded_file_mime_type")

    # Jika tidak ada file yang perlu diproses, langsung lewati node ini
    if not file_bytes or not mime_type:
        logger.info("[VISION] Tidak ada dokumen yang perlu diekstrak. Melewati node.")
        return {}

    logger.info(f"[VISION] Mengirim file ({mime_type}) ke service ekstraksi...")
    
    try:
        # Panggil service yang sudah ada
        extraction_result = await extract_rab_from_file(file_bytes, mime_type)
        
        # Gabungkan item baru ini dengan item RAB yang mungkin sudah ada di state sebelumnya
        existing_rab = state.get("rab_items", [])
        extracted_items = extraction_result.get("items", [])
        merged_rab = existing_rab + extracted_items

        logger.info(f"[VISION] Ekstraksi sukses. Mendapatkan {len(extracted_items)} item baru.")

        # Kembalikan data RAB yang sudah diperbarui
        # Reset state file agar tidak diproses ulang di putaran (loop) berikutnya
        return {
            "rab_items": merged_rab,
            "uploaded_file_bytes": None,
            "uploaded_file_mime_type": None
        }

    except Exception as e:
        logger.error(f"[VISION] Gagal memproses file via service: {str(e)}")
        # Kosongkan penampung file agar tidak menyebabkan infinite loop pada LangGraph jika error
        return {
            "uploaded_file_bytes": None,
            "uploaded_file_mime_type": None
        }