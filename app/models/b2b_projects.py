# app/models/b2b_projects.py
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime
import enum
from app.models.base import Base

class ProjectStatus(str, enum.Enum):
    PENDING_ANALYSIS = "PENDING_ANALYSIS" # Sedang dibaca AI
    NEGOTIATING = "NEGOTIATING"           # Sedang tawar-menawar
    WAITING_APPROVAL = "WAITING_APPROVAL" # Menunggu klik Admin (HITL)
    APPROVED = "APPROVED"                 # Deal & Siap bayar
    REJECTED = "REJECTED"                 # Ditolak Admin / Sistem
    FLAGGED_FRAUD = "FLAGGED_FRAUD"       # AI mendeteksi dokumen aneh

class B2BProject(Base):
    __tablename__ = "b2b_projects"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    project_name = Column(String(255), nullable=False) # Contoh: "Proyek RSUD Sayang Ibu"
    document_url = Column(String(500), nullable=True)  # Link PDF/Excel yang diunggah
    
    # Total anggaran yang dihitung (Deterministik, bukan karangan AI)
    total_budget_initial = Column(Float, nullable=False, default=0.0) # Harga awal
    total_budget_final = Column(Float, nullable=True)                 # Harga setelah nego
    
    # Diskon yang dikunci oleh SPK MAUT untuk proyek ini
    maut_max_discount_allowed = Column(Float, nullable=True)
    
    # Isi RAB yang diekstrak (Disimpan dalam JSON agar fleksibel)
    # Format: [{"sku": "...", "qty": 10, "unit_price": 50000}, ...]
    extracted_items = Column(JSONB, nullable=True)
    
    status = Column(Enum(ProjectStatus), default=ProjectStatus.PENDING_ANALYSIS, nullable=False)
    
    # Untuk fitur Fraud Detection
    fraud_reason = Column(String(500), nullable=True) # Contoh: "Harga Semen di PDF diubah jadi Rp1.000"
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())