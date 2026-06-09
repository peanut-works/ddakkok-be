import json

from openai import AsyncOpenAI

from app.ai.base import AIProvider, ChatMessage


class OpenAIProvider(AIProvider):
    """OpenAI GPT-4o-mini 기반 provider."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        self._client = AsyncOpenAI(api_key=api_key)
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
        tools: list[dict],
        tool_choice: str = "auto",
    ) -> dict:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            tools=tools,
            tool_choice=tool_choice,
        )
        tool_call = response.choices[0].message.tool_calls[0]
        return json.loads(tool_call.function.arguments)
