"""Rule Checker — 제품 성분 × 아동 건강 프로필 안전 판정 엔진.

파이프라인 위치: NER → [RuleChecker] → LLM 설명 생성

판정 기준:
    FAIL    — 알레르기 유발 성분 매칭
    WARN    — 민감성 피부 주의 성분 매칭 또는 유통기한 임박(30일 이내)
    PASS    — 매칭되는 위험 성분 없음
    EXPIRED — 유통기한 만료
    UNKNOWN — 성분표 판독 불가 (빈 ingredients)

데이터 소스 (서버 시작 시 1회 로딩):
    app/data/01_seed/07_safety_rules.json       — 위험 성분 규칙 정의
    app/data/01_seed/06_ingredient_aliases.json — 성분 별칭 정규화 사전

복수 규칙 매칭 시 가장 심각한 판정이 최종 판정:
    FAIL > EXPIRED > WARN > PASS > UNKNOWN
"""

import json
import logging
from datetime import date, datetime
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai.ner import NERResult
from app.core.database import get_db

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent.parent / "data" / "01_seed"
_EXPIRY_WARN_DAYS = 30  # 유통기한 임박 기준 (일)


# ── 판정 상태 ─────────────────────────────────────────────────────────────────

class CheckStatus(StrEnum):
    """판정 결과. severity_rank() 값이 높을수록 위험."""

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"

    def severity_rank(self) -> int:
        return {"UNKNOWN": 0, "PASS": 1, "WARN": 2, "EXPIRED": 3, "FAIL": 4}[self.value]


# ── 입력 모델 ─────────────────────────────────────────────────────────────────

class ChildHealthProfile(BaseModel):
    """Rule Checker 입력용 아동 건강 프로필.

    BE 팀 DB 모델과 1:1로 매핑된다.
    allergies: 알레르기 항목 목록 (예: ["우유", "계란"])
    skin_conditions: 피부 상태 목록 (예: ["민감성 피부", "아토피"])
    sensitive_ingredients: 개인별 추가 주의 성분 (예: ["페녹시에탄올"])
    """

    child_id: int
    allergies: list[str] = []
    skin_conditions: list[str] = []
    sensitive_ingredients: list[str] = []


# ── 출력 모델 ─────────────────────────────────────────────────────────────────

class MatchedRule(BaseModel):
    """단일 규칙 매칭 결과."""

    rule_code: str
    status: CheckStatus
    matched_ingredient: str
    reason: str


class ChildCheckResult(BaseModel):
    """아동 1명에 대한 판정 결과."""

    child_id: int
    status: CheckStatus
    matched_rules: list[MatchedRule] = []
    reason: str


class ProductSafetyReport(BaseModel):
    """제품 전체 안전 보고서."""

    product_name: str
    overall_status: CheckStatus
    child_results: list[ChildCheckResult]
    pass_count: int = 0
    warn_count: int = 0
    fail_count: int = 0
    expired_count: int = 0
    unknown_count: int = 0


# ── 데이터 로딩 ───────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _load_rules_from_json() -> list[dict[str, Any]]:
    """07_safety_rules.json 로딩 (JSON fallback, @lru_cache로 1회 캐싱)."""
    path = _DATA_DIR / "07_safety_rules.json"
    with open(path, encoding="utf-8") as f:
        data: list[dict[str, Any]] = json.load(f)["safety_rules"]
    logger.info("[RuleChecker] 안전 규칙 %d개 로딩 (JSON)", len(data))
    return data


@lru_cache(maxsize=1)
def _load_aliases_from_json() -> dict[str, str]:
    """06_ingredient_aliases.json 로딩 (JSON fallback, @lru_cache로 1회 캐싱)."""
    path = _DATA_DIR / "06_ingredient_aliases.json"
    with open(path, encoding="utf-8") as f:
        items: list[dict[str, str]] = json.load(f)["ingredient_aliases"]
    mapping = {item["alias"].lower().strip(): item["canonical_name"] for item in items}
    logger.info("[RuleChecker] 성분 별칭 %d개 로딩 (JSON)", len(mapping))
    return mapping


def _rules_from_db(db: Session) -> list[dict[str, Any]]:
    """safety_rules 테이블에서 활성 규칙 로딩."""
    from app.models.safety_rule import SafetyRule

    rows = db.query(SafetyRule).filter(SafetyRule.is_active.is_(True)).all()
    return [
        {
            "rule_code": r.rule_code,
            "target_type": r.target_type,
            "trigger_name": r.trigger_name,
            "ingredient_keywords": r.ingredient_keywords,
            "severity": r.severity,
            "reason": r.reason,
        }
        for r in rows
    ]


def _aliases_from_db(db: Session) -> dict[str, str]:
    """ingredient_aliases 테이블에서 별칭 매핑 로딩."""
    from app.models.product import IngredientAlias

    rows = db.query(IngredientAlias).all()
    return {row.alias.lower().strip(): row.canonical_name for row in rows}


# ── Rule Checker ──────────────────────────────────────────────────────────────

class RuleChecker:
    """성분 × 아동 건강 프로필 대조 판정 엔진.

    사용 예::

        checker = RuleChecker()
        report = checker.check(ner_result, children)
        # report.overall_status → "FAIL"
        # report.fail_count     → 2
    """

    def __init__(
        self,
        rules: list[dict[str, Any]] | None = None,
        aliases: dict[str, str] | None = None,
    ) -> None:
        self._rules = rules if rules is not None else _load_rules_from_json()
        self._aliases = aliases if aliases is not None else _load_aliases_from_json()

    # ── Public ────────────────────────────────────────────────────────────────

    def check(
        self,
        ner_result: NERResult,
        children: list[ChildHealthProfile],
        today: date | None = None,
    ) -> ProductSafetyReport:
        """NERResult + 아동 프로필 목록 → ProductSafetyReport.

        Args:
            ner_result: NER 추출 결과 (성분 목록, 유통기한 포함)
            children:   대조할 아동 프로필 목록
            today:      기준일 (기본값: 오늘). 테스트에서 날짜 고정 시 사용.
        """
        today = today or date.today()

        child_results = [
            self._check_child(ner_result, child, today)
            for child in children
        ]

        counts: dict[str, int] = {s.value: 0 for s in CheckStatus}
        for r in child_results:
            counts[r.status.value] += 1

        overall = (
            max(child_results, key=lambda r: r.status.severity_rank()).status
            if child_results
            else CheckStatus.UNKNOWN
        )

        return ProductSafetyReport(
            product_name=ner_result.product or "알 수 없는 제품",
            overall_status=overall,
            child_results=child_results,
            pass_count=counts["PASS"],
            warn_count=counts["WARN"],
            fail_count=counts["FAIL"],
            expired_count=counts["EXPIRED"],
            unknown_count=counts["UNKNOWN"],
        )

    # ── Internal ──────────────────────────────────────────────────────────────

    def _normalize(self, name: str) -> str:
        """별칭을 정규 성분명으로 변환. 사전에 없으면 원문 반환."""
        return self._aliases.get(name.strip().lower(), name.strip())

    def _parse_expiry(self, expiry_str: str) -> date | None:
        """유통기한 문자열 파싱. 실패 시 None."""
        for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d", "%y.%m.%d", "%y/%m/%d"):
            try:
                return datetime.strptime(expiry_str.strip(), fmt).date()
            except ValueError:
                continue
        return None

    def _get_expiry_status(self, expiry_str: str, today: date) -> CheckStatus | None:
        """유통기한 판정.

        Returns:
            EXPIRED  — 만료됨
            WARN     — 임박 (30일 이내)
            None     — 정상 또는 파싱 불가
        """
        if not expiry_str:
            return None
        expiry = self._parse_expiry(expiry_str)
        if expiry is None:
            logger.warning("[RuleChecker] 유통기한 파싱 실패: '%s'", expiry_str)
            return None
        if expiry < today:
            return CheckStatus.EXPIRED
        if (expiry - today).days <= _EXPIRY_WARN_DAYS:
            return CheckStatus.WARN
        return None

    def _match_ingredient(self, ingredient: str, keyword: str) -> bool:
        """성분명과 키워드 매칭 (대소문자 무시, 부분 문자열).

        '카제인나트륨' ↔ '카제인Na' 같은 별칭은 _normalize() 후 이 함수에 도달.
        짧은 키워드가 긴 성분명에 포함되거나, 긴 키워드에 짧은 성분명이 포함되면 매칭.
        """
        a = ingredient.lower().strip()
        b = keyword.lower().strip()
        return a == b or b in a or a in b

    def _dedupe_matched_rules(
        self,
        matched_rules: list[MatchedRule],
    ) -> list[MatchedRule]:
        """동일 rule/status/ingredient/reason 조합을 한 번만 남긴다."""
        seen: set[tuple[str, CheckStatus, str, str]] = set()
        deduped: list[MatchedRule] = []

        for rule in matched_rules:
            key = (
                rule.rule_code,
                rule.status,
                rule.matched_ingredient,
                rule.reason,
            )
            if key in seen:
                continue

            seen.add(key)
            deduped.append(rule)

        return deduped

    def _check_child(
        self,
        ner_result: NERResult,
        child: ChildHealthProfile,
        today: date,
    ) -> ChildCheckResult:
        """아동 1명에 대한 판정 수행."""

        # ── UNKNOWN: 성분표 없음 ────────────────────────────────────────────
        if not ner_result.ingredient:
            return ChildCheckResult(
                child_id=child.child_id,
                status=CheckStatus.UNKNOWN,
                matched_rules=[
                    MatchedRule(
                        rule_code="OCR_UNKNOWN_001",
                        status=CheckStatus.UNKNOWN,
                        matched_ingredient="",
                        reason="성분표를 확인할 수 없어 안전 여부를 판단할 수 없습니다.",
                    )
                ],
                reason="성분표를 확인할 수 없어 안전 여부를 판단할 수 없습니다.",
            )

        # ── 성분 정규화 ─────────────────────────────────────────────────────
        normalized = [self._normalize(i) for i in ner_result.ingredient]

        # ── EXPIRED: 유통기한 만료 ──────────────────────────────────────────
        expiry_status = self._get_expiry_status(ner_result.expiry, today)
        if expiry_status == CheckStatus.EXPIRED:
            return ChildCheckResult(
                child_id=child.child_id,
                status=CheckStatus.EXPIRED,
                matched_rules=[
                    MatchedRule(
                        rule_code="EXPIRY_DATE_001",
                        status=CheckStatus.EXPIRED,
                        matched_ingredient="",
                        reason="제품 유통기한이 지나 사용이 권장되지 않습니다.",
                    )
                ],
                reason="제품 유통기한이 지나 사용이 권장되지 않습니다.",
            )

        # ── 규칙 매칭 ────────────────────────────────────────────────────────
        matched_rules: list[MatchedRule] = []

        for rule in self._rules:
            target = rule.get("target_type", "")
            if target not in ("ALLERGY", "SKIN"):
                continue

            # 이 아동과 관련된 규칙인지 확인
            trigger = rule.get("trigger_name", "")
            if target == "ALLERGY" and trigger not in child.allergies:
                continue
            if target == "SKIN" and trigger not in child.skin_conditions:
                continue

            # 성분 키워드 매칭
            for keyword in rule.get("ingredient_keywords", []):
                norm_keyword = self._normalize(keyword)
                for ingredient in normalized:
                    if self._match_ingredient(ingredient, norm_keyword):
                        matched_rules.append(
                            MatchedRule(
                                rule_code=rule["rule_code"],
                                status=CheckStatus(rule["severity"]),
                                matched_ingredient=ingredient,
                                reason=rule["reason"],
                            )
                        )
                        break  # 같은 규칙에서 중복 추가 방지

        # ── 개인별 민감 성분 직접 매칭 (WARN) ──────────────────────────────
        for sensitive in child.sensitive_ingredients:
            norm_sensitive = self._normalize(sensitive)
            for ingredient in normalized:
                if self._match_ingredient(ingredient, norm_sensitive):
                    # 이미 같은 성분으로 규칙 매칭됐으면 중복 추가 안 함
                    already = any(r.matched_ingredient == ingredient for r in matched_rules)
                    if not already:
                        matched_rules.append(
                            MatchedRule(
                                rule_code="SENSITIVE_DIRECT",
                                status=CheckStatus.WARN,
                                matched_ingredient=ingredient,
                                reason=f"아동 개인 주의 성분 '{sensitive}' 포함.",
                            )
                        )
                    break

        # ── 유통기한 임박 WARN ──────────────────────────────────────────────
        if expiry_status == CheckStatus.WARN:
            matched_rules.append(
                MatchedRule(
                    rule_code="EXPIRY_DATE_001",
                    status=CheckStatus.WARN,
                    matched_ingredient="",
                    reason=f"유통기한이 {_EXPIRY_WARN_DAYS}일 이내로 임박했습니다.",
                )
            )

        # ── 최종 판정 ────────────────────────────────────────────────────────
        matched_rules = self._dedupe_matched_rules(matched_rules)

        if not matched_rules:
            return ChildCheckResult(
                child_id=child.child_id,
                status=CheckStatus.PASS,
                matched_rules=[],
                reason="아동 건강 프로필과 매칭되는 위험 성분 없음",
            )

        worst = max(matched_rules, key=lambda r: r.status.severity_rank())
        return ChildCheckResult(
            child_id=child.child_id,
            status=worst.status,
            matched_rules=matched_rules,
            reason=worst.reason,
        )


# ── 팩토리 ───────────────────────────────────────────────────────────────────


def get_rule_checker(db: Session = Depends(get_db)) -> RuleChecker:
    """FastAPI Depends 주입용 팩토리.

    DB에서 safety_rules / ingredient_aliases를 로딩한다.
    DB가 비어있을 경우 JSON fallback으로 자동 전환.
    """
    rules = _rules_from_db(db)
    aliases = _aliases_from_db(db)
    if not rules or not aliases:
        logger.warning("[RuleChecker] DB 규칙/별칭 없음 — JSON fallback 사용")
        return RuleChecker()
    logger.debug("[RuleChecker] DB에서 규칙 %d개, 별칭 %d개 로딩", len(rules), len(aliases))
    return RuleChecker(rules=rules, aliases=aliases)
