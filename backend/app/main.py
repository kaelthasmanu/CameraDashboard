from fastapi import Depends, FastAPI
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from .presentation.api import router
from .presentation.schemas import HealthResponse
from .infrastructure.cors import (
    CIDRCORSMiddleware,
    parse_cors_origin_cidr_ports,
    parse_cors_origin_cidrs,
    parse_cors_origins,
)
from .infrastructure.settings import settings
from .infrastructure.database import Base, engine, SessionLocal
from .infrastructure.db_models import UserModel
from .infrastructure.security import hash_password, require_admin
from .presentation.auth import router as auth_router
from .presentation.activity import router as activity_router
from .presentation.users import router as users_router
from .domain.user import UserRole
from sqlalchemy import select

# Documentation is mounted explicitly below so its schema cannot reveal the
# API surface to unauthenticated visitors.
app = FastAPI(
    title="Hikvision Camera Dashboard API",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
cors_origin_cidrs = parse_cors_origin_cidrs(settings.cors_origin_cidrs)
cors_cidr_ports = parse_cors_origin_cidr_ports(settings.cors_origin_cidr_ports)
if cors_origin_cidrs and not cors_cidr_ports:
    raise ValueError(
        "CORS_ORIGIN_CIDR_PORTS es obligatorio cuando CORS_ORIGIN_CIDRS está configurado"
    )
app.add_middleware(
    CIDRCORSMiddleware,
    allow_origins=parse_cors_origins(settings.cors_origins),
    allow_origin_cidrs=cors_origin_cidrs,
    cidr_allowed_ports=cors_cidr_ports,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Range"],
    expose_headers=["Accept-Ranges", "Content-Length", "Content-Range"],
    allow_credentials=True,
)
app.include_router(router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(activity_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")

@app.on_event("startup")
async def initialize_database():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        user = await session.scalar(select(UserModel).where(UserModel.username == settings.admin_username))
        if user is None:
            session.add(UserModel(
                username=settings.admin_username,
                password_hash=hash_password(settings.admin_password),
                is_admin=True,
                role=UserRole.ADMIN.value,
            ))
            await session.commit()

@app.get("/health", response_model=HealthResponse)
async def health():
    return {"status": "ok"}


@app.get("/openapi.json", include_in_schema=False)
async def openapi_schema(_: UserModel = Depends(require_admin)):
    return app.openapi()


@app.get("/docs", include_in_schema=False)
async def swagger_ui(_: UserModel = Depends(require_admin)):
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=f"{app.title} - Swagger UI",
    )


@app.get("/redoc", include_in_schema=False)
async def redoc_ui(_: UserModel = Depends(require_admin)):
    return get_redoc_html(
        openapi_url="/openapi.json",
        title=f"{app.title} - ReDoc",
    )
