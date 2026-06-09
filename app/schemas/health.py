from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    status: str
    message: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "ok",
                "message": "Ddakkok API is running",
            }
        }
    )


class DatabaseHealthResponse(BaseModel):
    status: str
    database: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "ok",
                "database": "connected",
            }
        }
    )
