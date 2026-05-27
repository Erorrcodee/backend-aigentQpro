# app/schemas/common_schema.py
from pydantic import BaseModel
from typing import Any, Optional, Generic, TypeVar

# Tipe data dinamis (Bisa List, Dict, dll)
T = TypeVar("T")

class BaseResponse(BaseModel, Generic[T]):
    """Standar baku balasan HTTP ke Frontend"""
    status: str = "success"
    message: str
    data: Optional[T] = None

class TokenResponse(BaseModel):
    """Skema saat user berhasil login"""
    access_token: str
    token_type: str = "bearer"
    role: str
    
class ErrorResponse(BaseModel):
    """Standar balasan jika terjadi error"""
    status: str = "error"
    message: str
    detail: Optional[Any] = None