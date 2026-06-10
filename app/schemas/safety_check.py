from datetime import date

from pydantic import BaseModel, Field


class SafetyCheckCreateRequest(BaseModel):
    product_id: int = Field(..., examples=[102])
    classroom_id: int = Field(..., examples=[1])
    child_ids: list[int] = Field(..., min_length=1, examples=[[1, 3]])


class MatchedRuleResponse(BaseModel):
    rule_code: str
    status: str
    matched_ingredient: str
    reason: str


class SafetyCheckChildResultResponse(BaseModel):
    child_id: int
    child_name: str
    status: str
    matched_rules: list[MatchedRuleResponse]

    # 기존 응답 호환용 대표 매칭값
    matched_rule_code: str | None = None
    matched_profile: str | None = None
    matched_ingredient: str | None = None
    reason: str


class SafetyCheckResponse(BaseModel):
    id: int
    product_id: int
    product_name: str
    classroom_id: int
    overall_status: str
    pass_count: int
    warn_count: int
    fail_count: int
    expired_count: int
    unknown_count: int
    results: list[SafetyCheckChildResultResponse]


class SafetyCheckProductResponse(BaseModel):
    id: int
    name: str
    category: str
    manufacturer: str | None = None
    barcode: str | None = None
    expiry_date: date | None = None
    ingredients: list[str] = Field(default_factory=list)
    normalized_ingredients: list[str] = Field(default_factory=list)


class SafetyCheckSummaryResponse(BaseModel):
    overall_status: str
    pass_count: int
    warn_count: int
    fail_count: int
    expired_count: int
    unknown_count: int
    total_count: int


class SafetyCheckDetailChildResultResponse(BaseModel):
    child_id: int
    child_name: str
    status: str
    matched_rule_code: str | None = None
    matched_profile: str | None = None
    matched_ingredient: str | None = None
    reason: str | None = None
    explanation: str | None = None


class SafetyCheckDetailResponse(BaseModel):
    id: int
    product: SafetyCheckProductResponse
    classroom_id: int
    summary: SafetyCheckSummaryResponse
    results: list[SafetyCheckDetailChildResultResponse]
    overall_explanation: str | None = None