"""app/ai/embedding.py 및 app/ai/knowledge_loader.py 단위 테스트."""

from __future__ import annotations

import pytest

from app.ai.embedding import (
    EMBEDDING_DIM,
    FallbackEmbeddingProvider,
    MockEmbeddingProvider,
    OpenAIEmbeddingProvider,
)
from app.ai.knowledge import KnowledgeChunkData, load_all
from app.ai.knowledge_loader import KnowledgeLoader
from app.models.knowledge_chunk import KnowledgeChunk


# ── MockEmbeddingProvider ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mock_embed_returns_correct_shape() -> None:
    provider = MockEmbeddingProvider()
    result = await provider.embed(["안녕", "test"])
    assert len(result) == 2
    assert all(len(v) == EMBEDDING_DIM for v in result)


@pytest.mark.asyncio
async def test_mock_embed_empty_input() -> None:
    provider = MockEmbeddingProvider()
    result = await provider.embed([])
    assert result == []


@pytest.mark.asyncio
async def test_mock_embed_values() -> None:
    provider = MockEmbeddingProvider()
    result = await provider.embed(["x"])
    assert result[0][0] == pytest.approx(0.1)


# ── FallbackEmbeddingProvider ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fallback_uses_mock_on_primary_failure() -> None:
    """primary가 예외를 던지면 mock 벡터가 반환된다."""
    from unittest.mock import AsyncMock

    failing_primary = AsyncMock(spec=MockEmbeddingProvider)
    failing_primary.embed.side_effect = RuntimeError("API 오류")

    fallback = FallbackEmbeddingProvider(primary=failing_primary)
    result = await fallback.embed(["테스트"])
    assert len(result) == 1
    assert len(result[0]) == EMBEDDING_DIM


@pytest.mark.asyncio
async def test_fallback_passes_through_on_success() -> None:
    """primary 성공 시 primary 결과가 그대로 반환된다."""
    from unittest.mock import AsyncMock

    fake_vec = [[0.5] * EMBEDDING_DIM]
    primary = AsyncMock(spec=MockEmbeddingProvider)
    primary.embed.return_value = fake_vec

    fallback = FallbackEmbeddingProvider(primary=primary)
    result = await fallback.embed(["테스트"])
    assert result == fake_vec


# ── 지식베이스 데이터 ──────────────────────────────────────────────────────────


def test_load_all_returns_nonempty_list() -> None:
    chunks = load_all()
    assert len(chunks) > 0


def test_load_all_returns_knowledge_chunk_data() -> None:
    chunks = load_all()
    assert all(isinstance(c, KnowledgeChunkData) for c in chunks)


def test_load_all_fields_nonempty() -> None:
    for chunk in load_all():
        assert chunk.title, f"title이 비어 있는 청크: {chunk}"
        assert chunk.content, f"content가 비어 있는 청크: {chunk}"
        assert chunk.category, f"category가 비어 있는 청크: {chunk}"
        assert chunk.source, f"source가 비어 있는 청크: {chunk}"


def test_load_all_covers_all_categories() -> None:
    categories = {c.category for c in load_all()}
    # 알레르기·화장품·생활화학 각 카테고리 접두사 확인
    assert any(c.startswith("allergen_") for c in categories)
    assert any(c.startswith("cosmetics_") for c in categories)
    assert any(c.startswith("daily_chemicals_") for c in categories)


# ── KnowledgeLoader ────────────────────────────────────────────────────────────


def _make_db_mock() -> object:
    """SQLAlchemy Session을 흉내 내는 최소 mock."""
    from unittest.mock import MagicMock

    db = MagicMock()
    db.add_all = MagicMock()
    db.add = MagicMock()
    db.flush = MagicMock()
    db.commit = MagicMock()
    db.query.return_value.delete.return_value = None
    return db


@pytest.mark.asyncio
async def test_knowledge_loader_load_all_returns_count() -> None:
    db = _make_db_mock()
    provider = MockEmbeddingProvider()
    loader = KnowledgeLoader(db=db, embed_provider=provider)  # type: ignore[arg-type]

    count = await loader.load_all()
    total_chunks = len(load_all())
    assert count == total_chunks


@pytest.mark.asyncio
async def test_knowledge_loader_load_all_replace_calls_delete() -> None:
    db = _make_db_mock()
    provider = MockEmbeddingProvider()
    loader = KnowledgeLoader(db=db, embed_provider=provider)  # type: ignore[arg-type]

    await loader.load_all(replace=True)
    db.query.assert_called_once_with(KnowledgeChunk)
    db.query.return_value.delete.assert_called_once()


@pytest.mark.asyncio
async def test_knowledge_loader_search_with_no_embedding_returns_empty() -> None:
    """임베딩 실패(빈 벡터) 시 빈 리스트를 반환한다."""
    from unittest.mock import AsyncMock, MagicMock

    bad_provider = AsyncMock()
    bad_provider.embed.return_value = []  # 빈 벡터

    db = MagicMock()
    loader = KnowledgeLoader(db=db, embed_provider=bad_provider)
    result = await loader.search("파라벤")
    assert result == []


@pytest.mark.asyncio
async def test_knowledge_loader_search_calls_cosine_distance() -> None:
    """search()가 cosine_distance 정렬 쿼리를 실행하는지 확인한다."""
    from unittest.mock import AsyncMock, MagicMock, patch

    provider = AsyncMock()
    provider.embed.return_value = [[0.1] * EMBEDDING_DIM]

    db = MagicMock()
    mock_result = [KnowledgeChunk(title="t", content="c", category="cat", source="src")]
    db.scalars.return_value.all.return_value = mock_result

    with patch("app.ai.knowledge_loader.select") as mock_select:
        mock_stmt = MagicMock()
        mock_select.return_value = mock_stmt
        mock_stmt.where.return_value = mock_stmt
        mock_stmt.order_by.return_value = mock_stmt
        mock_stmt.limit.return_value = mock_stmt

        loader = KnowledgeLoader(db=db, embed_provider=provider)
        results = await loader.search("파라벤", top_k=3)

    assert results == mock_result
    mock_stmt.order_by.assert_called_once()
    mock_stmt.limit.assert_called_once_with(3)
