from pydantic import BaseModel, ConfigDict


from pydantic import BaseModel, ConfigDict, Field


class ClassroomResponse(BaseModel):
    id: int = Field(..., examples=[1])
    facility_id: int = Field(..., examples=[1])
    name: str = Field(..., examples=["햇님반"])
    age_group: str | None = Field(None, examples=["만 3세"])

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "facility_id": 1,
                "name": "햇님반",
                "age_group": "만 3세",
            }
        },
    )