"""임베딩 provider 추상화.

text-embedding-3-small 기준 벡터 차원: 1536

provider 선택:
  EMBEDDING_PROVIDER=mock   → MockEmbeddingProvider (키 불필요, 고정 벡터)
  EMBEDDING_PROVIDER=openai → OpenAI embeddings API
  EMBEDDING_PROVIDER=gms    → GMS embeddings (OpenAI 호환, gms_api_key + gms_api_url 재사용)

모든 provider는 FallbackEmbeddingProvider로 래핑 → 실패 시 mock으로 자동 전환.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from functools import lru_cache

from fastapi import Depends
from openai import AsyncOpenAI

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 1536  # text-embedding-3-small 기본 차원


# ── 추상 기반 ──────────────────────────────────────────────────────────────────


class EmbeddingProvider(ABC):
    """텍스트 목록을 벡터 목록으로 변환하는 provider 인터페이스."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """texts[i] → float[EMBEDDING_DIM] 변환.

        Returns:
            texts와 동일한 길이의 벡터 목록.
        """


# ── 구현체 ─────────────────────────────────────────────────────────────────────


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI text-embedding-3-small (또는 GMS 호환 엔드포인트).

    GMS 사용 시: base_url=gms_api_url, api_key=gms_api_key 로 초기화.
    GMS가 OpenAI 호환 형식이므로 동일 클라이언트 재사용 가능.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        base_url: str | None = None,
    ) -> None:
        self._model = model
        self._client = AsyncOpenAI(
            api_key=api_key,
            **({"base_url": base_url} if base_url else {}),
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = await self._client.embeddings.create(
            model=self._model,
            input=texts,
        )
        return [item.embedding for item in response.data]


class MockEmbeddingProvider(EmbeddingProvider):
    """테스트·시연용 mock provider. API 키 불필요.

    반환 벡터는 모두 동일한 고정값이므로 코사인 유사도 비교는 무의미하지만,
    파이프라인 I/O 형식 검증과 DB 저장 테스트에는 충분하다.
    """

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * EMBEDDING_DIM for _ in texts]


class FallbackEmbeddingProvider(EmbeddingProvider):
    """primary 실패 시 MockEmbeddingProvider로 자동 전환."""

    def __init__(self, primary: EmbeddingProvider) -> None:
        self._primary = primary
        self._fallback = MockEmbeddingProvider()
        self._name = type(primary).__name__

    async def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            return await self._primary.embed(texts)
        except Exception as exc:
            logger.warning(
                "[EMBEDDING FALLBACK] provider=%s error=%s: %s",
                self._name,
                type(exc).__name__,
                exc,
            )
            return await self._fallback.embed(texts)


# ── 팩토리 ─────────────────────────────────────────────────────────────────────


@lru_cache
def _build_embedding_provider(
    embedding_provider: str,
    openai_api_key: str,
    openai_embedding_model: str,
    gms_api_key: str,
    gms_api_url: str,
) -> EmbeddingProvider:
    if embedding_provider == "openai":
        return FallbackEmbeddingProvider(
            OpenAIEmbeddingProvider(api_key=openai_api_key, model=openai_embedding_model)
        )
    if embedding_provider == "gms":
        return FallbackEmbeddingProvider(
            OpenAIEmbeddingProvider(
                api_key=gms_api_key,
                model=openai_embedding_model,
                base_url=gms_api_url or None,
            )
        )
    return MockEmbeddingProvider()


def get_embedding_provider(settings: Settings = Depends(get_settings)) -> EmbeddingProvider:
    """FastAPI Depends로 주입 가능한 EmbeddingProvider 팩토리."""
    return _build_embedding_provider(
        embedding_provider=settings.embedding_provider,
        openai_api_key=settings.openai_api_key,
        openai_embedding_model=settings.openai_embedding_model,
        gms_api_key=settings.gms_api_key,
        gms_api_url=settings.gms_api_url,
    )
