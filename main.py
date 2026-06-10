from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.routes.ai import router as ai_router
from app.api.routes.auth import router as auth_router
from app.api.routes.children import router as children_router
from app.api.routes.classrooms import router as classrooms_router
from app.api.routes.health import router as health_router
from app.api.routes.products import router as products_router
from app.api.routes.safety_checks import router as safety_checks_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.schemas.common import RootResponse

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

register_exception_handlers(app)

app.include_router(health_router)
app.include_router(ai_router)
app.include_router(auth_router)
app.include_router(classrooms_router)
app.include_router(products_router)
app.include_router(children_router)
app.include_router(safety_checks_router)


@app.get(
    "/",
    response_model=RootResponse,
    summary="API root",
)
def root() -> RootResponse:
    return RootResponse(
        message="Ddakkok API",
        docs="/docs",
        health="/api/health",
    )


@app.get("/api/docs", include_in_schema=False)
def api_docs():
    return RedirectResponse(url="/docs")
