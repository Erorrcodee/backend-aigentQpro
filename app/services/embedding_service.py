# app/services/embedding_service.py
import logging
# pyrefly: ignore [missing-import]
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.core.config import settings

logger = logging.getLogger(__name__)

# Migrasi ke model embedding generasi terbaru dari Google yang aktif saat ini
embedding_model = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-2", # <--- UPDATE KE MODEL GENERASI KEDUA
    google_api_key=settings.GEMINI_API_KEY
)

async def generate_product_vector(text_content: str) -> list[float]:
    """
    Fungsi untuk mengubah deskripsi produk menjadi Vektor Angka.
    Menggunakan pemotongan [:768] untuk memastikan kompatibilitas batas dimensi dengan kolom pgvector di database Anda.
    """
    try:
        # LangChain Google GenAI aembed_query
        vector = await embedding_model.aembed_query(text_content)
        return vector[:768]
    except Exception as e:
        logger.error(f"Gagal generate Vector dari Google Gemini: {str(e)}")
        raise e