# app/api/endpoints/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token
from app.models.users import User
from app.schemas.common_schema import TokenResponse, BaseResponse
from app.schemas.user_schema import UserCreate, UserResponse

router = APIRouter()

@router.post("/register", response_model=BaseResponse[UserResponse], status_code=status.HTTP_201_CREATED)
async def register_user(
    user_in: UserCreate, 
    db: AsyncSession = Depends(get_db)
):
    """Mendaftarkan akun baru (B2B/B2C/Admin)"""
    # Cek apakah email sudah terdaftar
    stmt = select(User).where(User.email == user_in.email)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email sudah digunakan.")

    # Simpan user baru dengan password yang di-hash
    new_user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        company_name=user_in.company_name,
        role=user_in.role
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return BaseResponse(
        status="success", 
        message="Registrasi berhasil", 
        data=UserResponse.model_validate(new_user)
    )

@router.post("/login", response_model=TokenResponse)
async def login_access_token(
    db: AsyncSession = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
):
    """Mengecek email & password, lalu memberikan Tiket JWT"""
    # Cari email di database
    stmt = select(User).where(User.email == form_data.username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    # Validasi password
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email atau password salah",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Akun tidak aktif.")

    # Cetak Token JWT
    access_token = create_access_token(subject=user.id, role=user.role.value)
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        role=user.role.value
    )