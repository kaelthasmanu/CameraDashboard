from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.user import UserRole
from ..infrastructure.db_models import UserModel
from ..infrastructure.security import get_session, hash_password, require_admin
from .schemas import CreateUserRequest, UserResponse


router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserResponse])
async def list_users(
    session: AsyncSession = Depends(get_session),
    _: UserModel = Depends(require_admin),
):
    result = await session.scalars(select(UserModel).order_by(UserModel.username))
    return result.all()


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: CreateUserRequest,
    session: AsyncSession = Depends(get_session),
    _: UserModel = Depends(require_admin),
):
    existing_user = await session.scalar(
        select(UserModel).where(UserModel.username == payload.username)
    )
    if existing_user is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ese nombre de usuario ya existe")

    user = UserModel(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role.value,
        # Kept in sync for installations that still read this legacy column.
        is_admin=payload.role is UserRole.ADMIN,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ese nombre de usuario ya existe") from error
    await session.refresh(user)
    return user
