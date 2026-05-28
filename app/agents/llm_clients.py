from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from app.core.config import settings

# ==========================================
# 1. KLIEN GROQ (CADANGAN GRATIS)
# ==========================================
groq_chat_llm = ChatGroq(
    model="llama-3.1-8b-instant", 
    api_key=settings.GROQ_API_KEY,
    temperature=0.4,
    streaming=True
)

groq_logical_llm = ChatGroq(
    model="llama-3.1-8b-instant",
    api_key=settings.GROQ_API_KEY,
    temperature=0.2
)

# ==========================================
# 2. KLIEN SUMOPOD (UTAMA / BERBAYAR)
# ==========================================

# OPSI A: Menggunakan Gemini 2.5 Flash via SumoPod
# Kecepatan tinggi, jendela konteks sangat besar (cocok untuk baca RAB panjang)
sumopod_chat_llm = ChatOpenAI(
    base_url="https://ai.sumopod.com/v1",
    api_key=settings.SUMOPOD_API_KEY,
    model="gemini/gemini-2.5-flash", 
    temperature=0.4,
    streaming=True
)

# OPSI B: Menggunakan GPT-4o-Mini via SumoPod
# Sangat presisi untuk output terstruktur (JSON/Pydantic) di Gateway Node
sumopod_logical_llm = ChatOpenAI(
    base_url="https://ai.sumopod.com/v1",
    api_key=settings.SUMOPOD_API_KEY,
    model="gpt-4o-mini",
    temperature=0.0 
)