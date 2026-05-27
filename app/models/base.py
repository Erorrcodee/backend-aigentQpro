# app/models/base.py
from sqlalchemy.orm import declarative_base

# Ini adalah induk (parent) dari semua model tabel database yang akan kita buat
Base = declarative_base()