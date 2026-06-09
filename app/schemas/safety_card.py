"""안전카드 API 응답 스키마."""

from pydantic import BaseModel


class MatchedRuleSummary(BaseModel):
    """아동 1명에게 매칭된 규칙 1건 요약."""

    rule_code: str
    status: str
    matched_ingredient: str
    reason: str


class ChildSafetyResult(BaseModel):
    """아동 1명의 안전 판정 결과."""

    child_id: int
    child_name: str
    status: str
    matched_rules: list[MatchedRuleSummary]
    reason: str


class SafetyCardResponse(BaseModel):
    """안전카드 API 전체 응답.

    Attributes:
        check_id:       DB에 저장된 SafetyCheck ID. 데모 모드(GET /analyze/demo)는 None.
        product_name:   NER로 추출된 제품명
        overall_status: 전체 판정 (PASS / WARN / FAIL / EXPIRED / UNKNOWN)
        child_results:  아동별 상세 판정
        explanation:    교사용 설명 텍스트
        ocr_text:       OCR 원문 (디버그·감사용)
    """

    check_id: int | None = None
    product_name: str
    overall_status: str
    pass_count: int = 0
    warn_count: int = 0
    fail_count: int = 0
    expired_count: int = 0
    unknown_count: int = 0
    child_results: list[ChildSafetyResult]
    explanation: str
    ocr_text: str
