from datetime import date

from pydantic import BaseModel, ConfigDict


class RecallNoticeResponse(BaseModel):
    id: int
    product_name: str
    manufacturer: str | None = None
    category: str | None = None
    recall_date: date
    reason: str
    action_guide: str | None = None
    source: str
    source_url: str | None = None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "product_name": "아토팜 리얼베리어 크림 100ml",
                "manufacturer": None,
                "category": "화장품",
                "recall_date": "2025-06-07",
                "reason": "기준치 초과 방부제 검출",
                "action_guide": "해당 제품을 구매한 소비자는 판매 또는 구입처에 반품하세요.",
                "source": "Consumer24",
                "source_url": None,
            }
        },
    )
