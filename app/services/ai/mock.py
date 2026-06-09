import json

from app.services.ai.base import AIProvider, ChatMessage


class MockAIProvider(AIProvider):
    """테스트용 mock provider. 외부 API 없이 고정 응답을 반환한다."""

    async def chat_complete(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.3,
    ) -> str:
        return "[mock] 이 제품은 테스트 응답입니다."

    async def function_call(
        self,
        messages: list[ChatMessage],
        tools: list[dict],
        tool_choice: str = "auto",
    ) -> dict:
        return {
            "product": "mock 제품",
            "ingredient": ["정제수", "글리세린"],
            "expiry": "2027-01-01",
            "maker": "mock 제조사",
        }
