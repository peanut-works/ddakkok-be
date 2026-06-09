from typing import Literal

from pydantic import BaseModel, Field

LoginMethod = Literal["FACILITY", "EMAIL", "DEMO"]


class LoginRequest(BaseModel):
    email: str = Field(..., examples=["teacher@ddakkok.com"])
    password: str = Field(..., min_length=1, examples=["ddakkok1234"])
    login_method: Literal["FACILITY", "EMAIL"] = Field(
        default="EMAIL",
        examples=["FACILITY"],
    )


class FacilityContext(BaseModel):
    id: int
    name: str
    facility_type: str


class ClassroomContext(BaseModel):
    id: int
    name: str
    age_group: str | None = None


class UserContext(BaseModel):
    id: int
    email: str
    name: str
    role: str
    facility: FacilityContext
    classroom: ClassroomContext | None = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    login_method: LoginMethod
    user: UserContext


class KakaoLoginRequest(BaseModel):
    code: str | None = Field(
        default=None,
        description="Kakao OAuth authorization code. Callback server setup 후 사용합니다.",
    )
