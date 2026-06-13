"""AI 관련 API 엔드포인트.

엔드포인트:
  GET  /api/ai/ping            — AI provider 연결 테스트
  POST /api/ai/analyze         — 제품 라벨 이미지 → 안전카드 + DB 저장
  GET  /api/ai/analyze/demo    — 시나리오 OCR 텍스트로 파이프라인 실행 (DB 저장 없음)
"""

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session, joinedload

from app.ai.base import AIProvider, ChatMessage
from app.ai.factory import get_ai_provider
from app.ai.ocr_mock_data import DEFAULT_OCR_SCENARIO, MOCK_OCR_RESULTS
from app.ai.pipeline import AnalysisPipeline, PipelineResult, get_analysis_pipeline
from app.ai.rule_checker import ChildHealthProfile as RuleCheckerProfile
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.models.child import Child
from app.models.classroom import Classroom
from app.models.product import Product
from app.models.safety_check import SafetyCheck, SafetyCheckResult
from app.schemas.ai import AiPingResponse
from app.schemas.error import ErrorResponse
from app.schemas.safety_card import ChildSafetyResult, MatchedRuleSummary, SafetyCardResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai", tags=["ai"])


# ── GET /ping ─────────────────────────────────────────────────────────────────


@router.get(
    "/ping",
    response_model=AiPingResponse,
    summary="AI provider connection check",
    responses={
        500: {
            "model": ErrorResponse,
            "description": "Internal server error",
        }
    },
)
async def ai_ping(
    provider: AIProvider = Depends(get_ai_provider),
    settings: Settings = Depends(get_settings),
) -> AiPingResponse:
    """AI provider 연결 테스트.

    - AI_PROVIDER=openai/gms: 실제 API 호출 (15초 timeout)
    - AI_PROVIDER=mock       : mock 응답 즉시 반환
    - 호출 실패 시            : FallbackAIProvider가 mock으로 자동 전환
    - 어떤 경우에도 200 + 정상 JSON 형식으로 응답 (시연 중단 없음)
    """
    messages = [
        ChatMessage(
            role="system",
            content="당신은 API 연결 테스트용 도우미입니다. 한 문장으로만 답하세요.",
        ),
        ChatMessage(
            role="user",
            content="연결 테스트입니다. '연결 성공'이라고만 답해주세요.",
        ),
    ]
    try:
        response = await provider.chat_complete(messages, temperature=0.0)
        return AiPingResponse(
            status="ok",
            provider=settings.ai_provider,
            response=response,
        )
    except Exception as e:
        logger.error("ai_ping 최종 예외 — provider=%s error=%s", settings.ai_provider, e)
        return AiPingResponse(
            status="fallback",
            provider=settings.ai_provider,
            response="AI 연결에 실패했습니다. Mock 응답으로 대체됩니다. GMS 키 혹은 서버 상태를 확인해주세요.",
        )


# ── POST /analyze ─────────────────────────────────────────────────────────────


@router.post("/analyze", response_model=SafetyCardResponse)
async def analyze_product(
    image: UploadFile = File(..., description="제품 라벨 이미지 (JPEG/PNG)"),
    classroom_id: int = Form(..., description="분석 대상 반 ID"),
    pipeline: AnalysisPipeline = Depends(get_analysis_pipeline),
    db: Session = Depends(get_db),
) -> SafetyCardResponse:
    """제품 라벨 이미지를 분석해 반 전체 아동의 안전카드를 반환한다.

    파이프라인:
        이미지 → 전처리 → OCR → NER → Rule Checker → LLM 설명 → DB 저장

    - classroom_id 반의 활성 아동 전원을 대조 대상으로 삼는다.
    - 어떤 단계가 실패해도 fallback으로 자동 전환되어 200 응답을 유지한다.
    - 결과는 SafetyCheck + SafetyCheckResult 테이블에 저장된다.
    """
    classroom, profiles, name_map = _fetch_children(db, classroom_id)

    image_bytes = await image.read()
    result = await pipeline.analyze(image_bytes, profiles)

    check = _save_to_db(db, result, classroom)
    return _build_response(result, name_map, check_id=check.id)


# ── GET /analyze/demo ─────────────────────────────────────────────────────────


@router.get("/analyze/demo", response_model=SafetyCardResponse)
async def analyze_demo(
    scenario: str = Query(
        DEFAULT_OCR_SCENARIO,
        description="시나리오: wipes (FAIL) / lotion (WARN) / sunscreen (PASS)",
    ),
    classroom_id: int = Query(1, description="분석 대상 반 ID (DB에 존재해야 함)"),
    pipeline: AnalysisPipeline = Depends(get_analysis_pipeline),
    db: Session = Depends(get_db),
) -> SafetyCardResponse:
    """이미지 없이 시나리오 OCR 텍스트로 전체 파이프라인을 실행한다. DB 저장 없음.

    현장 시연 시 이미지 촬영 없이 안전카드 흐름을 빠르게 보여줄 때 사용.
    classroom_id 반의 실제 아동 데이터를 그대로 사용하므로 시연 현실감이 높다.
    """
    _, profiles, name_map = _fetch_children(db, classroom_id)

    ocr_text = MOCK_OCR_RESULTS.get(scenario, MOCK_OCR_RESULTS[DEFAULT_OCR_SCENARIO])
    result = await pipeline.analyze_from_text(ocr_text, profiles)

    return _build_response(result, name_map, check_id=None)


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────


def _fetch_children(
    db: Session,
    classroom_id: int,
) -> tuple[Classroom, list[RuleCheckerProfile], dict[int, str]]:
    """반 ID로 Classroom + 활성 아동 건강 프로필을 조회한다.

    Raises:
        HTTPException 404: 반 ID가 존재하지 않는 경우
    """
    classroom = db.get(Classroom, classroom_id)
    if classroom is None:
        raise HTTPException(status_code=404, detail=f"반 ID {classroom_id}를 찾을 수 없습니다.")

    children = (
        db.query(Child)
        .filter(Child.classroom_id == classroom_id, Child.is_active.is_(True))
        .options(joinedload(Child.health_profile))
        .all()
    )

    profiles: list[RuleCheckerProfile] = []
    name_map: dict[int, str] = {}

    for child in children:
        name_map[child.id] = child.name
        hp = child.health_profile
        profiles.append(RuleCheckerProfile(
            child_id=child.id,
            allergies=hp.allergies if hp else [],
            skin_conditions=hp.skin_conditions if hp else [],
            sensitive_ingredients=hp.sensitive_ingredients if hp else [],
        ))

    return classroom, profiles, name_map


def _save_to_db(
    db: Session,
    result: PipelineResult,
    classroom: Classroom,
) -> SafetyCheck:
    """파이프라인 결과를 Product → SafetyCheck → SafetyCheckResult 순으로 저장한다."""
    ner = result.ner_result
    report = result.safety_report

    product = Product(
        facility_id=classroom.facility_id,
        name=ner.product or "알 수 없는 제품",
        category="기타",
        manufacturer=ner.maker or None,
        raw_ingredients_text=result.ocr_text,
        ingredients=ner.ingredient,
        normalized_ingredients=ner.ingredient,
        ocr_raw_text=result.ocr_text,
    )
    db.add(product)
    db.flush()

    check = SafetyCheck(
        facility_id=classroom.facility_id,
        product_id=product.id,
        classroom_id=classroom.id,
        overall_status=report.overall_status,
        pass_count=report.pass_count,
        warn_count=report.warn_count,
        fail_count=report.fail_count,
        expired_count=report.expired_count,
        unknown_count=report.unknown_count,
    )
    db.add(check)
    db.flush()

    for child_result in report.child_results:
        primary = (
            max(child_result.matched_rules, key=lambda r: r.status.severity_rank())
            if child_result.matched_rules
            else None
        )
        db.add(SafetyCheckResult(
            safety_check_id=check.id,
            child_id=child_result.child_id,
            status=child_result.status,
            matched_rule_code=primary.rule_code if primary else None,
            matched_ingredient=primary.matched_ingredient if primary else None,
            reason=child_result.reason,
            explanation=result.explanation,
        ))

    db.commit()
    db.refresh(check)
    return check


def _build_response(
    result: PipelineResult,
    name_map: dict[int, str],
    check_id: int | None,
) -> SafetyCardResponse:
    """PipelineResult → SafetyCardResponse 변환."""
    report = result.safety_report
    return SafetyCardResponse(
        check_id=check_id,
        product_name=report.product_name,
        overall_status=report.overall_status,
        pass_count=report.pass_count,
        warn_count=report.warn_count,
        fail_count=report.fail_count,
        expired_count=report.expired_count,
        unknown_count=report.unknown_count,
        child_results=[
            ChildSafetyResult(
                child_id=cr.child_id,
                child_name=name_map.get(cr.child_id, f"아동 {cr.child_id}"),
                status=cr.status,
                matched_rules=[
                    MatchedRuleSummary(
                        rule_code=r.rule_code,
                        status=r.status,
                        matched_ingredient=r.matched_ingredient,
                        reason=r.reason,
                    )
                    for r in cr.matched_rules
                ],
                reason=cr.reason,
            )
            for cr in report.child_results
        ],
        explanation=result.explanation,
        ocr_text=result.ocr_text,
    )
