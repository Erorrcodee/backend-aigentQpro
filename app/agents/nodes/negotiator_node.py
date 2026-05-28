# app/agents/nodes/negotiator_node.py
"""
Node Senior Sales Consultant B2B: Merangkai jawaban berdasarkan FAKTA KATALOG,
menangani edukasi produk, serta menentukan deal negosiasi.
"""
from app.agents.llm_clients import sumopod_chat_llm
import logging
from langchain_core.messages import SystemMessage
from app.agents.state import B2BNegotiationState
from app.agents.llm_clients import groq_chat_llm

logger = logging.getLogger(__name__)

async def execute_negotiator_node(state: B2BNegotiationState) -> dict:
    """
    Node pamungkas untuk merangkai jawaban negosiasi ke pengguna tanpa halusinasi.
    """
    logger.info("[NODE] Memasuki Negotiator Node...")

    # 1. Tarik parameter diskon
    requested_discount = state.get("requested_discount", 0.0)
    max_allowed = state.get("maut_allowed_discount", 0.0)
    
    # 2. Tarik FAKTA MUTLAK dari Pricing Node (Anti-Halusinasi)
    catalog_facts = state.get("product_catalog_facts", "Belum ada data barang yang divalidasi.")
    directives = state.get("negotiation_directives", "")
    cross_sells = state.get("mba_cross_sell_opportunities", [])

    # --- Logika Deal Deterministik ---
    # Hanya anggap deal tercapai jika user BENAR-BENAR meminta diskon (> 0.0)
    # dan angka tersebut masuk akal (<= max_allowed).
    is_negotiating = requested_discount > 0.0
    deal_reached = False
    final_discount = 0.0

    if is_negotiating:
        deal_reached = requested_discount <= max_allowed
        final_discount = requested_discount if deal_reached else 0.0

    # --- Format instruksi MBA untuk cross-sell ---
    mba_text = ""
    if cross_sells:
        mba_text = "\n[PELUANG CROSS-SELL - TAWARKAN DENGAN NATURAL]\n"
        for opp in cross_sells:
            trigger = opp.get('trigger_found_in_rab', '')
            sku = opp.get('suggested_product', {}).get('name', '')
            harga = opp.get('suggested_product', {}).get('price', 0)
            mba_text += f"- Karena ada '{trigger}', rekomendasikan '{sku}' (Rp {harga}) sebagai pelengkap.\n"

    # --- Susun Konteks Percakapan (Fase Konsultasi vs Fase Tawar-Menawar) ---
    if not is_negotiating:
        deal_context = (
            "FASE SAAT INI: KONSULTASI & EDUKASI.\n"
            "Klien belum meminta diskon spesifik. FOKUSLAH menjawab pertanyaan klien, "
            "memberikan informasi ketersediaan barang, spesifikasi teknis, atau menjelaskan rincian RAB. "
            "Jangan membahas persetujuan/penolakan diskon secara prematur."
        )
    elif deal_reached:
        deal_context = (
            f"FASE SAAT INI: PENUTUPAN DEAL.\n"
            f"Permintaan diskon klien sebesar {requested_discount}% DISETUJUI. "
            f"Sampaikan persetujuan ini dengan hangat, elegan, dan profesional. "
            f"Informasikan bahwa sistem sedang menyiapkan dokumen invoice."
        )
    else:
        deal_context = (
            f"FASE SAAT INI: TAWAR-MENAWAR (COUNTER-OFFER).\n"
            f"Permintaan diskon {requested_discount}% DITOLAK karena melebihi otorisasi batas maksimal {max_allowed}%. "
            f"Tolak dengan sangat diplomatis agar klien tidak tersinggung. "
            f"Berikan penawaran balik (counter-offer) di angka maksimal {max_allowed}%."
        )

    # --- RAKIT SYSTEM PROMPT (ANTI-HALUSINASI) ---
    sys_msg = f"""Anda adalah Senior B2B Sales Consultant untuk QHome. 
Gaya bahasa Anda: Profesional, empatik, berbasis solusi, dan sangat akurat.

ATURAN ANTI-HALUSINASI (WAJIB DIPATUHI - PELANGGARAN BERAKIBAT FATAL):
1. JANGAN PERNAH mengarang nama barang, spesifikasi, kuantitas, atau harga.
2. JANGAN PERNAH berasumsi. HANYA gunakan informasi yang tercantum dalam [SUMBER KEBENARAN KATALOG] di bawah ini.
3. Jika informasi yang ditanyakan tidak ada di [SUMBER KEBENARAN KATALOG], Anda WAJIB menjawab dengan sopan bahwa Anda perlu mengecek database atau informasi tersebut belum tersedia.
4. DILARANG KERAS membagikan metrik internal (seperti algoritma MAUT, batas maksimal diskon sistem secara eksplisit sebelum menawar, atau istilah teknis AI).

[SUMBER KEBENARAN KATALOG - FAKTA DATABASE]
{catalog_facts}

[ARAHAN STRATEGI NEGOSIASI INTERNAL]
{directives}

{deal_context}
{mba_text}
"""

    # Sisipkan instruksi sistem di urutan paling awal, diikuti riwayat obrolan user
    messages_to_send = [SystemMessage(content=sys_msg)] + state["messages"]

    # Eksekusi pemanggilan ke LLM
    response = await sumopod_chat_llm.ainvoke(messages_to_send)

    logger.info(f"[NEGOTIATOR] Selesai. Deal Reached: {deal_reached}")

    return {
        "messages": [response],
        "is_deal_reached": deal_reached,
        "final_agreed_discount": final_discount,
    }