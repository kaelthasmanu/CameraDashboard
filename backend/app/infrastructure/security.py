from datetime import datetime, timedelta, timezone
import hashlib, hmac, os
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .database import SessionLocal
from .db_models import UserModel
from .settings import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)
def hash_password(password: str) -> str:
    salt = os.urandom(16); digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return f"pbkdf2_sha256$310000${salt.hex()}${digest.hex()}"
def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt, expected = encoded.split("$")
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds))
        return algorithm == "pbkdf2_sha256" and hmac.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError): return False
def create_access_token(user: UserModel) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_minutes)
    return jwt.encode({"sub": str(user.id), "username": user.username, "admin": user.is_admin, "exp": expires}, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
async def get_session():
    async with SessionLocal() as session: yield session
async def get_current_user(request: Request, token: str | None = Depends(oauth2_scheme), session: AsyncSession = Depends(get_session)) -> UserModel:
    unauthorized = HTTPException(status_code=401, detail="Invalid or expired token", headers={"WWW-Authenticate": "Bearer"})
    token = token or request.cookies.get("access_token")
    if not token: raise unauthorized
    try: user_id = int(jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]).get("sub", ""))
    except (jwt.InvalidTokenError, ValueError, TypeError): raise unauthorized
    user = await session.scalar(select(UserModel).where(UserModel.id == user_id, UserModel.is_active.is_(True)))
    if user is None: raise unauthorized
    return user
