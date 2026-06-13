import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.routes.ai import router as ai_router
from app.api.routes.auth import router as auth_router
from app.api.routes.children import router as children_router
from app.api.routes.classrooms import router as classrooms_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.health import router as health_router
from app.api.routes.products import router as products_router
from app.api.routes.recalls import router as recalls_router
from app.api.routes.safety_checks import router as safety_checks_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.schemas.common import RootResponse

logger = logging.getLogger(__name__)
settings = get_settings()


async def _seed_knowledge_if_empty() -> None:
    """서버 시작 시 knowledge_chunks 테이블이 비어있으면 27개 청크를 자동 적재한다."""
    from app.ai.embedding import get_embedding_provider
    from app.ai.knowledge_loader import KnowledgeLoader
    from app.core.database import SessionLocal
    from app.models.knowledge_chunk import KnowledgeChunk

    db = SessionLocal()
    try:
        count = db.query(KnowledgeChunk).count()
        if count > 0:
            logger.info("[Startup] knowledge_chunks %d개 이미 존재 — 스킵", count)
            return
        embed = get_embedding_provider(settings)
        n = await KnowledgeLoader(db=db, embed_provider=embed).load_all()
        logger.info("[Startup] knowledge_chunks %d개 적재 완료", n)
    except Exception as exc:
        db.rollback()
        logger.warning("[Startup] 지식베이스 적재 실패 (서버는 계속 구동): %s", exc)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _seed_knowledge_if_empty()
    yield


app = FastAPI(
    title=settings.app_name,
    description="영유아 맞춤 제품 안전관리 서비스 딱콕 API",
    version="0.1.0",
    lifespan=lifespan,
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
app.include_router(dashboard_router)
app.include_router(recalls_router)


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
