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

        # 구조화 추출(NER)은 결정론적이어야 한다 — 같은 OCR 텍스트면 항상 같은 결과.
        # temperature=0 고정. (gpt-5 계열은 temperature 미지원이라 생략.)
        if not self._model.startswith("gpt-5"):
            request_kwargs["temperature"] = 0.0

        response = await self._client.chat.completions.create(**request_kwargs)
        message = response.choices[0].message
        if not message.tool_calls:
            # 모델이 tool call을 반환하지 않으면 예외를 올려 상위 FallbackAIProvider가
            # mock 응답으로 전환하게 한다(조용한 None 역참조 크래시 방지).
            raise ValueError("function_call: 모델이 tool call을 반환하지 않았습니다")
        tool_call = message.tool_calls[0]
        result: dict[str, Any] = json.loads(tool_call.function.arguments)
        return result
