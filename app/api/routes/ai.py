"""AI 관련 API 엔드포인트.

현재:
  GET /api/ai/ping  — AI provider 연결 테스트 (소량 호출)
"""

import logging

from fastapi import APIRouter, Depends

from app.ai.base import AIProvider, ChatMessage
from app.ai.factory import get_ai_provider
from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/ping")
async def ai_ping(
    provider: AIProvider = Depends(get_ai_provider),
    settings: Settings = Depends(get_settings),
) -> dict:
    """AI provider 연결 테스트.

    - AI_PROVIDER=openai: OpenAI API 실제 호출 (15초 timeout)
    - AI_PROVIDER=mock  : mock 응답 즉시 반환
    - 호출 실패 시       : FallbackAIProvider가 mock으로 자동 전환
    - 어떤 경우에도 200 + 정상 JSON 형식으로 응답 (시연 중단 없음)

    API key는 서버 환경변수에서만 읽으며 응답에 포함되지 않는다.
    """
    messages = [
        ChatMessage(
            role="system",
            content="당신은 API 연결 테스트용 도우미입니다. 한 문장으로만 답하세요.",
        ),
        ChatMessage(
            role="user",
            content="연결 테스트입니다. '연결 성공'이라고만 답해주세요.",
        ),
    ]

    try:
        response = await provider.chat_complete(messages, temperature=0.0)
        return {
            "status": "ok",
            "provider": settings.ai_provider,
            "response": response,
        }
    except Exception as e:
        # FallbackAIProvider가 이미 모든 예외를 잡지만, 만일의 경우를 대비한 최후 방어선.
        # 프론트에는 항상 200 + 정상 형식 반환.
        logger.error("ai_ping 최종 예외 — provider=%s error=%s", settings.ai_provider, e)
        return {
            "status": "fallback",
            "provider": settings.ai_provider,
            "response": "AI 연결에 실패했습니다. Mock 응답으로 대체됩니다.",
        }
