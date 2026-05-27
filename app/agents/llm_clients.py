# pyrefly: ignore [missing-import]
from langchain_groq import ChatGroq
from app.core.config import settings

# Klien Groq untuk Negotiator Node (Streaming super cepat, temperature 0.4)
groq_chat_llm = ChatGroq(
    model="llama-3.1-8b-instant", 
    api_key=settings.GROQ_API_KEY,
    temperature=0.4,
    streaming=True
)

# Klien Groq untuk Gateway Node (Suhu 0, output terstruktur/kaku)
groq_logical_llm = ChatGroq(
    model="llama-3.1-8b-instant",
    api_key=settings.GROQ_API_KEY,
    temperature=0.2
)