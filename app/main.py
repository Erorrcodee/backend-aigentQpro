
from app.api.v1.routers import auth, admin, b2b, products, invoices
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.websockets.negotiation import ws_router
from app.core.config import settings
from app.core.scheduler import setup_scheduler, shutdown_scheduler

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

# 1. Daftarkan URL Frontend yang diizinkan (Spesifik agar kredensial bisa dikirim)
origins = [
    "http://localhost:3000",       # Port standar Create React App / Next.js
    "http://127.0.0.1:3000",
    "http://localhost:5173",       # Port standar Vite React
    "http://127.0.0.1:5173",
    
    
]

# 2. Terapkan Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,         # Memanggil daftar 'origins' di atas
    allow_credentials=True,        # Wajib True agar bisa menerima JWT Token / Cookies dari FE
    allow_methods=["*"],           # Mengizinkan GET, POST, PUT, DELETE
    allow_headers=["*"],           # Mengizinkan semua header, termasuk Authorization
)

@app.on_event("startup")
async def startup_event():
    """Tugas eksekusi otomatis saat peladen FastAPI mulai berjalan."""
    await setup_scheduler(app)

@app.on_event("shutdown")
async def shutdown_event():
    """Tugas eksekusi otomatis saat peladen FastAPI dihentikan."""
    await shutdown_scheduler()

@app.get("/")
async def root_health_check():
    return {
        "status": "online",
        "system": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "message": "Welcome to QHome AI Backend! Server is running smoothly. 🚀"
    }

# Tempat me-register router API nanti
# --- DAFTAR ROUTER (Rute API) ---
# Memasang /api/v1/auth
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["Authentication"])
app.include_router(admin.router, prefix=f"{settings.API_V1_STR}/admin", tags=["Admin Control Panel"])
app.include_router(b2b.router, prefix=f"{settings.API_V1_STR}/b2b", tags=["B2B Contractor Panel"])
app.include_router(products.router, prefix=f"{settings.API_V1_STR}/products", tags=["Product Catalog Management"])
app.include_router(invoices.router, prefix=f"{settings.API_V1_STR}/invoices", tags=["Invoice Management"])
app.include_router(ws_router)