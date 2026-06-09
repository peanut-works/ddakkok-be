"""RuleChecker 단위 테스트.

app/data/01_seed/ 실제 JSON 파일을 그대로 사용해 통합 검증.
날짜는 today= 파라미터로 고정해 재현 가능성 확보.
"""

from datetime import date

import pytest

from app.ai.ner import NERResult
from app.ai.rule_checker import (
    CheckStatus,
    ChildHealthProfile,
    RuleChecker,
)

# ── 픽스처 ─────────────────────────────────────────────────────────────────────

TODAY = date(2026, 6, 9)  # 테스트 기준일 고정


@pytest.fixture
def checker() -> RuleChecker:
    return RuleChecker()


# 아동 프로필 픽스처
CHILD_MILK_ALLERGY = ChildHealthProfile(child_id=1, allergies=["우유"])
CHILD_EGG_ALLERGY = ChildHealthProfile(child_id=4, allergies=["계란"])
CHILD_PEANUT_NUT = ChildHealthProfile(child_id=5, allergies=["땅콩", "견과류"])
CHILD_SENSITIVE_SKIN = ChildHealthProfile(
    child_id=2,
    skin_conditions=["민감성 피부"],
    sensitive_ingredients=["페녹시에탄올"],
)
CHILD_ATOPY = ChildHealthProfile(
    child_id=6,
    skin_conditions=["아토피"],
    sensitive_ingredients=["향료", "색소", "에탄올"],
)
CHILD_HEALTHY = ChildHealthProfile(child_id=3)


# ── 1. PASS: 위험 성분 없는 제품 ───────────────────────────────────────────────

def test_pass_clean_product(checker: RuleChecker) -> None:
    """위험 성분 없는 핸드워시 → 모든 아동 PASS."""
    ner = NERResult(
        product="세이프 데일리 핸드워시",
        ingredient=["정제수", "글리세린", "코코베타인", "구연산"],
        expiry="2027-12-31",
    )
    report = checker.check(ner, [CHILD_MILK_ALLERGY, CHILD_SENSITIVE_SKIN, CHILD_HEALTHY], today=TODAY)

    assert report.overall_status == CheckStatus.PASS
    assert report.pass_count == 3
    assert report.fail_count == 0
    assert report.warn_count == 0
    for r in report.child_results:
        assert r.status == CheckStatus.PASS


# ── 2. FAIL: 알레르기 성분 매칭 ────────────────────────────────────────────────

def test_fail_milk_allergy(checker: RuleChecker) -> None:
    """카제인나트륨 포함 물티슈 → 우유 알레르기 아동 FAIL."""
    ner = NERResult(
        product="밀크 프로틴 보습 물티슈",
        ingredient=["정제수", "글리세린", "카제인나트륨", "페녹시에탄올"],
        expiry="2027-08-31",
    )
    report = checker.check(ner, [CHILD_MILK_ALLERGY], today=TODAY)

    assert report.overall_status == CheckStatus.FAIL
    assert report.fail_count == 1
    result = report.child_results[0]
    assert result.status == CheckStatus.FAIL
    assert any(r.rule_code == "ALLERGY_MILK_001" for r in result.matched_rules)


def test_fail_egg_allergy(checker: RuleChecker) -> None:
    """계란 포함 식품 → 계란 알레르기 아동 FAIL."""
    ner = NERResult(
        product="에그 소프트 쿠키",
        ingredient=["밀가루", "설탕", "계란", "난백", "버터"],
        expiry="2027-02-28",
    )
    report = checker.check(ner, [CHILD_EGG_ALLERGY], today=TODAY)

    assert report.fail_count == 1
    assert report.child_results[0].status == CheckStatus.FAIL


def test_fail_peanut_allergy(checker: RuleChecker) -> None:
    """땅콩버터 포함 → 땅콩 알레르기 아동 FAIL."""
    ner = NERResult(
        product="땅콩버터 크런치바",
        ingredient=["귀리", "설탕", "땅콩버터", "아몬드"],
        expiry="2027-05-20",
    )
    report = checker.check(ner, [CHILD_PEANUT_NUT], today=TODAY)

    assert report.overall_status == CheckStatus.FAIL
    matched_codes = {r.rule_code for r in report.child_results[0].matched_rules}
    # 땅콩 또는 견과류 규칙 중 하나 이상 매칭
    assert matched_codes & {"ALLERGY_PEANUT_001", "ALLERGY_NUT_001"}


# ── 3. WARN: 민감성 피부 성분 매칭 ──────────────────────────────────────────────

def test_warn_sensitive_skin(checker: RuleChecker) -> None:
    """향료/에탄올 포함 로션 → 민감성 피부 아동 WARN."""
    ner = NERResult(
        product="향기 톡톡 키즈 로션",
        ingredient=["정제수", "글리세린", "향료", "에탄올"],
        expiry="2027-11-30",
    )
    report = checker.check(ner, [CHILD_SENSITIVE_SKIN], today=TODAY)

    assert report.overall_status == CheckStatus.WARN
    assert report.warn_count == 1
    result = report.child_results[0]
    assert result.status == CheckStatus.WARN
    assert any(r.rule_code == "SKIN_SENSITIVE_001" for r in result.matched_rules)


def test_warn_atopy(checker: RuleChecker) -> None:
    """색소 포함 클렌저 → 아토피 아동 WARN."""
    ner = NERResult(
        product="컬러 버블 클렌저",
        ingredient=["정제수", "코코베타인", "색소", "구연산"],
        expiry="2027-09-15",
    )
    report = checker.check(ner, [CHILD_ATOPY], today=TODAY)

    assert report.warn_count == 1
    assert report.child_results[0].status == CheckStatus.WARN


# ── 4. FAIL > WARN: 복합 케이스 ─────────────────────────────────────────────────

def test_fail_overrides_warn(checker: RuleChecker) -> None:
    """FAIL + WARN 동시 발생 시 overall_status = FAIL."""
    ner = NERResult(
        product="복합 주의 키즈 크림",
        ingredient=["정제수", "글리세린", "카제인나트륨", "향료", "에탄올"],
        expiry="2027-10-10",
    )
    # 우유 알레르기(FAIL) + 민감성 피부(WARN) 동시 보유 아동
    child_complex = ChildHealthProfile(
        child_id=7,
        allergies=["우유"],
        skin_conditions=["아토피"],
    )
    report = checker.check(ner, [child_complex], today=TODAY)

    assert report.overall_status == CheckStatus.FAIL
    result = report.child_results[0]
    assert result.status == CheckStatus.FAIL
    codes = {r.rule_code for r in result.matched_rules}
    assert "ALLERGY_MILK_001" in codes


def test_mixed_children(checker: RuleChecker) -> None:
    """우유 알레르기 아동(FAIL) + 건강 아동(PASS) 혼재 → overall FAIL."""
    ner = NERResult(
        product="밀크 물티슈",
        ingredient=["정제수", "카제인나트륨"],
        expiry="2027-12-31",
    )
    report = checker.check(ner, [CHILD_MILK_ALLERGY, CHILD_HEALTHY], today=TODAY)

    assert report.overall_status == CheckStatus.FAIL
    assert report.fail_count == 1
    assert report.pass_count == 1


# ── 5. EXPIRED: 유통기한 만료 ───────────────────────────────────────────────────

def test_expired_product(checker: RuleChecker) -> None:
    """유통기한 만료 제품 → 모든 아동 EXPIRED (성분 검사 우선 종료)."""
    ner = NERResult(
        product="유통기한 지난 물티슈",
        ingredient=["정제수", "글리세린"],
        expiry="2025-12-31",  # 기준일(2026-06-09)보다 과거
    )
    report = checker.check(ner, [CHILD_HEALTHY, CHILD_MILK_ALLERGY], today=TODAY)

    assert report.overall_status == CheckStatus.EXPIRED
    assert report.expired_count == 2
    for r in report.child_results:
        assert r.status == CheckStatus.EXPIRED
        assert r.matched_rules[0].rule_code == "EXPIRY_DATE_001"


def test_expiry_approaching_warn(checker: RuleChecker) -> None:
    """유통기한 임박(30일 이내) → 건강 아동에게 WARN."""
    ner = NERResult(
        product="곧 만료 제품",
        ingredient=["정제수", "글리세린"],
        expiry="2026-06-20",  # TODAY(2026-06-09) + 11일 → 임박
    )
    report = checker.check(ner, [CHILD_HEALTHY], today=TODAY)

    assert report.overall_status == CheckStatus.WARN
    assert report.child_results[0].status == CheckStatus.WARN


def test_expiry_not_soon(checker: RuleChecker) -> None:
    """유통기한 31일 후 → PASS."""
    ner = NERResult(
        product="여유 있는 제품",
        ingredient=["정제수"],
        expiry="2026-07-10",  # TODAY + 31일
    )
    report = checker.check(ner, [CHILD_HEALTHY], today=TODAY)

    assert report.overall_status == CheckStatus.PASS


# ── 6. UNKNOWN: 성분표 없음 ─────────────────────────────────────────────────────

def test_unknown_empty_ingredients(checker: RuleChecker) -> None:
    """빈 성분 목록 → UNKNOWN."""
    ner = NERResult(product="성분표 훼손 제품", ingredient=[], expiry="2027-12-31")
    report = checker.check(ner, [CHILD_HEALTHY, CHILD_MILK_ALLERGY], today=TODAY)

    assert report.overall_status == CheckStatus.UNKNOWN
    assert report.unknown_count == 2
    for r in report.child_results:
        assert r.status == CheckStatus.UNKNOWN


# ── 7. 별칭 정규화 ────────────────────────────────────────────────────────────

def test_alias_normalization_casein(checker: RuleChecker) -> None:
    """OCR이 '카제인Na'로 읽어도 우유 알레르기 FAIL."""
    ner = NERResult(
        product="별칭 테스트 제품",
        ingredient=["정제수", "카제인Na"],  # OCR 원문 그대로
        expiry="2027-12-31",
    )
    report = checker.check(ner, [CHILD_MILK_ALLERGY], today=TODAY)

    assert report.overall_status == CheckStatus.FAIL


def test_alias_normalization_alcohol(checker: RuleChecker) -> None:
    """'알코올' 표기도 민감성 피부 WARN."""
    ner = NERResult(
        product="알코올 테스트",
        ingredient=["정제수", "글리세린", "향료", "알코올"],
        expiry="2027-12-31",
    )
    report = checker.check(ner, [CHILD_SENSITIVE_SKIN], today=TODAY)

    # 향료만으로도 WARN 충분하지만, 알코올 별칭 정규화도 확인
    assert report.overall_status == CheckStatus.WARN


# ── 8. 프로필 미매칭: 다른 알레르기 보유 아동 ──────────────────────────────────────

def test_no_match_wrong_allergy(checker: RuleChecker) -> None:
    """계란 알레르기 아동에게 우유 성분 → PASS (알레르기 불일치)."""
    ner = NERResult(
        product="우유 제품",
        ingredient=["정제수", "카제인나트륨"],
        expiry="2027-12-31",
    )
    report = checker.check(ner, [CHILD_EGG_ALLERGY], today=TODAY)

    assert report.overall_status == CheckStatus.PASS


def test_no_match_healthy_child_dangerous_product(checker: RuleChecker) -> None:
    """건강한 아동은 위험 성분 포함 제품도 PASS."""
    ner = NERResult(
        product="알레르기 성분 제품",
        ingredient=["카제인나트륨", "난백", "땅콩버터"],
        expiry="2027-12-31",
    )
    report = checker.check(ner, [CHILD_HEALTHY], today=TODAY)

    assert report.overall_status == CheckStatus.PASS


# ── 9. 엣지 케이스 ────────────────────────────────────────────────────────────

def test_empty_children_list(checker: RuleChecker) -> None:
    """아동 목록이 비어 있으면 UNKNOWN 반환."""
    ner = NERResult(product="테스트", ingredient=["정제수"])
    report = checker.check(ner, [], today=TODAY)

    assert report.overall_status == CheckStatus.UNKNOWN
    assert report.child_results == []


def test_no_expiry_date(checker: RuleChecker) -> None:
    """유통기한 없어도 성분 검사 정상 진행."""
    ner = NERResult(
        product="유통기한 없는 제품",
        ingredient=["정제수", "글리세린"],
        expiry="",
    )
    report = checker.check(ner, [CHILD_HEALTHY], today=TODAY)

    assert report.overall_status == CheckStatus.PASS


def test_product_name_defaults(checker: RuleChecker) -> None:
    """product 빈 문자열이면 '알 수 없는 제품'으로 대체."""
    ner = NERResult(product="", ingredient=["정제수"])
    report = checker.check(ner, [CHILD_HEALTHY], today=TODAY)

    assert report.product_name == "알 수 없는 제품"


def test_personal_sensitive_ingredient(checker: RuleChecker) -> None:
    """아동 개인 sensitive_ingredients 직접 매칭 → WARN."""
    child = ChildHealthProfile(
        child_id=99,
        sensitive_ingredients=["페녹시에탄올"],  # 피부 상태 없이 직접 지정
    )
    ner = NERResult(
        product="페녹시에탄올 제품",
        ingredient=["정제수", "페녹시에탄올"],
        expiry="2027-12-31",
    )
    report = checker.check(ner, [child], today=TODAY)

    assert report.overall_status == CheckStatus.WARN
    assert report.child_results[0].matched_rules[0].rule_code == "SENSITIVE_DIRECT"
