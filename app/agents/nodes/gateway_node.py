import logging
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field
from app.agents.state import B2BNegotiationState
from app.agents.llm_clients import sumopod_logical_llm

logger = logging.getLogger(__name__)

# 1. PERKUAT STRUKTUR OUTPUT (Mendeteksi Niat & Ekstrak Barang)
class IntentCheck(BaseModel):
    is_off_topic: bool = Field(description="True jika obrolan sama sekali di luar konteks B2B, konstruksi, atau material.")
    intent_category: str = Field(description="Pilih salah satu: 'tanya_barang', 'negosiasi_diskon', 'deal_setuju', 'salam_umum'")
    extracted_discount: float = Field(description="Jika user secara spesifik menyebut angka/persen diskon, tulis angkanya. Jika tidak, WAJIB isi 0.0")
    mentioned_products: list[str] = Field(description="WAJIB DIISI! Ekstrak nama barang atau merek yang diketik user. Contoh: ['semen gresik', 'keramik KIA']. Jika tidak ada, isi list kosong [].")
    reason: str

# Gunakan klien logis dengan struktur baru (GPT-4o-Mini via SumoPod)
gateway_agent = sumopod_logical_llm.with_structured_output(IntentCheck)

async def execute_gateway_node(state: B2BNegotiationState) -> dict:
    logger.info("[NODE] Memasuki Gateway Node (Intent, Routing & Extraction)...")
    
    messages = state.get("messages", [])
    if not messages:
        return {"is_off_topic": False, "mentioned_products": []}
        
    latest_message = messages[-1].content

    # Bangun konteks percakapan singkat
    history_messages = messages[:-1][-3:]
    conversation_context = ""
    if history_messages:
        lines = []
        for msg in history_messages:
            role = "AI" if msg.__class__.__name__ == "AIMessage" else "User"
            lines.append(f"[{role}]: {str(msg.content)[:100]}")
        conversation_context = "Riwayat singkat:\n" + "\n".join(lines) + "\n\n"

    prompt_instruction = f"""
    Kamu adalah Manajer Analisis Niat (Intent) untuk sistem B2B QHome.
    Tugasmu adalah menganalisis pesan terbaru dari pengguna dan mengekstrak parameternya.

    {conversation_context}Pesan terbaru user: "{latest_message}"

    ATURAN KLASIFIKASI:
    1. Tentukan `intent_category`:
       - 'tanya_barang': Jika user bertanya ketersediaan, stok, jenis semen, besi, atau spesifikasi.
       - 'negosiasi_diskon': Jika user eksplisit meminta potongan harga.
       - 'deal_setuju': Jika user sepakat.
       - 'salam_umum': Jika sekadar sapaan.
    2. Tentukan `extracted_discount`:
       - Jika user TIDAK menyebut angka diskon, pastikan nilainya 0.0.
    3. Tentukan `mentioned_products`:
       - WAJIB ekstrak nama barang/merek ke dalam list ini. Jika user menyebut "semen gresik", masukkan ["semen gresik"]. Ini sangat penting untuk pencarian database!
    4. `is_off_topic`:
       - Hanya bernilai True jika murni membahas di luar konstruksi/material.
    """

    try:
        result = await gateway_agent.ainvoke(prompt_instruction)
        logger.info(f"[GATEWAY] Kategori: {result.intent_category} | Diskon: {result.extracted_discount}% | Barang: {result.mentioned_products}")
        
        # Jika benar-benar ngawur (di luar topik)
        if result.is_off_topic:
            reject_msg = AIMessage(content="Maaf, saya hanya dapat membantu urusan pengadaan material bangunan dan negosiasi RAB B2B. Ada yang bisa saya bantu terkait proyek Anda?")
            return {"is_off_topic": True, "messages": [reject_msg]}
            
        # PEMBARUAN STATE YANG KRUSIAL
        return {
            "is_off_topic": False,
            "requested_discount": result.extracted_discount,
            "mentioned_products": result.mentioned_products
        }

    except Exception as e:
        logger.error(f"[GATEWAY] Error klasifikasi: {str(e)}. Default: loloskan pesan.")
        # Jika gagal, pastikan state tidak rusak dengan memberikan nilai default
        return {
            "is_off_topic": False, 
            "requested_discount": 0.0,
            "mentioned_products": []
        }