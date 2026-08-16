from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..infrastructure.db_models import UserModel
from ..infrastructure.security import create_access_token, get_authorized_camera_names, get_current_user, get_session, verify_password
from ..infrastructure.settings import settings
from .activity import add_activity_event
from .schemas import TokenResponse, UserResponse
from .user_serializers import serialize_user
router = APIRouter(prefix="/auth", tags=["auth"])
@router.post("/login", response_model=TokenResponse)
async def login(response: Response, form: OAuth2PasswordRequestForm = Depends(), session: AsyncSession = Depends(get_session)):
    user = await session.scalar(select(UserModel).where(UserModel.username == form.username))
    if user is None or not user.is_active or not verify_password(form.password, user.password_hash): raise HTTPException(status_code=401, detail="Incorrect username or password")
    # Successful logins are meaningful audit events.  The event timestamp is
    # assigned by the server, not supplied by the browser.
    add_activity_event(session, user_id=user.id, event_type="login")
    await session.commit()
    access_token = create_access_token(user)
    response.set_cookie("access_token", access_token, httponly=True, secure=settings.auth_cookie_secure, samesite="lax", max_age=settings.jwt_access_token_minutes * 60, path="/")
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/logout", status_code=204)
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
@router.get("/me", response_model=UserResponse)
async def me(
    user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    camera_names = await get_authorized_camera_names(user, session)
    return serialize_user(user, camera_names or [])
