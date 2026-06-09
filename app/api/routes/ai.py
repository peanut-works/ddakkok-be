"""AI 관련 API 엔드포인트.

현재:
  GET /api/ai/ping  — AI provider 연결 테스트 (소량 호출)
"""

from fastapi import APIRouter, Depends

from app.ai.base import ChatMessage
from app.ai.factory import get_ai_provider
from app.ai.base import AIProvider
from app.core.config import Settings, get_settings

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/ping")
async def ai_ping(
    provider: AIProvider = Depends(get_ai_provider),
    settings: Settings = Depends(get_settings),
) -> dict:
    """AI provider 연결 테스트.

    - AI_PROVIDER=openai: OpenAI API를 실제 호출 (소량)
    - AI_PROVIDER=mock: mock 응답 즉시 반환 (API 호출 없음)
    - OpenAI 호출 실패 시: FallbackAIProvider가 mock으로 자동 전환

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

    response = await provider.chat_complete(messages, temperature=0.0)

    return {
        "status": "ok",
        "provider": settings.ai_provider,
        "response": response,
    }
