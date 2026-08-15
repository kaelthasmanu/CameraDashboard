from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .presentation.api import router
from .presentation.schemas import HealthResponse
from .infrastructure.settings import settings

app = FastAPI(title="Hikvision Camera Dashboard API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()], allow_methods=["*"], allow_headers=["*"])
app.include_router(router, prefix="/api/v1")

@app.get("/health", response_model=HealthResponse)
async def health():
    return {"status": "ok"}
