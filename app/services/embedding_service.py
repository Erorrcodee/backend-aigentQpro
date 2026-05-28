# app/services/embedding_service.py
import logging
# pyrefly: ignore [missing-import]
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.core.config import settings

logger = logging.getLogger(__name__)

# Inisialisasi model LLM pengubah Teks -> Vektor Angka milik Google
# text-embedding-004 adalah model gratis terbaru dari Google (Output: 768 Dimensi)
embedding_model = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-004",
    
    google_api_key=settings.GEMINI_API_KEY
)

async def generate_product_vector(text_content: str) -> list[float]:
    """
    Fungsi untuk mengubah deskripsi produk menjadi 768 dimensi Vektor Angka.
    """
    try:
        # LangChain Google GenAI aembed_query
        vector = await embedding_model.aembed_query(text_content)
        return vector[:768]
    except Exception as e:
        logger.error(f"Gagal generate Vector dari Google Gemini: {str(e)}")
        raise e