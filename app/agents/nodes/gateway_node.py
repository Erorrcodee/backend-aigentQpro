import logging
import traceback
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field
from app.agents.state import B2BNegotiationState
from app.agents.llm_clients import sumopod_logical_llm

# Setup Logger khusus untuk modul Gateway
logger = logging.getLogger(__name__)

# 1. STRUKTUR OUTPUT (Mendeteksi Niat & Ekstrak Barang)
class IntentCheck(BaseModel):
    is_off_topic: bool = Field(description="True jika obrolan sama sekali di luar konteks B2B, konstruksi, atau material.")
    intent_category: str = Field(description="Pilih salah satu: 'tanya_barang', 'negosiasi_diskon', 'deal_setuju', 'salam_umum'")
    extracted_discount: float = Field(description="Jika user secara spesifik menyebut angka/persen diskon, tulis angkanya. Jika tidak, WAJIB isi 0.0")
    mentioned_products: list[str] = Field(description="WAJIB DIISI! Ekstrak nama barang atau merek yang diketik user. Contoh: ['semen gresik', 'keramik KIA']. Jika tidak ada, isi list kosong [].")
    reason: str = Field(description="Alasan singkat mengapa kamu mengambil kesimpulan klasifikasi tersebut.")

# Menggunakan GPT-4o-Mini via SumoPod sebagai mesin utama
gateway_agent = sumopod_logical_llm.with_structured_output(IntentCheck)

async def execute_gateway_node(state: B2BNegotiationState) -> dict:
    logger.info("==========================================================================")
    logger.info("🚀 [GATEWAY - START] Memulai Eksekusi Node Klasifikasi Niat & Ekstraksi")
    logger.info("==========================================================================")
    
    # 1. Ambil dan lacak pesan dari State LangGraph
    messages = state.get("messages", [])
    if not messages:
        logger.warning("🚨 [GATEWAY - WARNING] State 'messages' kosong! Tidak ada data untuk diproses.")
        return {"is_off_topic": False, "mentioned_products": []}
        
    latest_message = messages[-1].content
    logger.info(f"📥 [GATEWAY - INPUT] Pesan terbaru dari user: '{latest_message}'")

    # 2. Bangun dan lacak konteks percakapan singkat (3 pesan terakhir)
    history_messages = messages[:-1][-3:]
    conversation_context = ""
    logger.info(f"📊 [GATEWAY - HISTORY] Mengompilasi {len(history_messages)} pesan riwayat terakhir...")
    
    if history_messages:
        lines = []
        for idx, msg in enumerate(history_messages):
            role = "AI" if msg.__class__.__name__ == "AIMessage" else "User"
            lines.append(f"[{role}]: {str(msg.content)[:50]}...")
            logger.info(f"   ↳ Riwayat [{idx+1}] ({role}): '{str(msg.content)[:70]}'")
        conversation_context = "Riwayat singkat:\n" + "\n".join(lines) + "\n\n"

    # 3. Susun instruksi prompt
    prompt_instruction = f"""
    Kamu adalah Manajer Analisis Niat (Intent) untuk sistem B2B QHome.
    Tugasmu adalah menganalisis pesan terbaru dari pengguna dan mengekstrak parameternya dengan akurat.

    {conversation_context}Pesan terbaru user: "{latest_message}"

    ATURAN KLASIFIKASI & EKSTRAKSI WAJIB:
    1. Tentukan `intent_category`:
       - 'tanya_barang': Jika user bertanya ketersediaan, stok, jenis semen, besi, keramik, atau spesifikasi material.
       - 'negosiasi_diskon': Jika user secara eksplisit meminta potongan harga, menawar harga, atau menanyakan diskon.
       - 'deal_setuju': Jika user menyatakan sepakat, setuju, atau konfirmasi pemesanan (misal: "oke deal", "siapkan barangnya").
       - 'salam_umum': Jika sekadar sapaan pembuka atau penutup (misal: "halo", "selamat pagi", "terima kasih").
    
    2. Tentukan `extracted_discount`:
       - Jika user menyebut angka diskon (misal: "minta 5%"), isi dengan angka 5.0. Jika tidak ada, WAJIB isi 0.0.
    
    3. Tentukan `mentioned_products`:
       - Ekstrak seluruh nama produk, material, atau merek yang disebutkan dalam pesan terbaru.
       - Contoh jika user menginput "ada semen gresik 40kg", isi dengan ["semen gresik 40kg"].
       - Jika user HANYA menyatakan sepakat (misal: "oke", "deal", "setuju", "oke deal", "siap"), WAJIB isi dengan list kosong []. Jangan pernah memasukkan kata "deal", "oke", atau "setuju" sebagai nama produk!
    
    4. Tentukan `is_off_topic`:
       - Bernilai True HANYA jika pesan murni membahas hal di luar konstruksi, bangunan, atau material.
    
    5. Tentukan `reason`:
       - Tuliskan satu kalimat singkat yang mendasari keputusan klasifikasimu.
    """

    # 4. Panggil LLM dengan pelacakan performa dan luaran data
    try:
        logger.info("🧠 [GATEWAY - LLM_CALL] Mengirim prompt ke gpt-4o-mini via SumoPod...")
        result = await gateway_agent.ainvoke(prompt_instruction)
        
        logger.info("✨ [GATEWAY - LLM_RESPONSE] AI Berhasil mengembalikan data terstruktur:")
        logger.info(f"   📂 Kategori Niat  : '{result.intent_category}'")
        logger.info(f"   💰 Diskon Diperoleh: {result.extracted_discount}%")
        logger.info(f"   📦 Produk Diekstrak: {result.mentioned_products}")
        logger.info(f"   🚫 Di Luar Topik  : {result.is_off_topic}")
        logger.info(f"   💡 Alasan AI       : '{result.reason}'")
        
        # Evaluasi jika pesan di luar topik konstruksi
        if result.is_off_topic:
            logger.warning("⚠️ [GATEWAY - ROUTING] Pesan terdeteksi di luar topik konstruksi! Mengarahkan ke rute penolakan.")
            reject_msg = AIMessage(content="Maaf, saya hanya dapat membantu urusan pengadaan material bangunan dan negosiasi RAB B2B. Ada yang bisa saya bantu terkait proyek Anda?")
            
            logger.info("💾 [GATEWAY - END_STATE] Mengembalikan State Penolakan.")
            return {"is_off_topic": True, "messages": [reject_msg], "mentioned_products": []}
            
        return {
            "is_off_topic": False,
            "requested_discount": result.extracted_discount,
            "mentioned_products": result.mentioned_products
        }

    except Exception as e:
        # Menangkap error lengkap dengan lokasi baris kode yang rusak (stack trace)
        logger.error("💥 [GATEWAY - FATAL_ERROR] Terjadi kegagalan pemrosesan pada Pydantic atau API LLM!")
        logger.error(f"   Detail Pesan Kesalahan: {str(e)}")
        logger.error(f"   Detail Stack Trace:\n{traceback.format_exc()}")
        logger.warning("🛟 [GATEWAY - FALLBACK] Memicu Protokol Jaring Pengaman Darurat (Fallback)...")
        
        fallback_products = []
        words_count = len(latest_message.split())
        logger.info(f"   📝 Panjang kata pesan user: {words_count} kata.")
        
        # Evaluasi pesan teks sebagai kueri darurat jika kalimat pendek
        if 0 < words_count <= 10:
            fallback_products.append(latest_message)
            logger.info(f"   📌 Teks di bawah 10 kata. Kalimat utuh dimasukkan ke target kueri: {fallback_products}")
        else:
            logger.warning("   📌 Teks terlalu panjang untuk fallback otomatis. Mengosongkan variabel produk.")
            
        logger.info(f"💾 [GATEWAY - END_STATE] Mengembalikan State Fallback Darurat: {{'mentioned_products': {fallback_products}}}")
        return {
            "is_off_topic": False, 
            "requested_discount": 0.0,
            "mentioned_products": fallback_products
        }