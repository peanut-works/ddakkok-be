"""파이프라인 오케스트레이터 — 이미지 1장 → 안전 판정 + 교사용 설명 전 과정.

파이프라인 순서:
    Step 1: ImagePreprocessor  — 기울기·원근·곡면·주름·조도 보정
    Step 2: OCRProvider        — 텍스트 추출
    Step 3: LabelParser (NER)  — 성분·유통기한·제품명 파싱
    Step 4: RuleChecker        — 아동 건강 프로필 × 성분 대조
    Step 5: ExplanationGenerator — 교사용 한국어 설명 생성

독립 실패 허용 원칙:
    - Step 1 실패  → 원본 이미지 그대로 사용 (ImagePreprocessor 내부 처리)
    - Step 2 실패  → FallbackOCRProvider 가 mock 텍스트로 자동 전환
    - Step 3/5 실패 → FallbackAIProvider 가 mock 응답으로 자동 전환
    - Step 4 예외  → 전체 아동 UNKNOWN 보고서 반환
    - Step 5 EXPIRED/UNKNOWN → LLM 불호출, 고정 설명 문자열 반환
"""

import logging
from typing import Literal

from fastapi import Depends
from pydantic import BaseModel

from app.ai.base import AIProvider
from app.ai.factory import get_ai_provider
from app.ai.llm import ExplanationGenerator, ExplanationInput
from app.ai.ner import LabelParser, NERResult
from app.ai.ocr import OCRProvider, get_ocr_provider
from app.ai.rule_checker import (
    CheckStatus,
    ChildCheckResult,
    ChildHealthProfile,
    MatchedRule,
    ProductSafetyReport,
    RuleChecker,
    get_rule_checker,
)
from app.services.image_processing import ImagePreprocessor, get_image_preprocessor

logger = logging.getLogger(__name__)

# ── 고정 설명 (EXPIRED / UNKNOWN 은 LLM 호출 불필요) ─────────────────────────────

_EXPLANATION_EXPIRED = (
    "이 제품은 유통기한이 지났습니다.\n\n"
    "⏰ 요약: 유통기한 만료\n"
    "만료된 제품은 품질이 저하되거나 안전하지 않을 수 있습니다.\n\n"
    "보호자 또는 관리자 확인 후 즉시 폐기를 권장합니다."
)

_EXPLANATION_UNKNOWN = (
    "제품 성분표를 확인할 수 없어 안전 여부를 판단할 수 없습니다.\n\n"
    "❓ 요약: 성분 확인 불가\n"
    "OCR 인식에 실패하거나 성분표가 훼손된 경우입니다.\n\n"
    "교사 판단 하에 사용 여부를 결정하고, 불확실한 경우 사용을 보류해 주세요."
)

# ── 결과 모델 ─────────────────────────────────────────────────────────────────


class PipelineResult(BaseModel):
    """파이프라인 전체 실행 결과.

    Attributes:
        ocr_text:      Step 2 OCR 원문 (디버그·감사 로그용)
        ner_result:    Step 3 NER 파싱 결과
        safety_report: Step 4 Rule Checker 결과
        explanation:   Step 5 교사용 설명 텍스트
    """

    ocr_text: str
    ner_result: NERResult
    safety_report: ProductSafetyReport
    explanation: str


# ── 파이프라인 ────────────────────────────────────────────────────────────────


class AnalysisPipeline:
    """이미지 bytes → PipelineResult 전 과정 오케스트레이터.

    사용 예::

        pipeline = get_analysis_pipeline(...)
        result = await pipeline.analyze(image_bytes, children)
        # result.safety_report.overall_status → "FAIL"
        # result.explanation                  → "이 제품은 우유 알레르기..."
    """

    def __init__(
        self,
        preprocessor: ImagePreprocessor,
        ocr: OCRProvider,
        parser: LabelParser,
        checker: RuleChecker,
        explainer: ExplanationGenerator,
    ) -> None:
        self._preprocessor = preprocessor
        self._ocr = ocr
        self._parser = parser
        self._checker = checker
        self._explainer = explainer

    # ── Public ────────────────────────────────────────────────────────────────

    async def analyze(
        self,
        image: bytes,
        children: list[ChildHealthProfile],
    ) -> PipelineResult:
        """이미지 + 아동 프로필 목록 → PipelineResult.

        Args:
            image:    원본 이미지 bytes (JPEG 권장)
            children: 대조할 아동 건강 프로필 목록
        """
        # Step 1: 이미지 전처리
        logger.info("[Pipeline] Step 1 — 이미지 전처리")
        clean_image = await self._preprocessor.preprocess(image)

        # Step 2: OCR
        logger.info("[Pipeline] Step 2 — OCR")
        ocr_text = await self._ocr.extract_text(clean_image)
        logger.debug("[Pipeline] OCR 결과 길이=%d", len(ocr_text))

        # Step 3: NER
        logger.info("[Pipeline] Step 3 — NER")
        ner_result = await self._parser.parse(ocr_text)
        logger.debug("[Pipeline] NER: product=%s ingredient=%d개",
                     ner_result.product, len(ner_result.ingredient))

        # Step 4: Rule Checker
        logger.info("[Pipeline] Step 4 — Rule Checker")
        safety_report = self._run_checker(ner_result, children)
        logger.info(
            "[Pipeline] 판정=%s (FAIL=%d WARN=%d PASS=%d EXPIRED=%d UNKNOWN=%d)",
            safety_report.overall_status,
            safety_report.fail_count,
            safety_report.warn_count,
            safety_report.pass_count,
            safety_report.expired_count,
            safety_report.unknown_count,
        )

        # Step 5: LLM 설명
        logger.info("[Pipeline] Step 5 — 설명 생성")
        explanation = await self._generate_explanation(ner_result, safety_report)

        return PipelineResult(
            ocr_text=ocr_text,
            ner_result=ner_result,
            safety_report=safety_report,
            explanation=explanation,
        )

    # ── Internal ──────────────────────────────────────────────────────────────

    def _run_checker(
        self,
        ner_result: NERResult,
        children: list[ChildHealthProfile],
    ) -> ProductSafetyReport:
        """Rule Checker 실행. 예외 시 전체 UNKNOWN 보고서 반환."""
        try:
            return self._checker.check(ner_result, children)
        except Exception as exc:
            logger.error("[Pipeline] Rule Checker 오류 — UNKNOWN 반환: %s", exc)
            return _make_unknown_report(
                product_name=ner_result.product or "알 수 없는 제품",
                child_ids=[c.child_id for c in children],
            )

    async def _generate_explanation(
        self,
        ner_result: NERResult,
        report: ProductSafetyReport,
    ) -> str:
        """판정 상태에 따라 LLM 설명 생성 또는 고정 문자열 반환."""
        status = report.overall_status

        if status == CheckStatus.EXPIRED:
            return _EXPLANATION_EXPIRED
        if status == CheckStatus.UNKNOWN:
            return _EXPLANATION_UNKNOWN

        # PASS / WARN / FAIL → LLM 호출
        explanation_input = ExplanationInput(
            status=_to_verdict(status),
            product=ner_result.product,
            ingredient=ner_result.ingredient,
            matched_rules=_collect_rule_descriptions(report),
        )
        return await self._explainer.generate(explanation_input)


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────


def _to_verdict(status: CheckStatus) -> Literal["PASS", "WARN", "FAIL"]:
    """CheckStatus → ExplanationInput.status Literal 변환."""
    table: dict[CheckStatus, Literal["PASS", "WARN", "FAIL"]] = {
        CheckStatus.PASS: "PASS",
        CheckStatus.WARN: "WARN",
        CheckStatus.FAIL: "FAIL",
    }
    return table.get(status, "FAIL")


def _collect_rule_descriptions(report: ProductSafetyReport) -> list[str]:
    """모든 아동 결과에서 고유 규칙 설명 목록 수집 (LLM 컨텍스트용)."""
    seen: set[str] = set()
    descriptions: list[str] = []
    for child_result in report.child_results:
        for rule in child_result.matched_rules:
            desc = (
                f"{rule.matched_ingredient} — {rule.reason}"
                if rule.matched_ingredient
                else rule.reason
            )
            if desc not in seen:
                seen.add(desc)
                descriptions.append(desc)
    return descriptions


def _make_unknown_report(
    product_name: str,
    child_ids: list[int],
) -> ProductSafetyReport:
    """Rule Checker 예외 시 전체 UNKNOWN 보고서 생성."""
    unknown_rule = MatchedRule(
        rule_code="OCR_UNKNOWN_001",
        status=CheckStatus.UNKNOWN,
        matched_ingredient="",
        reason="성분표를 확인할 수 없어 안전 여부를 판단할 수 없습니다.",
    )
    child_results = [
        ChildCheckResult(
            child_id=cid,
            status=CheckStatus.UNKNOWN,
            matched_rules=[unknown_rule],
            reason="시스템 오류로 안전 여부를 판단할 수 없습니다.",
        )
        for cid in child_ids
    ]
    return ProductSafetyReport(
        product_name=product_name,
        overall_status=CheckStatus.UNKNOWN,
        child_results=child_results,
        unknown_count=len(child_ids),
    )


# ── 팩토리 ───────────────────────────────────────────────────────────────────


def get_analysis_pipeline(
    preprocessor: ImagePreprocessor = Depends(get_image_preprocessor),
    ocr: OCRProvider = Depends(get_ocr_provider),
    ai_provider: AIProvider = Depends(get_ai_provider),
) -> AnalysisPipeline:
    """FastAPI Depends 주입용 파이프라인 팩토리.

    AIProvider 하나를 NER(LabelParser)과 설명 생성(ExplanationGenerator) 모두에 공유.
    """
    return AnalysisPipeline(
        preprocessor=preprocessor,
        ocr=ocr,
        parser=LabelParser(provider=ai_provider),
        checker=get_rule_checker(),
        explainer=ExplanationGenerator(provider=ai_provider),
    )
