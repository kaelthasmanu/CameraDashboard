from datetime import datetime, timedelta, timezone
import hashlib, hmac, os
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .database import SessionLocal
from .db_models import UserCameraAccessModel, UserModel
from .settings import settings
from ..domain.user import UserRole

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
    return jwt.encode({"sub": str(user.id), "username": user.username, "admin": user.is_admin, "role": user.role, "exp": expires}, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
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


def require_roles(*allowed_roles: UserRole):
    """Require one of the requested roles using the freshly loaded DB user.

    The role is deliberately read from the database instead of trusting a JWT
    claim, so a role change is effective immediately for active sessions.
    """

    allowed_values = {role.value for role in allowed_roles}

    async def role_dependency(user: UserModel = Depends(get_current_user)) -> UserModel:
        if user.role not in allowed_values:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permiso para realizar esta acción")
        return user

    return role_dependency


require_live_access = require_roles(UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.GUARDIA)
require_recording_access = require_roles(UserRole.ADMIN, UserRole.SUPERVISOR)
require_admin = require_roles(UserRole.ADMIN)


async def get_authorized_camera_names(
    user: UserModel, session: AsyncSession
) -> set[str] | None:
    """Return permitted MediaMTX camera paths, or None for an admin."""

    if user.role == UserRole.ADMIN.value:
        return None

    result = await session.scalars(
        select(UserCameraAccessModel.camera_name).where(
            UserCameraAccessModel.user_id == user.id
        )
    )
    return set(result.all())
