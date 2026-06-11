"""AnalysisPipeline 단위 테스트.

하위 컴포넌트(ImagePreprocessor / OCRProvider / LabelParser / RuleChecker /
ExplanationGenerator)는 모두 Mock으로 대체하여 파이프라인 오케스트레이션
로직만 검증한다. 각 컴포넌트 자체 로직은 전용 테스트에서 커버.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.llm import ExplanationInput
from app.ai.ner import NERResult
from app.ai.pipeline import (
    _EXPLANATION_EXPIRED,
    _EXPLANATION_UNKNOWN,
    AnalysisPipeline,
    PipelineResult,
    _collect_rule_descriptions,
    _make_unknown_report,
    _to_verdict,
)
from app.ai.rule_checker import (
    CheckStatus,
    ChildCheckResult,
    ChildHealthProfile,
    MatchedRule,
    ProductSafetyReport,
)

# ── 공통 상수 ─────────────────────────────────────────────────────────────────

IMAGE_BYTES = b"fake-image"
CLEAN_BYTES = b"clean-image"
OCR_TEXT = "제품명: 아기 물티슈\n성분: 정제수, 글리세린\n유통기한: 2027-12-31"

CHILD_A = ChildHealthProfile(child_id=1, allergies=["우유"])
CHILD_B = ChildHealthProfile(child_id=2)

NER_CLEAN = NERResult(
    product="아기 물티슈",
    ingredient=["정제수", "글리세린"],
    expiry="2027-12-31",
)

# ── 보고서 픽스처 ─────────────────────────────────────────────────────────────

_PASS_RULE = ChildCheckResult(child_id=1, status=CheckStatus.PASS, matched_rules=[], reason="이상 없음")

REPORT_PASS = ProductSafetyReport(
    product_name="아기 물티슈",
    overall_status=CheckStatus.PASS,
    child_results=[_PASS_RULE],
    pass_count=1,
)

REPORT_FAIL = ProductSafetyReport(
    product_name="밀크 로션",
    overall_status=CheckStatus.FAIL,
    child_results=[
        ChildCheckResult(
            child_id=1,
            status=CheckStatus.FAIL,
            matched_rules=[
                MatchedRule(
                    rule_code="ALLERGY_MILK_001",
                    status=CheckStatus.FAIL,
                    matched_ingredient="카제인나트륨",
                    reason="우유 알레르기 관련 성분입니다.",
                )
            ],
            reason="우유 알레르기 관련 성분 포함",
        ),
    ],
    fail_count=1,
)

REPORT_WARN = ProductSafetyReport(
    product_name="향기 로션",
    overall_status=CheckStatus.WARN,
    child_results=[
        ChildCheckResult(
            child_id=1,
            status=CheckStatus.WARN,
            matched_rules=[
                MatchedRule(
                    rule_code="SKIN_SENSITIVE_001",
                    status=CheckStatus.WARN,
                    matched_ingredient="향료",
                    reason="민감성 피부 주의 성분입니다.",
                )
            ],
            reason="민감성 피부 주의",
        )
    ],
    warn_count=1,
)

REPORT_EXPIRED = ProductSafetyReport(
    product_name="만료 제품",
    overall_status=CheckStatus.EXPIRED,
    child_results=[
        ChildCheckResult(
            child_id=1,
            status=CheckStatus.EXPIRED,
            matched_rules=[
                MatchedRule(
                    rule_code="EXPIRY_DATE_001",
                    status=CheckStatus.EXPIRED,
                    matched_ingredient="",
                    reason="유통기한 만료",
                )
            ],
            reason="유통기한 만료",
        )
    ],
    expired_count=1,
)

REPORT_UNKNOWN = ProductSafetyReport(
    product_name="성분 불명",
    overall_status=CheckStatus.UNKNOWN,
    child_results=[
        ChildCheckResult(child_id=1, status=CheckStatus.UNKNOWN, matched_rules=[], reason="성분 불명")
    ],
    unknown_count=1,
)


# ── Mock 파이프라인 팩토리 ────────────────────────────────────────────────────

def _make_pipeline(
    *,
    clean_bytes: bytes = CLEAN_BYTES,
    ocr_text: str = OCR_TEXT,
    ner_result: NERResult = NER_CLEAN,
    report: ProductSafetyReport = REPORT_PASS,
    explanation: str = "안전한 제품입니다.",
) -> AnalysisPipeline:
    """모든 하위 컴포넌트를 Mock으로 대체한 테스트용 파이프라인."""
    preprocessor = MagicMock()
    preprocessor.preprocess = AsyncMock(return_value=clean_bytes)

    ocr = MagicMock()
    ocr.extract_text = AsyncMock(return_value=ocr_text)

    parser = MagicMock()
    parser.parse = AsyncMock(return_value=ner_result)

    checker = MagicMock()
    checker.check = MagicMock(return_value=report)

    explainer = MagicMock()
    explainer.generate = AsyncMock(return_value=explanation)

    return AnalysisPipeline(
        preprocessor=preprocessor,
        ocr=ocr,
        parser=parser,
        checker=checker,
        explainer=explainer,
    )


# ── 1. PipelineResult 구조 ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_result_fields_populated() -> None:
    """analyze() 결과의 모든 필드가 채워지는지 확인."""
    pipeline = _make_pipeline(report=REPORT_PASS, explanation="안전합니다.")
    result = await pipeline.analyze(IMAGE_BYTES, [CHILD_A])

    assert isinstance(result, PipelineResult)
    assert result.ocr_text == OCR_TEXT
    assert result.ner_result == NER_CLEAN
    assert result.safety_report.overall_status == CheckStatus.PASS
    assert result.explanation == "안전합니다."


# ── 2. 각 Step 호출 순서 확인 ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_all_steps_called_with_correct_args() -> None:
    """5개 Step 이 올바른 인수로 순서대로 호출되는지 확인."""
    pipeline = _make_pipeline()
    await pipeline.analyze(IMAGE_BYTES, [CHILD_A])

    # Step 1: 원본 이미지 → 전처리
    pipeline._preprocessor.preprocess.assert_awaited_once_with(IMAGE_BYTES)
    # Step 2: 전처리 결과 → OCR
    pipeline._ocr.extract_text.assert_awaited_once_with(CLEAN_BYTES)
    # Step 3: OCR 텍스트 → NER
    pipeline._parser.parse.assert_awaited_once_with(OCR_TEXT)
    # Step 4: NER 결과 + 아동 목록 → RuleChecker
    pipeline._checker.check.assert_called_once_with(NER_CLEAN, [CHILD_A])
    # Step 5: LLM 설명
    pipeline._explainer.generate.assert_awaited_once()


# ── 3. PASS 판정 ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pass_calls_llm_with_pass_status() -> None:
    """PASS 판정 시 ExplanationInput.status='PASS' 로 LLM 호출."""
    pipeline = _make_pipeline(report=REPORT_PASS)
    await pipeline.analyze(IMAGE_BYTES, [CHILD_A])

    call_args = pipeline._explainer.generate.call_args
    inp: ExplanationInput = call_args[0][0]
    assert inp.status == "PASS"


# ── 4. FAIL 판정 ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fail_result_status() -> None:
    """FAIL 판정 결과가 result.safety_report 에 반영되는지 확인."""
    pipeline = _make_pipeline(report=REPORT_FAIL, explanation="위험 성분 포함.")
    result = await pipeline.analyze(IMAGE_BYTES, [CHILD_A])

    assert result.safety_report.overall_status == CheckStatus.FAIL
    assert result.explanation == "위험 성분 포함."


@pytest.mark.asyncio
async def test_fail_llm_input_status() -> None:
    """FAIL 판정 시 ExplanationInput.status='FAIL' 로 LLM 호출."""
    pipeline = _make_pipeline(report=REPORT_FAIL)
    await pipeline.analyze(IMAGE_BYTES, [CHILD_A])

    call_args = pipeline._explainer.generate.call_args
    inp: ExplanationInput = call_args[0][0]
    assert inp.status == "FAIL"


@pytest.mark.asyncio
async def test_fail_llm_input_matched_rules_present() -> None:
    """FAIL 판정 시 matched_rules 가 ExplanationInput 에 담기는지 확인."""
    pipeline = _make_pipeline(report=REPORT_FAIL)
    await pipeline.analyze(IMAGE_BYTES, [CHILD_A])

    call_args = pipeline._explainer.generate.call_args
    inp: ExplanationInput = call_args[0][0]
    assert len(inp.matched_rules) >= 1
    assert "카제인나트륨" in inp.matched_rules[0]


# ── 5. WARN 판정 ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_warn_calls_llm_with_warn_status() -> None:
    """WARN 판정 시 ExplanationInput.status='WARN' 로 LLM 호출."""
    pipeline = _make_pipeline(report=REPORT_WARN)
    await pipeline.analyze(IMAGE_BYTES, [CHILD_A])

    call_args = pipeline._explainer.generate.call_args
    inp: ExplanationInput = call_args[0][0]
    assert inp.status == "WARN"


# ── 6. EXPIRED → 고정 설명, LLM 불호출 ──────────────────────────────────────

@pytest.mark.asyncio
async def test_expired_no_llm_call() -> None:
    """EXPIRED 판정 시 LLM 미호출."""
    pipeline = _make_pipeline(report=REPORT_EXPIRED)
    await pipeline.analyze(IMAGE_BYTES, [CHILD_A])

    pipeline._explainer.generate.assert_not_awaited()


@pytest.mark.anyio
async def test_expired_returns_fixed_explanation() -> None:
    """EXPIRED 판정 시 고정 설명 문자열 반환."""
    pipeline = _make_pipeline(report=REPORT_EXPIRED)
    result = await pipeline.analyze(IMAGE_BYTES, [CHILD_A])

    assert result.explanation == _EXPLANATION_EXPIRED
    assert "유통기한" in result.explanation


# ── 7. UNKNOWN → 고정 설명, LLM 불호출 ──────────────────────────────────────

@pytest.mark.asyncio
async def test_unknown_no_llm_call() -> None:
    """UNKNOWN 판정 시 LLM 미호출."""
    pipeline = _make_pipeline(report=REPORT_UNKNOWN)
    await pipeline.analyze(IMAGE_BYTES, [CHILD_A])

    pipeline._explainer.generate.assert_not_awaited()


@pytest.mark.anyio
async def test_unknown_returns_fixed_explanation() -> None:
    """UNKNOWN 판정 시 고정 설명 문자열 반환."""
    pipeline = _make_pipeline(report=REPORT_UNKNOWN)
    result = await pipeline.analyze(IMAGE_BYTES, [CHILD_A])

    assert result.explanation == _EXPLANATION_UNKNOWN
    assert "성분" in result.explanation


# ── 8. RuleChecker 예외 → UNKNOWN fallback ────────────────────────────────────

@pytest.mark.asyncio
async def test_checker_exception_overall_unknown() -> None:
    """RuleChecker 예외 시 overall_status = UNKNOWN."""
    pipeline = _make_pipeline()
    pipeline._checker.check.side_effect = RuntimeError("DB 오류")

    result = await pipeline.analyze(IMAGE_BYTES, [CHILD_A])

    assert result.safety_report.overall_status == CheckStatus.UNKNOWN


@pytest.mark.asyncio
async def test_checker_exception_no_llm() -> None:
    """RuleChecker 예외 → UNKNOWN → LLM 미호출."""
    pipeline = _make_pipeline()
    pipeline._checker.check.side_effect = RuntimeError("오류")

    await pipeline.analyze(IMAGE_BYTES, [CHILD_A])

    pipeline._explainer.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_checker_exception_child_id_preserved() -> None:
    """RuleChecker 예외 시 아동 child_id 가 UNKNOWN 보고서에 보존."""
    pipeline = _make_pipeline()
    pipeline._checker.check.side_effect = ValueError("파싱 오류")

    result = await pipeline.analyze(IMAGE_BYTES, [CHILD_A, CHILD_B])

    child_ids = {r.child_id for r in result.safety_report.child_results}
    assert child_ids == {CHILD_A.child_id, CHILD_B.child_id}


@pytest.mark.asyncio
async def test_checker_exception_empty_product_fallback() -> None:
    """product 빈 문자열이면 '알 수 없는 제품' fallback."""
    ner = NERResult(product="", ingredient=["정제수"], expiry="")
    pipeline = _make_pipeline(ner_result=ner)
    pipeline._checker.check.side_effect = ValueError("오류")

    result = await pipeline.analyze(IMAGE_BYTES, [CHILD_A])

    assert result.safety_report.product_name == "알 수 없는 제품"


# ── 9. _to_verdict 헬퍼 ───────────────────────────────────────────────────────

def test_to_verdict_pass() -> None:
    assert _to_verdict(CheckStatus.PASS) == "PASS"


def test_to_verdict_warn() -> None:
    assert _to_verdict(CheckStatus.WARN) == "WARN"


def test_to_verdict_fail() -> None:
    assert _to_verdict(CheckStatus.FAIL) == "FAIL"


def test_to_verdict_expired_fallback_fail() -> None:
    """EXPIRED는 표로 없으므로 'FAIL' 안전망 동작 확인."""
    assert _to_verdict(CheckStatus.EXPIRED) == "FAIL"


def test_to_verdict_unknown_fallback_fail() -> None:
    """UNKNOWN도 동일."""
    assert _to_verdict(CheckStatus.UNKNOWN) == "FAIL"


# ── 10. _collect_rule_descriptions 헬퍼 ──────────────────────────────────────

def test_collect_deduplicates_across_children() -> None:
    """여러 아동이 같은 규칙에 걸려도 설명이 1개만 수집."""
    rule = MatchedRule(
        rule_code="ALLERGY_MILK_001",
        status=CheckStatus.FAIL,
        matched_ingredient="카제인나트륨",
        reason="우유 알레르기",
    )
    report = ProductSafetyReport(
        product_name="X",
        overall_status=CheckStatus.FAIL,
        child_results=[
            ChildCheckResult(child_id=1, status=CheckStatus.FAIL, matched_rules=[rule], reason="x"),
            ChildCheckResult(child_id=2, status=CheckStatus.FAIL, matched_rules=[rule], reason="x"),
        ],
    )
    desc = _collect_rule_descriptions(report)
    assert len(desc) == 1
    assert "카제인나트륨" in desc[0]
    assert "우유 알레르기" in desc[0]


def test_collect_no_ingredient_uses_reason_only() -> None:
    """matched_ingredient 빈 문자열이면 reason만 반환."""
    rule = MatchedRule(
        rule_code="EXPIRY_DATE_001",
        status=CheckStatus.WARN,
        matched_ingredient="",
        reason="유통기한 임박",
    )
    report = ProductSafetyReport(
        product_name="X",
        overall_status=CheckStatus.WARN,
        child_results=[
            ChildCheckResult(child_id=1, status=CheckStatus.WARN, matched_rules=[rule], reason="x"),
        ],
    )
    desc = _collect_rule_descriptions(report)
    assert desc == ["유통기한 임박"]


def test_collect_empty_matched_rules() -> None:
    """모든 아동 PASS → matched_rules 없음 → 빈 리스트."""
    report = ProductSafetyReport(
        product_name="X",
        overall_status=CheckStatus.PASS,
        child_results=[
            ChildCheckResult(child_id=1, status=CheckStatus.PASS, matched_rules=[], reason=""),
        ],
    )
    assert _collect_rule_descriptions(report) == []


# ── 11. _make_unknown_report 헬퍼 ────────────────────────────────────────────

def test_make_unknown_report_count() -> None:
    """아동 3명 → unknown_count=3, child_results 3개."""
    report = _make_unknown_report("테스트", [10, 20, 30])

    assert report.unknown_count == 3
    assert len(report.child_results) == 3
    assert all(r.status == CheckStatus.UNKNOWN for r in report.child_results)


def test_make_unknown_report_rule_code() -> None:
    """각 아동 결과에 OCR_UNKNOWN_001 규칙 코드 포함."""
    report = _make_unknown_report("제품", [1])

    assert report.child_results[0].matched_rules[0].rule_code == "OCR_UNKNOWN_001"


def test_make_unknown_report_product_name() -> None:
    """product_name 이 그대로 반영되는지 확인."""
    report = _make_unknown_report("특정 제품명", [5])

    assert report.product_name == "특정 제품명"
    assert report.overall_status == CheckStatus.UNKNOWN


def test_make_unknown_report_empty_children() -> None:
    """아동 목록 비어있어도 보고서 생성."""
    report = _make_unknown_report("제품", [])

    assert report.unknown_count == 0
    assert report.child_results == []


# ── 9. RAG 통합 ───────────────────────────────────────────────────────────────


def _make_pipeline_with_rag(
    *,
    report: ProductSafetyReport = REPORT_FAIL,
    explanation: str = "RAG 설명입니다.",
    search_result: list[object] | None = None,
) -> AnalysisPipeline:
    """KnowledgeLoader mock이 주입된 파이프라인."""
    from unittest.mock import AsyncMock, MagicMock

    from app.ai.knowledge_loader import KnowledgeLoader

    pipeline = _make_pipeline(report=report, explanation=explanation)
    pipeline._explainer.generate = AsyncMock(return_value=explanation)

    mock_loader = MagicMock(spec=KnowledgeLoader)
    mock_loader.search = AsyncMock(return_value=search_result or [])
    pipeline._knowledge_loader = mock_loader
    return pipeline


@pytest.mark.asyncio
async def test_rag_search_called_on_fail() -> None:
    """FAIL 판정 시 KnowledgeLoader.search() 가 호출된다."""
    pipeline = _make_pipeline_with_rag(report=REPORT_FAIL)
    await pipeline.analyze(IMAGE_BYTES, [CHILD_A])

    pipeline._knowledge_loader.search.assert_awaited_once()


@pytest.mark.asyncio
async def test_rag_search_called_on_warn() -> None:
    """WARN 판정 시 KnowledgeLoader.search() 가 호출된다."""
    pipeline = _make_pipeline_with_rag(report=REPORT_WARN)
    await pipeline.analyze(IMAGE_BYTES, [CHILD_A])

    pipeline._knowledge_loader.search.assert_awaited_once()


@pytest.mark.asyncio
async def test_rag_search_not_called_on_pass() -> None:
    """PASS 판정 시 KnowledgeLoader.search() 는 호출되지 않는다."""
    pipeline = _make_pipeline_with_rag(report=REPORT_PASS)
    await pipeline.analyze(IMAGE_BYTES, [CHILD_A])

    pipeline._knowledge_loader.search.assert_not_awaited()


@pytest.mark.asyncio
async def test_rag_search_not_called_on_expired() -> None:
    """EXPIRED 판정 시 KnowledgeLoader.search() 는 호출되지 않는다 (고정 설명)."""
    pipeline = _make_pipeline_with_rag(report=REPORT_EXPIRED)
    await pipeline.analyze(IMAGE_BYTES, [CHILD_A])

    pipeline._knowledge_loader.search.assert_not_awaited()


@pytest.mark.asyncio
async def test_rag_search_not_called_on_unknown() -> None:
    """UNKNOWN 판정 시 KnowledgeLoader.search() 는 호출되지 않는다 (고정 설명)."""
    pipeline = _make_pipeline_with_rag(report=REPORT_UNKNOWN)
    await pipeline.analyze(IMAGE_BYTES, [CHILD_A])

    pipeline._knowledge_loader.search.assert_not_awaited()


@pytest.mark.asyncio
async def test_rag_context_passed_to_explainer() -> None:
    """검색된 청크가 generate(context=...) 로 전달된다."""
    from app.models.knowledge_chunk import KnowledgeChunk

    chunk = KnowledgeChunk(
        title="우유 알레르기",
        content="우유는 13대 알레르기 성분입니다.",
        category="allergen_food",
        source="식약처 고시",
    )
    pipeline = _make_pipeline_with_rag(report=REPORT_FAIL, search_result=[chunk])
    await pipeline.analyze(IMAGE_BYTES, [CHILD_A])

    call_args = pipeline._explainer.generate.call_args
    context = call_args.kwargs.get("context") or call_args[1].get("context") or call_args[0][1]
    assert context is not None
    assert len(context) == 1
    assert "식약처 고시" in context[0]
    assert "우유는 13대 알레르기 성분입니다." in context[0]


@pytest.mark.asyncio
async def test_rag_search_failure_does_not_abort_pipeline() -> None:
    """RAG 검색 중 예외가 발생해도 파이프라인이 중단되지 않는다."""
    from unittest.mock import AsyncMock


    pipeline = _make_pipeline_with_rag(report=REPORT_FAIL)
    pipeline._knowledge_loader.search = AsyncMock(side_effect=RuntimeError("DB 오류"))

    result = await pipeline.analyze(IMAGE_BYTES, [CHILD_A])
    assert result.explanation == "RAG 설명입니다."


@pytest.mark.asyncio
async def test_rag_empty_knowledge_base_uses_no_context() -> None:
    """지식베이스가 비어있어 검색 결과가 없으면 context=[] 로 generate 호출."""
    pipeline = _make_pipeline_with_rag(report=REPORT_FAIL, search_result=[])
    await pipeline.analyze(IMAGE_BYTES, [CHILD_A])

    call_args = pipeline._explainer.generate.call_args
    # context=[] 는 falsy이므로 explicit key lookup으로 확인
    if "context" in call_args.kwargs:
        context = call_args.kwargs["context"]
    else:
        context = call_args[0][1]
    assert context == []


def test_build_system_prompt_with_context() -> None:
    """RAG 컨텍스트가 있으면 시스템 프롬프트에 보조 정보 섹션이 추가된다."""
    from app.ai.llm import _SYSTEM_PROMPT, _build_system_prompt

    context = ["[출처: 식약처]\n우유는 알레르기 유발 성분입니다."]
    prompt = _build_system_prompt(context)

    assert _SYSTEM_PROMPT in prompt
    assert "보조 정보" in prompt
    assert "식약처" in prompt


def test_build_system_prompt_without_context() -> None:
    """RAG 컨텍스트가 없으면 기본 시스템 프롬프트 그대로 반환."""
    from app.ai.llm import _SYSTEM_PROMPT, _build_system_prompt

    assert _build_system_prompt(None) == _SYSTEM_PROMPT
    assert _build_system_prompt([]) == _SYSTEM_PROMPT
