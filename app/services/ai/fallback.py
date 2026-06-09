import logging

from app.services.ai.base import AIProvider, ChatMessage
from app.services.ai.mock import MockAIProvider

logger = logging.getLogger(__name__)


class FallbackAIProvider(AIProvider):
    """primary provider 호출 실패 시 MockAIProvider로 자동 전환하는 래퍼.

    GMS key 미설정, OpenAI 할당량 초과, 네트워크 오류 등 모든 예외를
    잡아 mock 응답으로 대체한다. 시연 환경에서 API key 없이도 동작 가능.
    """

    def __init__(self, primary: AIProvider) -> None:
        self._primary = primary
        self._fallback = MockAIProvider()

    async def chat_complete(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.3,
    ) -> str:
        try:
            return await self._primary.chat_complete(messages, temperature)
        except Exception as e:
            logger.warning("AI provider chat_complete 실패, mock으로 대체합니다. 원인: %s", e)
            return await self._fallback.chat_complete(messages, temperature)

    async def function_call(
        self,
        messages: list[ChatMessage],
        tools: list[dict],
        tool_choice: str = "auto",
    ) -> dict:
        try:
            return await self._primary.function_call(messages, tools, tool_choice)
        except Exception as e:
            logger.warning("AI provider function_call 실패, mock으로 대체합니다. 원인: %s", e)
            return await self._fallback.function_call(messages, tools, tool_choice)
