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
                "product_name": "마이디데이 브로멜라인",
                "manufacturer": "주식회사 피비에이치",
                "category": "식품",
                "recall_date": "2026-04-23",
                "reason": "표시대상 알레르기 유발 원료성분(우유, 대두) 미표시",
                "action_guide": "해당 제품은 섭취를 중단하고 구입처 또는 판매처에 반품하세요.",
                "source": "Consumer24",
                "source_url": None,
            }
        },
    )
