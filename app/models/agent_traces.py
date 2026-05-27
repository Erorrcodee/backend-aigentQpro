# app/models/agent_traces.py
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime
from app.models.base import Base

class AgentTrace(Base):
    __tablename__ = "agent_traces"

    id = Column(Integer, primary_key=True, index=True)
    
    # Melacak proses ini milik obrolan/proyek siapa
    project_id = Column(Integer, ForeignKey("b2b_projects.id"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    
    # Siapa yang berpikir? (Contoh: "VisionAgent", "PricingAgent", "NegotiatorAgent")
    agent_name = Column(String(100), nullable=False)
    
    # Apa tugasnya? (Contoh: "Extracting_PDF", "Calculating_MAUT")
    action_type = Column(String(100), nullable=False)
    
    # Menyimpan isi pikiran AI (Prompt masuk, Data dari pgvector, Output dari AI)
    # Disimpan sebagai JSONB agar bisa dirender rapi di Dashboard Admin
    payload = Column(JSONB, nullable=False) 
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())