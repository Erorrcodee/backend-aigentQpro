
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
from app.core.security import ALGORITHM
from app.models.users import User, UserRole

# Memberitahu FastAPI di mana letak "Loket Tiket" login kita (untuk Swagger UI)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    """Fungsi dasar penagih Token JWT"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token tidak valid atau sudah kedaluwarsa",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Bongkar isi Token JWT
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # Cari user di database berdasarkan ID dari dalam Token
    stmt = select(User).where(User.id == int(user_id))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if user is None or not user.is_active:
        raise credentials_exception
        
    return user

# --- ROLE CHECKERS (Satpam Khusus) ---

async def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    """Hanya izinkan jika role adalah ADMIN"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Akses ditolak. Khusus Admin.")
    return current_user

async def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """Memastikan bahwa pengguna yang terautentikasi memiliki peran ADMIN."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Akses ditolak. Hanya diperbolehkan untuk pengguna dengan peran Admin."
        )
    return current_user

async def get_current_b2b(current_user: User = Depends(get_current_user)) -> User:
    """Hanya izinkan jika role adalah B2B (Kontraktor)"""
    if current_user.role != UserRole.B2B:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Akses ditolak. Khusus Kontraktor B2B.")
    return current_user