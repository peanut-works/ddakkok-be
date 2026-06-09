from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.routes.ai import router as ai_router
from app.api.routes.health import router as health_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="영유아 맞춤 제품 안전관리 서비스 딱콕 API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(ai_router)


@app.get("/")
def root():
    return {
        "message": "Ddakkok API",
        "docs": "/docs",
        "health": "/api/health",
    }


@app.get("/api/docs", include_in_schema=False)
def api_docs():
    return RedirectResponse(url="/docs")
