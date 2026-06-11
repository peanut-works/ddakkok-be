from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class ChildHealthProfileResponse(BaseModel):
    allergies: list[str] = Field(default_factory=list, examples=[["우유"]])
    skin_conditions: list[str] = Field(default_factory=list, examples=[["민감성 피부"]])
    sensitive_ingredients: list[str] = Field(default_factory=list, examples=[["향료", "에탄올"]])
    notes: str | None = Field(default=None, examples=["우유 및 우유 유래 성분 섭취·접촉 주의"])

    model_config = ConfigDict(from_attributes=True)


class ChildListItemResponse(BaseModel):
    id: int = Field(..., examples=[1])
    facility_id: int = Field(..., examples=[1])
    classroom_id: int = Field(..., examples=[1])
    name: str = Field(..., examples=["강민준"])
    birth_date: date | None = Field(default=None, examples=["2022-03-15"])
    gender: str | None = Field(default=None, examples=["M"])
    memo: str | None = Field(default=None, examples=["우유 알레르기 주의"])
    is_active: bool = Field(default=True, examples=[True])
    health_profile: ChildHealthProfileResponse | None = None

    model_config = ConfigDict(from_attributes=True)


class ChildDetailResponse(ChildListItemResponse):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "facility_id": 1,
                "classroom_id": 1,
                "name": "강민준",
                "birth_date": "2022-03-15",
                "gender": "M",
                "memo": "우유 알레르기 주의",
                "is_active": True,
                "health_profile": {
                    "allergies": ["우유"],
                    "skin_conditions": [],
                    "sensitive_ingredients": [],
                    "notes": "우유 및 우유 유래 성분 섭취·접촉 주의",
                },
            }
        },
    )
