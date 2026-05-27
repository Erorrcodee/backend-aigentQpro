# app/agents/nodes/gateway_node.py
import logging
from langchain_core.messages import AIMessage
from pydantic import BaseModel
from app.agents.state import B2BNegotiationState
from app.agents.llm_clients import groq_logical_llm

logger = logging.getLogger(__name__)

class IntentCheck(BaseModel):
    is_off_topic: bool
    reason: str

# Langsung gunakan klien logis dari llm_clients dan pasang pengekstraksi struktur
gateway_agent = groq_logical_llm.with_structured_output(IntentCheck)

async def execute_gateway_node(state: B2BNegotiationState) -> dict:
    logger.info("[NODE] Memasuki Gateway Node (Groq)...")
    
    messages = state["messages"]
    latest_message = messages[-1].content

    # Bangun konteks percakapan: ambil maksimal 4 pesan terakhir (selain pesan terbaru)
    # agar gateway memahami bahwa ini adalah kelanjutan negosiasi yang sedang berjalan
    history_messages = messages[:-1][-4:]  # Maksimal 4 pesan sebelumnya
    conversation_context = ""
    if history_messages:
        lines = []
        for msg in history_messages:
            role = "AI" if msg.__class__.__name__ == "AIMessage" else "User"
            # Potong pesan panjang agar tidak membebani token
            content_preview = str(msg.content)[:200]
            lines.append(f"  [{role}]: {content_preview}")
        conversation_context = "Riwayat percakapan sebelumnya:\n" + "\n".join(lines) + "\n\n"

    prompt_instruction = f"""
    Kamu adalah penjaga topik percakapan sistem B2B pengadaan material bangunan QHome.

    {conversation_context}Pesan terbaru dari user: "{latest_message}"

    ATURAN PENILAIAN (baca dengan seksama):

    1. SELALU kembalikan is_off_topic=FALSE untuk:
       - Pesan yang membahas: material/bahan bangunan, proyek konstruksi, RAB, harga, diskon, negosiasi, pengadaan, kontrak, invoice, pengiriman, pembayaran.
       - Pesan perkenalan diri atau perusahaan dalam konteks bisnis (contoh: "Halo, saya Budi dari PT XYZ").
       - Pesan pendek yang merupakan KELANJUTAN NEGOSIASI seperti: "saya setuju", "ok", "deal", "oke", "lanjut", "baik", "ya", "tidak", "setuju saja", "oke saya terima", "boleh", atau ungkapan serupa APAPUN.
       - Jika ada riwayat percakapan negosiasi sebelumnya, SEMUA pesan lanjutan dianggap relevan.
       - Jika ragu, SELALU pilih is_off_topic=FALSE.

    2. HANYA kembalikan is_off_topic=TRUE jika pesan JELAS-JELAS membahas topik yang sama sekali tidak berkaitan seperti: hiburan, politik, gosip selebriti, resep masakan, olahraga, dll — DAN tidak ada riwayat percakapan negosiasi sebelumnya.

    PRINSIP UTAMA: Lebih baik meloloskan pesan yang sedikit ambigu daripada memblokir pesan yang valid.
    """

    try:
        result = await gateway_agent.ainvoke(prompt_instruction)
        logger.info(f"[GATEWAY] Hasil klasifikasi: is_off_topic={result.is_off_topic}, alasan: {result.reason}")
        
        if result.is_off_topic:
            reject_msg = AIMessage(content="Maaf, saya hanya dapat membantu urusan pengadaan material bangunan dan negosiasi RAB. Silakan hubungi kami untuk kebutuhan proyek konstruksi Anda.")
            return {"is_off_topic": True, "messages": [reject_msg]}
            
        return {"is_off_topic": False}

    except Exception as e:
        logger.error(f"[GATEWAY] Error klasifikasi: {str(e)}. Default: loloskan pesan.")
        # Jika LLM gagal, amankan dengan meloloskan pesan (fail-open)
        return {"is_off_topic": False}