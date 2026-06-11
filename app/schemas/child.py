from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.classroom import ClassroomResponse


class ChildHealthProfileResponse(BaseModel):
    allergies: list[str] = Field(default_factory=list, examples=[["milk"]])
    skin_conditions: list[str] = Field(default_factory=list, examples=[["sensitive-skin"]])
    sensitive_ingredients: list[str] = Field(
        default_factory=list,
        examples=[["fragrance", "ethanol"]],
    )
    notes: str | None = Field(
        default=None,
        examples=["Avoid products derived from milk proteins."],
    )

    model_config = ConfigDict(from_attributes=True)


class ChildListItemResponse(BaseModel):
    id: int = Field(..., examples=[1])
    facility_id: int = Field(..., examples=[1])
    classroom_id: int = Field(..., examples=[1])
    name: str = Field(..., examples=["Minjun Kang"])
    birth_date: date | None = Field(default=None, examples=["2022-03-15"])
    gender: str | None = Field(default=None, examples=["M"])
    memo: str | None = Field(default=None, examples=["Milk allergy caution"])
    is_active: bool = Field(default=True, examples=[True])

    model_config = ConfigDict(from_attributes=True)


class ChildDetailResponse(ChildListItemResponse):
    health_profile: ChildHealthProfileResponse | None = None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "facility_id": 1,
                "classroom_id": 1,
                "name": "Minjun Kang",
                "birth_date": "2022-03-15",
                "gender": "M",
                "memo": "Milk allergy caution",
                "is_active": True,
                "health_profile": {
                    "allergies": ["milk"],
                    "skin_conditions": [],
                    "sensitive_ingredients": [],
                    "notes": "Avoid products derived from milk proteins.",
                },
            }
        },
    )


class ClassroomChildrenResponse(BaseModel):
    classroom: ClassroomResponse
    total_count: int = Field(..., examples=[4])
    children: list[ChildListItemResponse] = Field(default_factory=list)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "classroom": {
                    "id": 1,
                    "facility_id": 1,
                    "name": "Class A",
                    "age_group": "Age 3",
                },
                "total_count": 4,
                "children": [
                    {
                        "id": 1,
                        "facility_id": 1,
                        "classroom_id": 1,
                        "name": "Minjun Kang",
                        "birth_date": "2022-03-15",
                        "gender": "M",
                        "memo": "Milk allergy caution",
                        "is_active": True,
                    }
                ],
            }
        }
    )
