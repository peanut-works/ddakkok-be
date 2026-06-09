from pydantic import BaseModel, ConfigDict


class RootResponse(BaseModel):
    message: str
    docs: str
    health: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "Ddakkok API",
                "docs": "/docs",
                "health": "/api/health",
            }
        }
    )
