from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .presentation.api import router
from .presentation.schemas import HealthResponse
from .infrastructure.settings import settings
from .infrastructure.database import Base, engine, SessionLocal
from .infrastructure.db_models import UserModel
from .infrastructure.security import hash_password
from .presentation.auth import router as auth_router
from sqlalchemy import select

app = FastAPI(title="Hikvision Camera Dashboard API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()], allow_methods=["*"], allow_headers=["*"], allow_credentials=True)
app.include_router(router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")

@app.on_event("startup")
async def initialize_database():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        user = await session.scalar(select(UserModel).where(UserModel.username == settings.admin_username))
        if user is None:
            session.add(UserModel(username=settings.admin_username, password_hash=hash_password(settings.admin_password), is_admin=True))
            await session.commit()

@app.get("/health", response_model=HealthResponse)
async def health():
    return {"status": "ok"}
