# app/models/system_configs.py
from sqlalchemy import Column, Integer, String, Boolean, Text
from sqlalchemy.dialects.postgresql import JSONB
from app.models.base import Base

class SystemConfig(Base):
    __tablename__ = "system_configs"

    id = Column(Integer, primary_key=True, index=True)
    config_key = Column(String(100), unique=True, index=True, nullable=False)
    
    # 🌟 Diubah ke JSONB: Bisa menampung Angka, Teks, Boolean, atau Dictionary bersarang
    config_value = Column(JSONB, nullable=False) 
    
    # 🌟 BARU: Memberi tahu Frontend (React) tipe input apa yang harus dirender
    # Contoh: 'number', 'boolean', 'string', 'json'
    config_type = Column(String(50), default="string", nullable=False) 
    
    description = Column(Text, nullable=True) 
    is_active = Column(Boolean, default=True)