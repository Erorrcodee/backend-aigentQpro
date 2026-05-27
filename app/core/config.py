# app/core/config.py

# pyrefly: ignore [missing-import]
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Variabel Umum (Boleh ada default)
    PROJECT_NAME: str = "QHome AI Intelligence System"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Infrastruktur (WAJIB diisi di .env, tidak ada nilai default)
    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379/0" # Pengecualian: Redis lokal biasa standar
    
    # Kunci API Agen (WAJIB diisi di .env)
    GEMINI_API_KEY: str 
    QWEN_API_KEY: str
    GROQ_API_KEY: str
    
    # Integrasi Cloudinary (WAJIB diisi di .env)
    CLOUDINARY_CLOUD_NAME: str
    CLOUDINARY_API_KEY: str
    CLOUDINARY_API_SECRET: str

    # Keamanan (WAJIB diisi di .env)
    JWT_SECRET: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    
    # Konfigurasi Pydantic untuk membaca dari file .env
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

# Instansiasi wajib
settings = Settings()