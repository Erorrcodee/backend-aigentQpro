# app/agents/nodes/invoice_node.py
"""
Node LangGraph untuk fitur Deal Lock & Invoice.
Berperan sebagai Controller Alur: memanggil invoice_service,
lalu memformat respons AI dan memperbarui state graf.
Node ini TIDAK mengandung logika bisnis — semua delegasi ke lapisan layanan.
"""
import logging
from langchain_core.messages import AIMessage
from app.agents.state import B2BNegotiationState
from app.services.invoice_service import process_new_deal

logger = logging.getLogger(__name__)


async def execute_invoice_node(state: B2BNegotiationState) -> dict:
    """
    Node pamungkas yang dieksekusi saat negosiasi mencapai kesepakatan (is_deal_reached=True).

    Alur kerja node ini:
      1. Membaca data yang dibutuhkan dari state (rab_items, final_agreed_discount).
      2. Mendelegasikan seluruh pemrosesan ke `invoice_service.process_new_deal()`.
      3. Merakit pesan balasan formal dari AI berisi tautan unduhan invoice.
      4. Mengembalikan pembaruan state tanpa mengubah field yang sudah ada sebelumnya.

    Returns:
        dict pembaruan state: is_deal_reached, invoice_data, dan messages (AIMessage).
    """
    logger.info("[NODE] Memasuki Invoice Node — memproses penguncian transaksi...")

    rab_items = state.get("rab_items", [])
    final_discount = state.get("final_agreed_discount", state.get("maut_allowed_discount", 0.0))

    try:
        # Delegasikan seluruh logika bisnis ke lapisan layanan
        result = await process_new_deal(
            rab_items=rab_items,
            final_discount=final_discount,
        )

        invoice_number = result.get("invoice_number", "N/A")
        download_url = result.get("download_url", "#")

        logger.info(f"[NODE] Invoice '{invoice_number}' berhasil diterbitkan. URL: {download_url}")

        # Rakit pesan ucapan terima kasih yang formal dan informatif
        thank_you_message = AIMessage(
            content=(
                f"Terima kasih atas kepercayaan Anda kepada QHome. "
                f"Transaksi negosiasi telah resmi dikunci dan terdokumentasi.\n\n"
                f"**Nomor Invoice:** `{invoice_number}`\n"
                f"**Diskon yang Disepakati:** {final_discount:.2f}%\n\n"
                f"Dokumen invoice dalam format PDF telah disiapkan dan dapat diunduh "
                f"melalui tautan berikut:\n"
                f"[Unduh Invoice {invoice_number}]({download_url})\n\n"
                f"Dokumen ini merupakan bukti kesepakatan yang sah. "
                f"Silakan simpan sebagai arsip resmi perusahaan Anda. "
                f"Tim QHome akan menghubungi Anda untuk proses pengiriman material."
            )
        )

        return {
            "is_deal_reached": True,
            "invoice_data": result,
            "messages": [thank_you_message],
        }

    except Exception as e:
        logger.error(f"[NODE] Gagal menerbitkan invoice: {str(e)}")

        # Kirim pesan kegagalan yang informatif tanpa mengekspos detail teknis
        error_message = AIMessage(
            content=(
                "Permohonan maaf kami sampaikan. Terjadi kendala teknis saat menerbitkan "
                "dokumen invoice Anda. Tim teknis kami telah menerima notifikasi dan akan "
                "segera menindaklanjuti. Silakan hubungi tim QHome untuk bantuan lebih lanjut."
            )
        )

        return {
            "is_deal_reached": False,
            "invoice_data": {"status": "error", "error": str(e)},
            "messages": [error_message],
        }
