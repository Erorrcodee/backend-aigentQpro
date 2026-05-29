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
    reason: str = Field(description="Alasan singkat mengapa kamu mengambil kesimpulan klasifikasi tersebut.")

# Menggunakan GPT-4o-Mini via SumoPod sebagai mesin utama
gateway_agent = sumopod_logical_llm.with_structured_output(IntentCheck)

async def execute_gateway_node(state: B2BNegotiationState) -> dict:
    logger.info("[NODE] Memasuki Gateway Node (Intent, Routing & Extraction)...")
    
    messages = state.get("messages", [])
    if not messages:
        return {"is_off_topic": False, "mentioned_products": []}
        
    latest_message = messages[-1].content

    # Bangun konteks percakapan singkat (3 pesan terakhir)
    history_messages = messages[:-1][-3:]
    conversation_context = ""
    if history_messages:
        lines = []
        for msg in history_messages:
            role = "AI" if msg.__class__.__name__ == "AIMessage" else "User"
            lines.append(f"[{role}]: {str(msg.content)[:100]}")
        conversation_context = "Riwayat singkat:\n" + "\n".join(lines) + "\n\n"

    # PERBAIKAN PROMPT: Instruksi dibuat jauh lebih tegas dan mencakup semua kolom Pydantic
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
       - Jika tidak ada produk yang disebutkan, isi dengan list kosong [].
    
    4. Tentukan `is_off_topic`:
       - Bernilai True HANYA jika pesan murni membahas hal di luar konstruksi, bangunan, atau material (misal: resep makanan, gosip, politik).
    
    5. Tentukan `reason`:
       - Tuliskan satu kalimat singkat yang mendasari keputusan klasifikasimu.
    """

    try:
        result = await gateway_agent.ainvoke(prompt_instruction)
        logger.info(f"[GATEWAY] Kategori: {result.intent_category} | Diskon: {result.extracted_discount}% | Barang: {result.mentioned_products}")
        
        # Jika obrolan melenceng jauh dari topik bisnis
        if result.is_off_topic:
            reject_msg = AIMessage(content="Maaf, saya hanya dapat membantu urusan pengadaan material bangunan dan negosiasi RAB B2B. Ada yang bisa saya bantu terkait proyek Anda?")
            return {"is_off_topic": True, "messages": [reject_msg], "mentioned_products": []}
            
        return {
            "is_off_topic": False,
            "requested_discount": result.extracted_discount,
            "mentioned_products": result.mentioned_products
        }

    except Exception as e:
        logger.error(f"[GATEWAY] Gagal klasifikasi otomatis: {str(e)}. Mengaktifkan Lapis Pertahanan Darurat!")
        
        # JARING PENGAMAN (FALLBACK REDUNDANCY):
        # Jika AI mengalami kegagalan sistematis, kita potong pesan teks user menjadi kueri mentah.
        # Strategi ini menjaga agar Node Pricing di tahap berikutnya tetap menerima data untuk mencari ke DB.
        fallback_products = []
        words_count = len(latest_message.split())
        
        # Jika input pendek (di bawah 10 kata), asumsikan teks tersebut berisi nama barang yang dicari
        if 0 < words_count <= 10:
            fallback_products.append(latest_message)
            
        return {
            "is_off_topic": False, 
            "requested_discount": 0.0,
            "mentioned_products": fallback_products
        }