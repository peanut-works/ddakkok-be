from pydantic import BaseModel, ConfigDict


class AiPingResponse(BaseModel):
    status: str
    provider: str
    response: str

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "status": "ok",
                    "provider": "mock",
                    "response": "연결 성공",
                },
                {
                    "status": "fallback",
                    "provider": "openai",
                    "response": "AI 연결에 실패했습니다. Mock 응답으로 대체됩니다.",
                },
            ]
        }
    )
