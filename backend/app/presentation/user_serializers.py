from collections.abc import Iterable

from ..infrastructure.db_models import UserModel
from .schemas import UserResponse


def serialize_user(user: UserModel, camera_names: Iterable[str] = ()) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        is_active=user.is_active,
        is_admin=user.is_admin,
        role=user.role,
        camera_names=sorted(camera_names),
    )
