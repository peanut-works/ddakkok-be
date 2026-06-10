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
from sqlalchemy.orm import Session

from app.ai.base import AIProvider
from app.ai.embedding import EmbeddingProvider, get_embedding_provider
from app.ai.factory import get_ai_provider
from app.ai.knowledge_loader import KnowledgeLoader
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
from app.core.database import get_db
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
        knowledge_loader: KnowledgeLoader | None = None,
    ) -> None:
        self._preprocessor = preprocessor
        self._ocr = ocr
        self._parser = parser
        self._checker = checker
        self._explainer = explainer
        self._knowledge_loader = knowledge_loader

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

    async def analyze_from_text(
        self,
        ocr_text: str,
        children: list[ChildHealthProfile],
    ) -> PipelineResult:
        """OCR 텍스트 직접 입력 → PipelineResult. 이미지 없이 데모·테스트용.

        Step 1(이미지 전처리), Step 2(OCR)를 건너뛰고 Step 3(NER)부터 실행.

        Args:
            ocr_text:  이미 추출된 OCR 텍스트 (MockOCR 시나리오 등)
            children:  대조할 아동 건강 프로필 목록
        """
        logger.info("[Pipeline] analyze_from_text — NER부터 실행 (이미지·OCR 스킵)")

        ner_result = await self._parser.parse(ocr_text)
        logger.debug("[Pipeline] NER: product=%s ingredient=%d개",
                     ner_result.product, len(ner_result.ingredient))

        safety_report = self._run_checker(ner_result, children)
        logger.info("[Pipeline] 판정=%s", safety_report.overall_status)

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
        """판정 상태에 따라 LLM 설명 생성 또는 고정 문자열 반환.

        FAIL/WARN이고 knowledge_loader가 주입된 경우 RAG 컨텍스트를 LLM에 함께 전달한다.
        """
        status = report.overall_status

        if status == CheckStatus.EXPIRED:
            return _EXPLANATION_EXPIRED
        if status == CheckStatus.UNKNOWN:
            return _EXPLANATION_UNKNOWN

        # FAIL / WARN → RAG 검색 후 LLM 호출, PASS → RAG 생략
        rag_context: list[str] | None = None
        if self._knowledge_loader and status in (CheckStatus.FAIL, CheckStatus.WARN):
            rag_context = await self._fetch_rag_context(ner_result, report)

        explanation_input = ExplanationInput(
            status=_to_verdict(status),
            product=ner_result.product,
            ingredient=ner_result.ingredient,
            matched_rules=_collect_rule_descriptions(report),
        )
        return await self._explainer.generate(explanation_input, context=rag_context)

    async def _fetch_rag_context(
        self,
        ner_result: NERResult,
        report: ProductSafetyReport,
    ) -> list[str]:
        """성분명 + 규칙 설명으로 지식베이스를 검색해 관련 청크 텍스트를 반환한다.

        검색 실패 시 예외 없이 빈 리스트를 반환해 파이프라인이 중단되지 않도록 한다.
        """
        rule_descs = _collect_rule_descriptions(report)
        query = " ".join(ner_result.ingredient[:5] + rule_descs[:3])
        try:
            chunks = await self._knowledge_loader.search(query, top_k=3)
            return [f"[출처: {c.source}]\n{c.content}" for c in chunks]
        except Exception as exc:
            logger.warning("[Pipeline] RAG 검색 실패 — context 없이 진행: %s", exc)
            return []


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
    db: Session = Depends(get_db),
    embed_provider: EmbeddingProvider = Depends(get_embedding_provider),
    checker: RuleChecker = Depends(get_rule_checker),
) -> AnalysisPipeline:
    """FastAPI Depends 주입용 파이프라인 팩토리.

    AIProvider 하나를 NER(LabelParser)과 설명 생성(ExplanationGenerator) 모두에 공유.
    RuleChecker는 DB safety_rules / ingredient_aliases를 사용한다.
    KnowledgeLoader는 FAIL/WARN 판정 시 RAG 컨텍스트 검색에 사용한다.
    """
    return AnalysisPipeline(
        preprocessor=preprocessor,
        ocr=ocr,
        parser=LabelParser(provider=ai_provider),
        checker=checker,
        explainer=ExplanationGenerator(provider=ai_provider),
        knowledge_loader=KnowledgeLoader(db=db, embed_provider=embed_provider),
    )
