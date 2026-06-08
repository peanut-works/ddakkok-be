from app.services.ai.base import AIProvider, ChatMessage


class GMSProvider(AIProvider):
    """GMS(Google Model Service) 기반 provider. 인터페이스 정의만, 미구현."""

    def __init__(self, api_key: str, api_url: str, model: str) -> None:
        self._api_key = api_key
        self._api_url = api_url
        self._model = model

    async def chat_complete(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.3,
    ) -> str:
        raise NotImplementedError("GMS provider는 아직 구현되지 않았습니다.")

    async def function_call(
        self,
        messages: list[ChatMessage],
        tools: list[dict],
        tool_choice: str = "auto",
    ) -> dict:
        raise NotImplementedError("GMS provider는 아직 구현되지 않았습니다.")
