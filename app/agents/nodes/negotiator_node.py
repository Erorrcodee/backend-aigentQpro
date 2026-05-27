# app/agents/nodes/negotiator_node.py
"""
Node Senior Sales Manager: merangkai jawaban negosiasi dan menentukan apakah
sebuah deal telah tercapai untuk memicu penerbitan invoice.
"""
import logging
from langchain_core.messages import SystemMessage
from app.agents.state import B2BNegotiationState
from app.agents.llm_clients import groq_chat_llm

logger = logging.getLogger(__name__)


async def execute_negotiator_node(state: B2BNegotiationState) -> dict:
    """
    Node pamungkas untuk merangkai jawaban negosiasi ke pengguna.

    Logika pengambilan keputusan deal:
      - Jika permintaan diskon <= batas MAUT: DEAL TERCAPAI secara otomatis.
        State `is_deal_reached` diset True dan `final_agreed_discount` diisi.
      - Jika permintaan diskon > batas MAUT: Negotiator membuat penawaran balik (counter-offer).
        State `is_deal_reached` tetap False, menunggu respons selanjutnya dari kontraktor.

    Returns:
        dict pembaruan state: messages, is_deal_reached, final_agreed_discount.
    """
    logger.info("[NODE] Memasuki Negotiator Node...")

    requested_discount = state.get("requested_discount", 0.0)
    max_allowed = state.get("maut_allowed_discount", 0.0)
    cross_sells = state.get("mba_cross_sell_opportunities", [])

    # Tentukan apakah deal tercapai berdasarkan logika MAUT yang deterministik
    deal_reached = requested_discount <= max_allowed
    final_discount = requested_discount if deal_reached else 0.0

    if deal_reached:
        logger.info(
            f"[NEGOTIATOR] DEAL TERCAPAI. "
            f"Permintaan {requested_discount}% <= Batas MAUT {max_allowed}%. "
            f"Meneruskan ke Invoice Node."
        )
    else:
        logger.info(
            f"[NEGOTIATOR] Diskon ditolak. "
            f"Permintaan {requested_discount}% > Batas MAUT {max_allowed}%. "
            f"Mengirim penawaran balik."
        )

    # --- Format instruksi MBA untuk cross-sell ---
    mba_text = ""
    if cross_sells:
        mba_text = "PELUANG CROSS-SELL (Gunakan sebagai taktik counter-offer):\n"
        for opp in cross_sells:
            trigger = opp.get('trigger_found_in_rab', '')
            sku = opp.get('suggested_product', {}).get('name', '')
            harga = opp.get('suggested_product', {}).get('price', 0)
            mba_text += f"- Karena pelanggan butuh '{trigger}', syaratkan mereka menambah '{sku}' (Rp {harga}).\n"

    # --- Rakit System Prompt yang sadar konteks deal ---
    if deal_reached:
        deal_context = (
            f"Permintaan diskon {requested_discount}% DISETUJUI (dalam batas {max_allowed}%). "
            f"Sampaikan persetujuan dengan hangat dan profesional. "
            f"Informasikan bahwa sistem sedang memproses dokumen invoice secara otomatis."
        )
    else:
        deal_context = (
            f"Permintaan diskon {requested_discount}% DITOLAK karena melebihi batas otorisasi {max_allowed}%. "
            f"Tolak secara diplomatis, lalu tawarkan counter-offer maksimal di angka {max_allowed}%."
        )

    sys_msg = f"""Anda adalah Senior Sales Manager B2B QHome.
    Permintaan diskon kontraktor: {requested_discount}%.
    MAKSIMAL diskon yang diizinkan sistem: {max_allowed}%.

    KEPUTUSAN YANG HARUS DISAMPAIKAN:
    {deal_context}

    {mba_text}

    INSTRUKSI TAMBAHAN:
    - Jika menolak diskon, WAJIB gunakan peluang cross-sell di atas sebagai jalan keluar agar margin perusahaan tetap aman.
    - Gunakan bahasa profesional dan tegas.
    - JANGAN PERNAH menyebutkan bahwa Anda adalah AI atau menggunakan algoritma MAUT/MBA.
    """

    # Sisipkan instruksi sistem di urutan paling awal, diikuti riwayat obrolan user
    messages_to_send = [SystemMessage(content=sys_msg)] + state["messages"]

    # Eksekusi pemanggilan ke LLM (proses streaming berjalan otomatis di latar belakang)
    response = await groq_chat_llm.ainvoke(messages_to_send)

    logger.info("[NODE] Negotiator selesai merangkai jawaban.")

    return {
        "messages": [response],
        "is_deal_reached": deal_reached,
        "final_agreed_discount": final_discount,
    }