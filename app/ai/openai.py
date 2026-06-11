import json
from typing import Any

from openai import AsyncOpenAI

from app.ai.base import AIProvider, ChatMessage

_DEFAULT_TIMEOUT = 30.0  # 초. 제품 라벨 구조화 응답 대기용


class OpenAIProvider(AIProvider):
    """OpenAI provider."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        timeout: float = _DEFAULT_TIMEOUT,
        base_url: str | None = None,
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout, base_url=base_url)
        self._model = model

    async def chat_complete(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.3,
    ) -> str:
        request_kwargs = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }

        # gpt-5 계열은 temperature를 명시적으로 넘기지 않음
        if not self._model.startswith("gpt-5"):
            request_kwargs["temperature"] = temperature

        response = await self._client.chat.completions.create(**request_kwargs)
        return response.choices[0].message.content or ""

    async def function_call(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]],
        tool_choice: str | dict[str, Any] = "auto",
    ) -> dict[str, Any]:
        request_kwargs = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "tools": tools,
            "tool_choice": tool_choice,
        }
        response = await self._client.chat.completions.create(**request_kwargs)
        tool_call = response.choices[0].message.tool_calls[0]
        result: dict[str, Any] = json.loads(tool_call.function.arguments)
        return result
