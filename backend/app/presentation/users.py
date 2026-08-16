from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..application.camera_service import CameraService
from ..domain.user import UserRole
from ..infrastructure.db_models import UserCameraAccessModel, UserModel
from ..infrastructure.security import get_session, hash_password, require_admin
from .camera_dependencies import get_camera_service
from .schemas import CreateUserRequest, UpdateUserCameraAccessRequest, UserResponse
from .user_serializers import serialize_user


router = APIRouter(prefix="/users", tags=["users"])


async def validate_camera_names(
    camera_names: list[str], camera_service: CameraService
) -> list[str]:
    available_names = {
        camera.name for camera in await camera_service.list_cameras()
    }
    unknown_names = sorted(set(camera_names) - available_names)
    if unknown_names:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cámaras no encontradas: {', '.join(unknown_names)}",
        )
    return camera_names


@router.get("", response_model=list[UserResponse])
async def list_users(
    session: AsyncSession = Depends(get_session),
    _: UserModel = Depends(require_admin),
):
    users = (await session.scalars(select(UserModel).order_by(UserModel.username))).all()
    if not users:
        return []

    assignments = await session.execute(
        select(UserCameraAccessModel.user_id, UserCameraAccessModel.camera_name).where(
            UserCameraAccessModel.user_id.in_([user.id for user in users])
        )
    )
    camera_names_by_user = {user.id: [] for user in users}
    for user_id, camera_name in assignments.all():
        camera_names_by_user[user_id].append(camera_name)

    return [serialize_user(user, camera_names_by_user[user.id]) for user in users]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: CreateUserRequest,
    session: AsyncSession = Depends(get_session),
    _: UserModel = Depends(require_admin),
    camera_service: CameraService = Depends(get_camera_service),
):
    existing_user = await session.scalar(
        select(UserModel).where(UserModel.username == payload.username)
    )
    if existing_user is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ese nombre de usuario ya existe")

    camera_names = [] if payload.role == UserRole.ADMIN else await validate_camera_names(
        payload.camera_names, camera_service
    )
    user = UserModel(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role.value,
        # Kept in sync for installations that still read this legacy column.
        is_admin=payload.role == UserRole.ADMIN,
    )
    session.add(user)
    try:
        await session.flush()
        session.add_all(
            UserCameraAccessModel(user_id=user.id, camera_name=camera_name)
            for camera_name in camera_names
        )
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ese nombre de usuario ya existe") from error
    await session.refresh(user)
    return serialize_user(user, camera_names)


@router.put("/{user_id}/cameras", response_model=UserResponse)
async def update_user_camera_access(
    user_id: int,
    payload: UpdateUserCameraAccessRequest,
    session: AsyncSession = Depends(get_session),
    _: UserModel = Depends(require_admin),
    camera_service: CameraService = Depends(get_camera_service),
):
    user = await session.scalar(select(UserModel).where(UserModel.id == user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    camera_names = [] if user.role == UserRole.ADMIN.value else await validate_camera_names(
        payload.camera_names, camera_service
    )
    await session.execute(
        delete(UserCameraAccessModel).where(UserCameraAccessModel.user_id == user.id)
    )
    session.add_all(
        UserCameraAccessModel(user_id=user.id, camera_name=camera_name)
        for camera_name in camera_names
    )
    await session.commit()
    return serialize_user(user, camera_names)
