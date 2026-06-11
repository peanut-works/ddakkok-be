"""지식베이스 초기 로딩 스크립트.

사용법:
  python scripts/load_knowledge_base.py            # 새 데이터 추가 (기존 유지)
  python scripts/load_knowledge_base.py --replace  # 기존 데이터 삭제 후 재삽입

환경변수:
  EMBEDDING_PROVIDER=openai  OPENAI_API_KEY=sk-xxx  → OpenAI 임베딩
  EMBEDDING_PROVIDER=gms     GMS_API_KEY=xxx GMS_API_URL=https://...  → GMS 임베딩
  EMBEDDING_PROVIDER=mock    (기본값)  → mock 벡터 (DB 저장 테스트용)
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.ai.embedding import get_embedding_provider  # noqa: E402
from app.ai.knowledge_loader import KnowledgeLoader  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402


async def main(replace: bool) -> None:
    settings = get_settings()
    print(f"EMBEDDING_PROVIDER = {settings.embedding_provider}")
    print(f"OPENAI_EMBEDDING_MODEL = {settings.openai_embedding_model}")

    embed_provider = get_embedding_provider(settings)
    db = SessionLocal()
    try:
        loader = KnowledgeLoader(db=db, embed_provider=embed_provider)
        count = await loader.load_all(replace=replace)
        print(f"완료: {count}건 저장")
    finally:
        db.close()


if __name__ == "__main__":
    replace = "--replace" in sys.argv
    asyncio.run(main(replace=replace))
