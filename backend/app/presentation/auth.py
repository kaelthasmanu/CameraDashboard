from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..infrastructure.db_models import UserModel
from ..infrastructure.security import create_access_token, get_current_user, get_session, verify_password
from .schemas import TokenResponse, UserResponse
router = APIRouter(prefix="/auth", tags=["auth"])
@router.post("/login", response_model=TokenResponse)
async def login(form: OAuth2PasswordRequestForm = Depends(), session: AsyncSession = Depends(get_session)):
    user = await session.scalar(select(UserModel).where(UserModel.username == form.username))
    if user is None or not user.is_active or not verify_password(form.password, user.password_hash): raise HTTPException(status_code=401, detail="Incorrect username or password")
    return {"access_token": create_access_token(user), "token_type": "bearer"}
@router.get("/me", response_model=UserResponse)
async def me(user: UserModel = Depends(get_current_user)): return user
