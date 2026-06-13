"""지식베이스 로더 및 유사도 검색 서비스.

사용 흐름:
  1. KnowledgeLoader.load_all()  — 지식베이스 전체를 DB에 임베딩+저장
  2. KnowledgeLoader.search()    — 쿼리 텍스트로 관련 청크 top-k 검색 (RAG용)
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.embedding import EMBEDDING_DIM, EmbeddingProvider
from app.ai.knowledge import KnowledgeChunkData, load_all
from app.models.knowledge_chunk import KnowledgeChunk

logger = logging.getLogger(__name__)

_BATCH_SIZE = 50  # 임베딩 API 단일 호출당 최대 텍스트 수
_MAX_COSINE_DISTANCE = 0.6  # 코사인 거리(0=동일, 2=정반대). 이 값보다 먼 청크는 관련성 낮음으로 제외.


class KnowledgeLoader:
    """지식베이스 청크를 임베딩해 DB에 저장하고, 코사인 유사도로 검색한다."""

    def __init__(self, db: Session, embed_provider: EmbeddingProvider) -> None:
        self._db = db
        self._embed = embed_provider

    # ── 로딩 ───────────────────────────────────────────────────────────────────

    async def load_all(self, *, replace: bool = False) -> int:
        """지식베이스 전체 청크를 임베딩하고 DB에 저장한다.

        Args:
            replace: True이면 기존 데이터를 모두 삭제 후 재삽입한다.

        Returns:
            저장된 청크 수.
        """
        if replace:
            self._db.query(KnowledgeChunk).delete()
            self._db.flush()
            logger.info("기존 knowledge_chunks 전체 삭제")

        chunks = load_all()
        if not chunks:
            return 0

        total = 0
        for i in range(0, len(chunks), _BATCH_SIZE):
            batch = chunks[i : i + _BATCH_SIZE]
            total += await self._insert_batch(batch)

        self._db.commit()
        logger.info("knowledge_chunks %d건 저장 완료", total)
        return total

    async def _insert_batch(self, batch: list[KnowledgeChunkData]) -> int:
        texts = [f"{c.title}\n{c.content}" for c in batch]
        vectors = await self._embed.embed(texts)

        rows = [
            KnowledgeChunk(
                title=chunk.title,
                content=chunk.content,
                category=chunk.category,
                source=chunk.source,
                embedding=vec,
            )
            for chunk, vec in zip(batch, vectors, strict=True)
        ]
        self._db.add_all(rows)
        self._db.flush()
        return len(rows)

    # ── 검색 ───────────────────────────────────────────────────────────────────

    async def search(
        self,
        query: str,
        top_k: int = 5,
        category: str | None = None,
        max_distance: float = _MAX_COSINE_DISTANCE,
    ) -> list[KnowledgeChunk]:
        """쿼리 텍스트와 코사인 유사도가 높은 청크를 top_k개 반환한다.

        Args:
            query:        검색 쿼리 (성분명, 규칙 설명 등)
            top_k:        반환할 최대 청크 수
            category:     지정 시 해당 카테고리로 필터링
            max_distance: 코사인 거리 임계값. 이보다 먼(=관련성 낮은) 청크는 제외한다.
                          관련 청크가 없으면 빈 리스트를 반환해 LLM에 노이즈가 주입되지 않게 한다.

        Returns:
            KnowledgeChunk 목록 (유사도 내림차순, max_distance 이내)
        """
        query_vectors = await self._embed.embed([query])
        if not query_vectors or len(query_vectors[0]) != EMBEDDING_DIM:
            logger.warning("search: 임베딩 실패 — 빈 결과 반환")
            return []

        query_vec = query_vectors[0]
        distance = KnowledgeChunk.embedding.cosine_distance(query_vec)

        stmt = select(KnowledgeChunk).where(KnowledgeChunk.embedding.isnot(None))
        if category:
            stmt = stmt.where(KnowledgeChunk.category == category)
        stmt = stmt.where(distance <= max_distance).order_by(distance).limit(top_k)

        return list(self._db.scalars(stmt).all())
