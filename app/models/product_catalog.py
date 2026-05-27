# app/models/product_catalog.py
from sqlalchemy import Column, Integer, String, Float, Boolean, Text
from sqlalchemy.dialects.postgresql import JSONB, ARRAY  # Senjata rahasia untuk data tidak konsisten
# pyrefly: ignore [missing-import]
from pgvector.sqlalchemy import Vector
from app.models.base import Base

class Product(Base):
    __tablename__ = "product_catalog"

    # --- 1. IDENTITAS WAJIB (Fixed Schema) ---
    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(50), unique=True, index=True, nullable=False) # Kunci Utama Anda
    name = Column(String(255), nullable=False)
    brand = Column(String(100), index=True, nullable=True) # Contoh: 'Gresik', 'INGCO'
    
    # Kategori bisa panjang jika digabung (Misal: "Hand Tools, Tools & Machinery")
    category = Column(String(255), index=True, nullable=False) 
    
    price = Column(Float, nullable=False, default=0.0)
    stock = Column(Integer, default=0, nullable=False)
    unit = Column(String(50), nullable=True) # Contoh: 'sak', 'pcs', 'lembar'

    # --- 2. KERANJANG FLEKSIBEL (Schema-less) ---
    # Menampung peluru fitur (Misal: "Bisa menggunakan Genset", "Terdapat fitur 2T4T")
    description = Column(Text, nullable=True) 
    
    # Menampung spesifikasi beda-beda (Tersimpan sebagai Dictionary/JSON)
    # Contoh isi: {"Tipe Produk": "Semen Portland", "Waktu Ikat Akhir": "± 6 - 8 jam"}
    # Contoh isi lain: {"Lebar Efektif": "750 mm", "Ketebalan": "0.30 mm"}
    specifications = Column(JSONB, nullable=True) 
    
    # Menampung tag (Tersimpan sebagai Array List)
    # Contoh isi: ["Mesin Las", "Kawat Otomatis"]
    tags = Column(ARRAY(String), nullable=True)

    # --- 3. KECERDASAN BUATAN (AI Search) ---
    # Kolom ini nanti diisi otomatis oleh AI (Gabungan Name + Deskripsi + Spesifikasi)
    embedding = Column(Vector(768), nullable=True) 
    
    is_active = Column(Boolean, default=True)