from functools import lru_cache

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.ai.base import AIProvider
from app.ai.fallback import FallbackAIProvider
from app.ai.gms import GMSProvider
from app.ai.mock import MockAIProvider
from app.ai.openai import OpenAIProvider


@lru_cache
def _build_provider(
    ai_provider: str,
    openai_api_key: str,
    openai_model: str,
    gms_api_key: str,
    gms_api_url: str,
    gms_model: str,
) -> AIProvider:
    if ai_provider == "openai":
        return FallbackAIProvider(
            primary=OpenAIProvider(api_key=openai_api_key, model=openai_model)
        )
    if ai_provider == "gms":
        return FallbackAIProvider(
            primary=GMSProvider(api_key=gms_api_key, api_url=gms_api_url, model=gms_model)
        )
    return MockAIProvider()


def get_ai_provider(settings: Settings = Depends(get_settings)) -> AIProvider:
    """FastAPI Depends로 주입 가능한 AI provider 팩토리.

    - mock: MockAIProvider 직접 반환
    - openai / gms: FallbackAIProvider로 감싸 API 실패 시 mock으로 자동 전환
    """
    return _build_provider(
        ai_provider=settings.ai_provider,
        openai_api_key=settings.openai_api_key,
        openai_model=settings.openai_model,
        gms_api_key=settings.gms_api_key,
        gms_api_url=settings.gms_api_url,
        gms_model=settings.gms_model,
    )
