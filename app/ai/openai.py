import json
from typing import Any

from openai import AsyncOpenAI

from app.ai.base import AIProvider, ChatMessage

_DEFAULT_TIMEOUT = 15.0  # 초. 시연 중 hang 방지용


class OpenAIProvider(AIProvider):
    """OpenAI 호환 chat completions provider.

    base_url을 지정하면 Groq 등 OpenAI 호환 API에도 그대로 사용할 수 있다.
    """

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
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=temperature,
        )
        return response.choices[0].message.content or ""

    async def function_call(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]],
        tool_choice: str | dict[str, Any] = "auto",
    ) -> dict[str, Any]:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            tools=tools,
            tool_choice=tool_choice,
        )
        tool_call = response.choices[0].message.tool_calls[0]
        result: dict[str, Any] = json.loads(tool_call.function.arguments)
        return result
