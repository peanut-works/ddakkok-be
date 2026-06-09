from functools import lru_cache

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.services.ai.base import AIProvider
from app.services.ai.gms import GMSProvider
from app.services.ai.mock import MockAIProvider
from app.services.ai.openai import OpenAIProvider


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
        return OpenAIProvider(api_key=openai_api_key, model=openai_model)
    if ai_provider == "gms":
        return GMSProvider(api_key=gms_api_key, api_url=gms_api_url, model=gms_model)
    return MockAIProvider()


def get_ai_provider(settings: Settings = Depends(get_settings)) -> AIProvider:
    """FastAPI Depends로 주입 가능한 AI provider 팩토리."""
    return _build_provider(
        ai_provider=settings.ai_provider,
        openai_api_key=settings.openai_api_key,
        openai_model=settings.openai_model,
        gms_api_key=settings.gms_api_key,
        gms_api_url=settings.gms_api_url,
        gms_model=settings.gms_model,
    )
