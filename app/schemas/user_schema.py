# app/schemas/user_schema.py
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from app.models.users import UserRole

class UserCreate(BaseModel):
    """Payload saat user baru mendaftar (Register)"""
    email: EmailStr = Field(..., description="Email valid yang akan jadi username")
    password: str = Field(..., min_length=6, description="Minimal 6 karakter")
    full_name: str
    company_name: Optional[str] = None
    role: UserRole = UserRole.B2C # Default ke retail biasa jika tidak diisi

class UserResponse(BaseModel):
    """Balasan data user tanpa menampilkan password!"""
    id: int
    email: EmailStr
    full_name: str
    company_name: Optional[str] = None
    role: UserRole
    is_active: bool

    class Config:
        from_attributes = True