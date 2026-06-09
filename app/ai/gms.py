"""GMS(Google Model Service) AI provider.

현장에서 GMS_API_KEY / GMS_API_URL / GMS_MODEL을 받으면
.env만 수정하고 AI_PROVIDER=gms로 바꾸면 바로 연결된다.

# 현장 연결 체크리스트
# 1. .env 에 아래 세 값 입력
#      GMS_API_KEY=<발급받은 키>
#      GMS_API_URL=<엔드포인트 URL>   예) https://gms.example.com/v1
#      GMS_MODEL=<모델명>              예) gms-pro
# 2. AI_PROVIDER=gms 로 변경
# 3. docker compose restart backend
# 4. GET /api/ai/ping 으로 연결 확인
#
# GMS API 스펙 미확정 항목 (현장에서 확인 후 TODO 제거):
#   - 인증 헤더 이름 (현재: Authorization: Bearer)
#   - chat completions 엔드포인트 경로 (현재: /chat/completions)
#   - 응답 JSON 필드 경로 (현재: choices[0].message.content)
#   - function calling 지원 여부 및 형식
"""

import json
import logging

import httpx

from app.ai.base import AIProvider, ChatMessage

logger = logging.getLogger(__name__)

# GMS API가 OpenAI 호환 형식을 사용한다고 가정.
# 스펙 확인 후 경로·필드명 수정 필요.
_CHAT_PATH = "/chat/completions"  # TODO: GMS 실제 경로로 교체
_DEFAULT_TIMEOUT = 15.0  # 초. OpenAIProvider와 통일


class GMSProvider(AIProvider):
    """GMS 기반 AI provider.

    GMS API 스펙이 확정되지 않아 OpenAI 호환 형식을 가정한다.
    현장에서 스펙 확인 후 TODO 항목을 수정하면 동작한다.
    호출 실패 시 FallbackAIProvider가 mock으로 자동 전환한다.
    """

    def __init__(self, api_key: str, api_url: str, model: str) -> None:
        self._api_key = api_key
        self._api_url = api_url.rstrip("/")
        self._model = model

    def _build_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",  # TODO: GMS 인증 헤더 확인
            "Content-Type": "application/json",
        }

    async def chat_complete(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.3,
    ) -> str:
        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
        }
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            response = await client.post(
                f"{self._api_url}{_CHAT_PATH}",
                headers=self._build_headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            # TODO: GMS 응답 구조 확인 후 필드 경로 수정
            return data["choices"][0]["message"]["content"]

    async def function_call(
        self,
        messages: list[ChatMessage],
        tools: list[dict],
        tool_choice: str = "auto",
    ) -> dict:
        # TODO: GMS function calling 지원 여부 확인
        #   - 지원한다면: OpenAI와 동일한 tools 파라미터 전달
        #   - 지원 안 한다면: JSON 출력 프롬프트로 대체 후 파싱
        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "tools": tools,
            "tool_choice": tool_choice,
        }
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            response = await client.post(
                f"{self._api_url}{_CHAT_PATH}",
                headers=self._build_headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            # TODO: GMS function call 응답 구조 확인 후 파싱 로직 수정
            tool_call = data["choices"][0]["message"]["tool_calls"][0]
            return json.loads(tool_call["function"]["arguments"])
