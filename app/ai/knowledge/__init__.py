"""딱콕 지식베이스 데이터. load_all()로 전체 청크를 가져온다."""

from __future__ import annotations

from dataclasses import dataclass

from app.ai.knowledge.allergens import ALLERGEN_CHUNKS
from app.ai.knowledge.cosmetics import COSMETICS_CHUNKS
from app.ai.knowledge.daily_chemicals import DAILY_CHEMICAL_CHUNKS


@dataclass
class KnowledgeChunkData:
    title: str
    content: str
    category: str
    source: str


def load_all() -> list[KnowledgeChunkData]:
    """모든 카테고리 청크를 하나의 리스트로 반환한다."""
    raw = ALLERGEN_CHUNKS + COSMETICS_CHUNKS + DAILY_CHEMICAL_CHUNKS
    return [KnowledgeChunkData(**item) for item in raw]
