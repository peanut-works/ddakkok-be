from typing import Any

from app.ai.base import AIProvider, ChatMessage
from app.ai.mock_data import MOCK_EXPLANATIONS, MOCK_FUNCTION_CALL_RESULT


def _detect_status(messages: list[ChatMessage]) -> str:
    """메시지 내용에서 판정 키워드를 감지해 시나리오를 결정한다."""
    combined = " ".join(m.content for m in messages if m.role == "user").upper()
    if "FAIL" in combined:
        return "FAIL"
    if "EXPIRED" in combined:
        return "EXPIRED"
    if "WARN" in combined:
        return "WARN"
    if "UNKNOWN" in combined:
        return "UNKNOWN"
    if "PASS" in combined:
        return "PASS"
    return "FAIL"  # 기본값: 가장 정보량이 많은 FAIL 예시


class MockAIProvider(AIProvider):
    """테스트·시연용 mock provider. 외부 API 없이 판정별 고정 설명을 반환한다."""

    async def chat_complete(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.3,
    ) -> str:
        status = _detect_status(messages)
        return MOCK_EXPLANATIONS[status]

    async def function_call(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]],
        tool_choice: str | dict[str, Any] = "auto",
    ) -> dict[str, Any]:
        return MOCK_FUNCTION_CALL_RESULT
