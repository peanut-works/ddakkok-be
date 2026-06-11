from functools import lru_cache

from fastapi import Depends

from app.ai.base import AIProvider
from app.ai.cache import CachedAIProvider
from app.ai.fallback import FallbackAIProvider
from app.ai.gms import GMSProvider
from app.ai.mock import MockAIProvider
from app.ai.openai import OpenAIProvider
from app.core.config import Settings, get_settings


@lru_cache
def _build_provider(
    ai_provider: str,
    openai_api_key: str,
    openai_model: str,
    gms_api_key: str,
    gms_api_url: str,
    gms_model: str,
    groq_api_key: str,
    groq_api_url: str,
    groq_model: str,
    ai_cache_enabled: bool,
    ai_cache_maxsize: int,
) -> AIProvider:
    if ai_provider == "openai":
        provider: AIProvider = FallbackAIProvider(
            primary=OpenAIProvider(api_key=openai_api_key, model=openai_model)
        )
    elif ai_provider == "gms":
        provider = FallbackAIProvider(
            primary=GMSProvider(api_key=gms_api_key, api_url=gms_api_url, model=gms_model)
        )
    elif ai_provider == "groq":
        # Groq는 OpenAI 호환 API — base_url만 바꿔 OpenAIProvider 재사용
        provider = FallbackAIProvider(
            primary=OpenAIProvider(
                api_key=groq_api_key,
                model=groq_model,
                base_url=groq_api_url,
            )
        )
    else:
        return MockAIProvider()  # mock은 캐시 불필요 (비용 없음)

    if ai_cache_enabled:
        return CachedAIProvider(primary=provider, maxsize=ai_cache_maxsize)
    return provider


def get_ai_provider(settings: Settings = Depends(get_settings)) -> AIProvider:
    """FastAPI Depends로 주입 가능한 AI provider 팩토리.

    - mock: MockAIProvider 직접 반환 (캐시 미적용)
    - openai / gms: FallbackAIProvider → CachedAIProvider 순으로 래핑
      AI_CACHE_ENABLED=false 시 캐시 레이어 생략
    """
    return _build_provider(
        ai_provider=settings.ai_provider,
        openai_api_key=settings.openai_api_key,
        openai_model=settings.openai_model,
        gms_api_key=settings.gms_api_key,
        gms_api_url=settings.gms_api_url,
        gms_model=settings.gms_model,
        groq_api_key=settings.groq_api_key,
        groq_api_url=settings.groq_api_url,
        groq_model=settings.groq_model,
        ai_cache_enabled=settings.ai_cache_enabled,
        ai_cache_maxsize=settings.ai_cache_maxsize,
    )
