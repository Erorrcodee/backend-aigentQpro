# app/models/users.py
from sqlalchemy import Column, Integer, String, Boolean, Enum
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime
import enum
from app.models.base import Base

class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    B2B = "B2B"  # Kontraktor
    B2C = "B2C"  # Retail

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    
    full_name = Column(String(255), nullable=False)
    company_name = Column(String(255), nullable=True) # Hanya B2B
    role = Column(Enum(UserRole), default=UserRole.B2C, nullable=False)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())