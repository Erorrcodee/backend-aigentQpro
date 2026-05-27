# app/core/database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings

# 1. Membuat Mesin Database Asynchronous
# pool_pre_ping=True: Sangat penting untuk Neon Tech agar mengecek koneksi mati sebelum mengeksekusi query.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,              # Ubah ke True jika ingin melihat log SQL query di terminal saat debugging
    future=True,
    pool_pre_ping=True,      # Mencegah error "connection dropped" dari Neon Tech
    pool_size=10,            # Jumlah koneksi serentak (sesuaikan dengan batas Neon)
    max_overflow=20          # Cadangan koneksi jika traffic sedang padat
)

# 2. Membuat Pabrik Sesi (Session Factory)
# Ini yang akan memproduksi sesi ke database setiap kali user/agen menge-hit endpoint API
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Mencegah error detached instance setelah commit
    autoflush=False
)

# 3. Dependency Injection (Digunakan oleh Endpoint API)
# Fungsi ini akan menyuntikkan (inject) sesi database ke setiap fungsi yang membutuhkannya,
# lalu otomatis menutupnya (close) setelah selesai agar tidak membebani memori Neon Tech.
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()