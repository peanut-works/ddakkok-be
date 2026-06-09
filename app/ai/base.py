from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str  # "system" | "user" | "assistant"
    content: str


class AIProvider(ABC):
    """LLM 호출 추상 인터페이스. 모든 provider가 구현해야 한다."""

    @abstractmethod
    async def chat_complete(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.3,
    ) -> str:
        """메시지 목록을 받아 assistant 응답 텍스트를 반환한다."""

    @abstractmethod
    async def function_call(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]],
        tool_choice: str | dict[str, Any] = "auto",
    ) -> dict[str, Any]:
        """Function Calling을 수행하고 파싱된 arguments dict를 반환한다."""
