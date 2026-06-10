from datetime import date

from pydantic import BaseModel, ConfigDict


class RecallAlertResponse(BaseModel):
    id: int
    product_name: str
    manufacturer: str | None = None
    category: str | None = None
    recall_date: date
    reason: str
    action_guide: str | None = None
    is_new: bool
    severity: str


class ExpiryAlertResponse(BaseModel):
    product_id: int
    product_name: str
    expiry_date: date
    alert_type: str
    message: str
    severity: str


class AttentionChildResponse(BaseModel):
    child_id: int
    child_name: str
    status: str
    status_label: str


class AttentionProductResponse(BaseModel):
    check_id: int
    product_id: int
    product_name: str
    overall_status: str
    status_label: str
    summary: str
    children: list[AttentionChildResponse]


class DashboardSummaryResponse(BaseModel):
    recall_alerts: list[RecallAlertResponse]
    expiry_alerts: list[ExpiryAlertResponse]
    attention_products: list[AttentionProductResponse]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "recall_alerts": [
                    {
                        "id": 1,
                        "product_name": "마이디데이 브로멜라인",
                        "manufacturer": "주식회사 피비에이치",
                        "category": "식품",
                        "recall_date": "2026-04-23",
                        "reason": "표시대상 알레르기 유발 원료성분(우유, 대두) 미표시",
                        "action_guide": "해당 제품은 섭취를 중단하고 구입처 또는 판매처에 반품하세요.",
                        "is_new": True,
                        "severity": "HIGH",
                    },
                    {
                        "id": 4,
                        "product_name": "올포홈 구르미 낮잠패드(쿠앤크)",
                        "manufacturer": "㈜올포홈리빙",
                        "category": "유아용 섬유제품",
                        "recall_date": "2026-05-21",
                        "reason": "폼알데하이드 기준치 초과",
                        "action_guide": "해당 제품은 사용을 중단하고 판매처 또는 사업자 안내에 따라 교환·환불 절차를 확인하세요.",
                        "is_new": True,
                        "severity": "HIGH",
                    },
                ],
                "expiry_alerts": [
                    {
                        "product_id": 108,
                        "product_name": "유통기한 지난 물티슈",
                        "expiry_date": "2025-06-01",
                        "alert_type": "EXPIRED",
                        "message": "유통기한이 만료된 제품입니다.",
                        "severity": "HIGH",
                    },
                    {
                        "product_id": 109,
                        "product_name": "임박한 베이비 로션",
                        "expiry_date": "2026-06-30",
                        "alert_type": "EXPIRING",
                        "message": "30일 이내 유통기한이 만료되는 제품입니다.",
                        "severity": "MEDIUM",
                    },
                ],
                "attention_products": [
                    {
                        "check_id": 35,
                        "product_id": 102,
                        "product_name": "밀크 프로틴 보습 물티슈",
                        "overall_status": "FAIL",
                        "status_label": "사용 보류",
                        "summary": "사용 보류 1명, 주의 필요 1명",
                        "children": [
                            {
                                "child_id": 1,
                                "child_name": "강민준",
                                "status": "FAIL",
                                "status_label": "사용 보류",
                            },
                            {
                                "child_id": 2,
                                "child_name": "김서아",
                                "status": "WARN",
                                "status_label": "주의 필요",
                            },
                        ],
                    }
                ],
            }
        }
    )
