from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

LoginMethod = Literal["FACILITY", "EMAIL", "DEMO"]



class LoginRequest(BaseModel):
    email: str = Field(..., examples=["teacher@ddakkok.com"])
    password: str = Field(..., min_length=1, examples=["ddakkok1234"])
    login_method: Literal["FACILITY", "EMAIL"] = Field(
        default="EMAIL",
        examples=["FACILITY"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "teacher@ddakkok.com",
                "password": "ddakkok1234",
                "login_method": "FACILITY",
            }
        }
    )


class FacilityContext(BaseModel):
    id: int = Field(..., examples=[1])
    name: str = Field(..., examples=["땅콩어린이집"])
    facility_type: str = Field(..., examples=["DAYCARE"])


class ClassroomContext(BaseModel):
    id: int = Field(..., examples=[1])
    name: str = Field(..., examples=["햇님반"])
    age_group: str | None = Field(default=None, examples=["만 3세"])


class UserContext(BaseModel):
    id: int = Field(..., examples=[1])
    email: str = Field(..., examples=["teacher@ddakkok.com"])
    name: str = Field(..., examples=["김하늘"])
    role: str = Field(..., examples=["TEACHER"])
    facility: FacilityContext
    classroom: ClassroomContext | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1,
                "email": "teacher@ddakkok.com",
                "name": "김하늘",
                "role": "TEACHER",
                "facility": {
                    "id": 1,
                    "name": "땅콩어린이집",
                    "facility_type": "DAYCARE",
                },
                "classroom": {
                    "id": 1,
                    "name": "햇님반",
                    "age_group": "만 3세",
                },
            }
        }
    )


class AuthResponse(BaseModel):
    access_token: str = Field(..., examples=["mock-token:user:1"])
    token_type: str = Field(default="bearer", examples=["bearer"])
    login_method: LoginMethod = Field(..., examples=["FACILITY"])
    user: UserContext

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "mock-token:user:1",
                "token_type": "bearer",
                "login_method": "FACILITY",
                "user": {
                    "id": 1,
                    "email": "teacher@ddakkok.com",
                    "name": "김하늘",
                    "role": "TEACHER",
                    "facility": {
                        "id": 1,
                        "name": "땅콩어린이집",
                        "facility_type": "DAYCARE",
                    },
                    "classroom": {
                        "id": 1,
                        "name": "햇님반",
                        "age_group": "만 3세",
                    },
                },
            }
        }
    )


class KakaoLoginRequest(BaseModel):
    code: str | None = Field(
        default=None,
        description="Kakao OAuth authorization code. Callback server setup 후 사용합니다.",
        examples=["sample-kakao-authorization-code"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": "sample-kakao-authorization-code"
            }
        }
    )
