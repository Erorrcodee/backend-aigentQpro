# app/services/vision_agent.py
import json
import logging
import asyncio
import fitz
from google import genai
from app.core.config import settings
from app.schemas.rab_schema import RABExtractionResult

logger = logging.getLogger(__name__)

client = genai.Client(api_key=settings.GEMINI_API_KEY)

# LAMPU LALU LINTAS: Maksimal 2 request ke Google berjalan bersamaan
# Ini sangat krusial untuk menghindari Error 429 (Rate Limit) pada tier gratis
semaphore = asyncio.Semaphore(2)

async def process_single_page(img_bytes: bytes, page_num: int) -> dict:
    """Fungsi pekerja: Memproses 1 halaman gambar ke Gemini dengan aman"""
    async with semaphore:
        prompt = """
        Ekstrak daftar barang, kuantitas, harga, dan indikasi mark-up (is_suspicious) dari halaman dokumen RAB ini.
        Fokus pada item material. Abaikan teks yang tidak relevan.
        """
        try:
            response = await client.aio.models.generate_content(
                model='gemini-2.5-flash',
                contents=[
                    prompt,
                    genai.types.Part.from_bytes(data=img_bytes, mime_type="image/png")
                ],
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=RABExtractionResult,
                    temperature=0.0  # Wajib 0 agar tidak halusinasi format
                )
            )
            
            # Beri jeda napas 4 detik setelah selesai agar Google tidak memblokir kita
            await asyncio.sleep(4)
            
            return json.loads(response.text)
        except Exception as e:
            logger.error(f"Gagal ekstrak halaman {page_num}: {str(e)}")
            # Jika 1 halaman gagal (mungkin blur/kosong), kembalikan kosong agar yang lain tetap jalan
            return {"items": []}

async def extract_rab_from_file(file_bytes: bytes, mime_type: str) -> dict:
    """Fungsi Utama: Membedah file, memecah PDF (jika ada), dan menjahit hasilnya"""
    
    page_images = []
    
    # 1. TAHAP PEMOTONGAN (CHUNKING)
    if mime_type == "application/pdf":
        try:
            # Buka PDF dari memori (bytes) menggunakan PyMuPDF
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                # Render halaman menjadi gambar PNG dengan resolusi sedang (DPI 150 cukup untuk AI)
                pix = page.get_pixmap(dpi=150)
                page_images.append(pix.tobytes("png"))
            doc.close()
            logger.info(f"PDF berhasil dipecah menjadi {len(page_images)} halaman.")
        except Exception as e:
            raise Exception(f"Gagal memecah PDF: {str(e)}")
    else:
        # Jika user mengunggah langsung gambar (JPG/PNG), anggap sebagai 1 halaman
        page_images.append(file_bytes)

    # 2. TAHAP PEMROSESAN PARALEL AMAN (MAP)
    tasks = []
    for i, img_data in enumerate(page_images):
        tasks.append(process_single_page(img_data, i + 1))
    
    # Tunggu semua halaman selesai diekstrak oleh AI
    logger.info(f"Memulai ekstraksi {len(tasks)} halaman ke Gemini...")
    results = await asyncio.gather(*tasks)

    # 3. TAHAP PENJAHITAN HASIL (REDUCE)
    all_items = []
    project_name = "Tidak Diketahui"
    contractor_name = "Tidak Diketahui"

    for res in results:
        # Gabungkan semua item dari tiap halaman
        if res.get("items"):
            all_items.extend(res["items"])
        
        # Ambil nama proyek/kontraktor dari halaman mana saja yang terdeteksi
        if res.get("project_name") and project_name == "Tidak Diketahui":
            project_name = res["project_name"]
        if res.get("contractor_name") and contractor_name == "Tidak Diketahui":
            contractor_name = res["contractor_name"]

    # Hitung ulang total budget berdasarkan item yang berhasil diekstrak
    total_budget = sum(item.get("total_price", 0) for item in all_items)
    
    # Buat ringkasan cerdas (Fraud Analysis)
    suspicious_items = [item.get("item_name") for item in all_items if item.get("is_suspicious")]
    if suspicious_items:
        summary = f"Peringatan: Ditemukan {len(suspicious_items)} item yang terindikasi Mark-up harga (seperti: {', '.join(suspicious_items[:3])}). Harap tinjau ulang."
    else:
        summary = "Aman. Semua harga item pada dokumen ini terindikasi berada di batas wajar."

    # 4. BUNGKUS DENGAN PYDANTIC FINAL
    final_data = {
        "project_name": project_name,
        "contractor_name": contractor_name,
        "items": all_items,
        "total_budget": total_budget,
        "fraud_analysis_summary": summary
    }
    
    # Loloskan ke Pydantic untuk garansi struktur 100% aman
    validated_data = RABExtractionResult(**final_data)
    return validated_data.model_dump()