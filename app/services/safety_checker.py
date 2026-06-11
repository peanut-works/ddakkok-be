import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.ai.base import AIProvider
from app.ai.knowledge_loader import KnowledgeLoader
from app.ai.llm import ExplanationGenerator, ExplanationInput
from app.ai.ner import NERResult
from app.ai.rule_checker import (
    ChildHealthProfile as RuleCheckerChildHealthProfile,
)
from app.ai.rule_checker import get_rule_checker
from app.models.child import Child
from app.models.classroom import Classroom
from app.models.product import Product
from app.models.safety_check import SafetyCheck, SafetyCheckResult
from app.models.user import User

logger = logging.getLogger(__name__)


class SafetyCheckNotFoundError(ValueError):
    pass


class SafetyCheckValidationError(ValueError):
    pass


STATUS_PRIORITY = {
    "UNKNOWN": 0,
    "PASS": 1,
    "WARN": 2,
    "EXPIRED": 3,
    "FAIL": 4,
}


def _status_value(status: Any) -> str:
    if hasattr(status, "value"):
        return str(status.value)

    return str(status)


def _to_string_list(value: Any) -> list[str]:
    if not value:
        return []

    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    return [str(value).strip()]


def _get_representative_rule(matched_rules: list[Any]) -> Any | None:
    if not matched_rules:
        return None

    return max(
        matched_rules,
        key=lambda rule: STATUS_PRIORITY.get(_status_value(rule.status), 0),
    )


def _build_explanation_matched_rules(result: SafetyCheckResult) -> list[str]:
    parts = [
        value
        for value in (
            result.matched_rule_code,
            result.matched_ingredient,
            result.reason,
        )
        if value
    ]

    return [" - ".join(parts)] if parts else []


def _build_explanation_input(
    result: SafetyCheckResult,
    product: Product,
) -> ExplanationInput:
    ingredients = _to_string_list(product.normalized_ingredients or product.ingredients)

    return ExplanationInput(
        status=result.status,
        product=product.name,
        ingredient=ingredients,
        matched_rules=_build_explanation_matched_rules(result),
    )


def _build_rag_query(result: SafetyCheckResult) -> str:
    return " ".join(
        value
        for value in (
            result.matched_ingredient,
            result.matched_rule_code,
            result.reason,
        )
        if value
    )


async def _fetch_explanation_context(
    *,
    db: Session,
    knowledge_loader: KnowledgeLoader | None,
    result: SafetyCheckResult,
) -> list[str] | None:
    if knowledge_loader is None:
        return None

    query = _build_rag_query(result)
    if not query:
        return None

    try:
        chunks = await knowledge_loader.search(query, top_k=3)
    except Exception as exc:
        logger.warning("[SafetyCheck] RAG 검색 실패 — context 없이 설명 생성: %s", exc)
        db.rollback()
        return None

    if not chunks:
        return None

    return [f"[출처: {chunk.source}]\n{chunk.content}" for chunk in chunks]


def _status_label(status: str) -> str:
    labels = {
        "PASS": "사용 가능",
        "WARN": "주의 필요",
        "FAIL": "사용 보류",
        "EXPIRED": "사용 불가",
        "UNKNOWN": "확인 필요",
    }
    return labels.get(status, status)


def _display_rule_text(
    *,
    rule_code: str | None,
    matched_ingredient: str | None,
    reason: str | None,
) -> str:
    rule_labels = {
        "ALLERGY_MILK_001": "우유 관련 성분",
        "ALLERGY_EGG_001": "계란 관련 성분",
        "ALLERGY_PEANUT_001": "땅콩 관련 성분",
        "ALLERGY_NUT_001": "견과류 관련 성분",
        "SKIN_SENSITIVE_001": "민감성 피부에 자극이 될 수 있는 성분",
        "SKIN_ATOPY_001": "아토피 피부에 자극이 될 수 있는 성분",
        "EXPIRY_DATE_001": "유통기한이 지난 제품",
        "OCR_UNKNOWN_001": "성분표 확인이 필요한 제품",
        "SENSITIVE_DIRECT": "개인 주의 성분",
    }

    if rule_code in rule_labels:
        return rule_labels[rule_code]
    if matched_ingredient:
        return f"{matched_ingredient} 성분"
    if reason:
        return reason.rstrip(".")
    return "주의가 필요한 항목"


def _count_phrase(summary: dict[str, int]) -> str:
    if (
        summary["pass_count"] == summary["total_count"]
        and summary["warn_count"] == 0
        and summary["fail_count"] == 0
        and summary["expired_count"] == 0
        and summary["unknown_count"] == 0
    ):
        return "모두 사용 가능"

    parts = []
    if summary["fail_count"] > 0:
        parts.append(f"{summary['fail_count']}명은 사용을 보류")
    if summary["warn_count"] > 0:
        parts.append(f"{summary['warn_count']}명은 주의가 필요")
    if summary["expired_count"] > 0:
        parts.append(f"{summary['expired_count']}명은 사용 불가")
    if summary["unknown_count"] > 0:
        parts.append(f"{summary['unknown_count']}명은 확인이 필요")
    if summary["pass_count"] > 0:
        parts.append(f"{summary['pass_count']}명은 사용 가능")

    if len(parts) == 1:
        return parts[0]
    return "하고 ".join([", ".join(parts[:-1]), parts[-1]]) if len(parts) > 1 else "결과 없음"


def _matched_ingredients_from_rules(
    matched_rules: list[dict[str, Any]],
    matched_ingredient: str | None,
) -> list[str]:
    ingredients = [
        rule["matched_ingredient"]
        for rule in matched_rules
        if rule.get("matched_ingredient")
    ]
    if matched_ingredient:
        ingredients.append(matched_ingredient)
    return list(dict.fromkeys(ingredients))


def _teacher_sentence(result: dict[str, Any]) -> str:
    child_name = result["child_name"]
    status = result["status"]

    if status == "FAIL":
        return f"{child_name} 아동에게는 해당 제품 사용을 보류하고 대체 제품을 확인해 주세요."
    if status == "WARN":
        return f"{child_name} 아동은 주의가 필요하므로 사용 후 상태를 확인해 주세요."
    if status == "EXPIRED":
        return f"{child_name} 아동에게는 유통기한이 지난 제품이므로 사용하지 않는 것을 권장합니다."
    if status == "UNKNOWN":
        return f"{child_name} 아동은 성분 정보를 확인할 수 없어 사용 전 추가 확인이 필요합니다."
    return f"{child_name} 아동은 현재 등록된 정보 기준으로 사용 가능합니다."


def _with_display_fields(result: dict[str, Any]) -> dict[str, Any]:
    matched_rules = result.get("matched_rules", [])
    enriched = {
        **result,
        "status_label": _status_label(result["status"]),
        "matched_ingredients": _matched_ingredients_from_rules(
            matched_rules=matched_rules,
            matched_ingredient=result.get("matched_ingredient"),
        ),
    }
    enriched["teacher_sentence"] = _teacher_sentence(enriched)
    return enriched


def _build_child_summary(result: dict[str, Any]) -> str:
    child_name = result["child_name"]
    status = result["status"]
    display_text = _display_rule_text(
        rule_code=result.get("matched_rule_code"),
        matched_ingredient=result.get("matched_ingredient"),
        reason=result.get("reason"),
    )

    if status == "FAIL":
        return (
            f"{child_name} 아동은 {display_text}이 확인되어 "
            "대체 제품 사용을 권장합니다."
        )
    if status == "WARN":
        return (
            f"{child_name} 아동은 {display_text}이 있어 "
            "사용 후 상태 확인이 필요합니다."
        )
    if status == "EXPIRED":
        return (
            f"{child_name} 아동에게는 유통기한이 지난 제품이므로 사용하지 않는 것을 권장합니다."
        )
    if status == "UNKNOWN":
        return (
            f"{child_name} 아동은 성분 정보를 확인할 수 없어 사용 전 추가 확인이 필요합니다."
        )

    return f"{child_name} 아동은 등록된 건강 정보와 충돌하는 성분이 확인되지 않았습니다."


def _build_overall_explanation(
    product: Product,
    summary: dict[str, int],
    results: list[dict[str, Any]],
) -> str:
    total_count = summary["total_count"]
    risk_results = [
        result
        for result in results
        if result["status"] in {"FAIL", "WARN", "EXPIRED", "UNKNOWN"}
    ]

    intro = (
        f"{product.name} 검사 결과, 선택한 아동 {total_count}명 중 "
        f"{_count_phrase(summary)}합니다."
    )

    if not risk_results:
        return f"{product.name} 검사 결과, 선택한 아동 {total_count}명 모두 사용 가능합니다."

    child_summaries = " ".join(_build_child_summary(result) for result in risk_results)

    worst_status = max(
        (result["status"] for result in risk_results),
        key=lambda status: STATUS_PRIORITY.get(status, 0),
    )
    recommendations = {
        "FAIL": "사용 보류 대상 아동에게는 대체 제품 사용을 권장합니다.",
        "EXPIRED": "유통기한 만료 제품은 사용하지 않는 것을 권장합니다.",
        "WARN": "주의 대상 아동은 교사 판단 하에 사용하고 사용 후 상태를 확인해 주세요.",
        "UNKNOWN": "성분 확인이 어려운 제품은 관리자 확인 전까지 사용을 보류해 주세요.",
    }

    return f"{intro} {child_summaries} {recommendations[worst_status]}"


def _build_ner_result(product: Product) -> NERResult:
    ingredients = _to_string_list(
        product.normalized_ingredients or product.ingredients
    )

    expiry = ""
    if product.expiry_date is not None:
        expiry = product.expiry_date.isoformat()

    return NERResult(
        product=product.name,
        ingredient=ingredients,
        expiry=expiry,
    )


def _build_rule_checker_children(
    children: list[Child],
) -> list[RuleCheckerChildHealthProfile]:
    rule_checker_children = []

    for child in children:
        health_profile = child.health_profile

        rule_checker_children.append(
            RuleCheckerChildHealthProfile(
                child_id=child.id,
                allergies=_to_string_list(
                    health_profile.allergies if health_profile else []
                ),
                skin_conditions=_to_string_list(
                    health_profile.skin_conditions if health_profile else []
                ),
                sensitive_ingredients=_to_string_list(
                    health_profile.sensitive_ingredients if health_profile else []
                ),
            )
        )

    return rule_checker_children


def run_safety_check(
    db: Session,
    product_id: int,
    classroom_id: int,
    child_ids: list[int],
    current_user: User,
) -> dict[str, Any]:
    if not child_ids:
        raise SafetyCheckValidationError("child_ids must not be empty")

    unique_child_ids = list(dict.fromkeys(child_ids))

    if len(unique_child_ids) != len(child_ids):
        raise SafetyCheckValidationError("Duplicate child ids are not allowed")

    product = db.scalar(
        select(Product).where(
            Product.id == product_id,
            Product.facility_id == current_user.facility_id,
        )
    )

    if product is None:
        raise SafetyCheckNotFoundError("Product not found")

    classroom = db.scalar(
        select(Classroom).where(
            Classroom.id == classroom_id,
            Classroom.facility_id == current_user.facility_id,
        )
    )

    if classroom is None:
        raise SafetyCheckNotFoundError("Classroom not found")

    selected_children = db.scalars(
        select(Child)
        .options(selectinload(Child.health_profile))
        .where(
            Child.id.in_(unique_child_ids),
            Child.classroom_id == classroom_id,
            Child.facility_id == current_user.facility_id,
            Child.is_active.is_(True),
        )
    ).all()

    children_by_id = {child.id: child for child in selected_children}

    if set(children_by_id.keys()) != set(unique_child_ids):
        raise SafetyCheckNotFoundError("Some children were not found")

    children = [children_by_id[child_id] for child_id in unique_child_ids]

    ner_result = _build_ner_result(product)
    rule_checker_children = _build_rule_checker_children(children)

    checker = get_rule_checker(db)
    report = checker.check(
        ner_result=ner_result,
        children=rule_checker_children,
    )

    safety_check = SafetyCheck(
        facility_id=current_user.facility_id,
        product_id=product.id,
        classroom_id=classroom.id,
        requested_by_id=current_user.id,
        overall_status=_status_value(report.overall_status),
        pass_count=report.pass_count,
        warn_count=report.warn_count,
        fail_count=report.fail_count,
        expired_count=report.expired_count,
        unknown_count=report.unknown_count,
    )

    db.add(safety_check)
    db.flush()

    response_results = []

    for child_result in report.child_results:
        child = children_by_id[child_result.child_id]
        matched_rules = child_result.matched_rules
        representative_rule = _get_representative_rule(matched_rules)

        matched_rules_payload = [
            {
                "rule_code": rule.rule_code,
                "status": _status_value(rule.status),
                "matched_ingredient": rule.matched_ingredient,
                "reason": rule.reason,
            }
            for rule in matched_rules
        ]

        matched_rule_code = None
        matched_ingredient = None

        if representative_rule is not None:
            matched_rule_code = representative_rule.rule_code
            matched_ingredient = representative_rule.matched_ingredient

        safety_check_result = SafetyCheckResult(
            safety_check_id=safety_check.id,
            child_id=child_result.child_id,
            status=_status_value(child_result.status),
            matched_rule_code=matched_rule_code,
            matched_profile=None,
            matched_ingredient=matched_ingredient,
            reason=child_result.reason,
            explanation=None,
        )

        db.add(safety_check_result)

        response_results.append(
            _with_display_fields(
                {
                "child_id": child.id,
                "child_name": child.name,
                "status": _status_value(child_result.status),
                "matched_rules": matched_rules_payload,
                "matched_rule_code": matched_rule_code,
                "matched_profile": None,
                "matched_ingredient": matched_ingredient,
                "reason": child_result.reason,
                }
            )
        )

    db.commit()
    db.refresh(safety_check)

    return {
        "id": safety_check.id,
        "product_id": product.id,
        "product_name": product.name,
        "classroom_id": classroom.id,
        "overall_status": _status_value(report.overall_status),
        "pass_count": report.pass_count,
        "warn_count": report.warn_count,
        "fail_count": report.fail_count,
        "expired_count": report.expired_count,
        "unknown_count": report.unknown_count,
        "results": response_results,
    }


def get_safety_check_detail(
    db: Session,
    check_id: int,
    current_user: User,
) -> dict:
    safety_check = db.scalar(
        select(SafetyCheck).where(
            SafetyCheck.id == check_id,
            SafetyCheck.facility_id == current_user.facility_id,
        )
    )

    if safety_check is None:
        raise SafetyCheckNotFoundError("Safety check not found")

    product = db.scalar(
        select(Product).where(
            Product.id == safety_check.product_id,
            Product.facility_id == current_user.facility_id,
        )
    )

    if product is None:
        raise SafetyCheckNotFoundError("Product not found")

    check_results = db.scalars(
        select(SafetyCheckResult)
        .where(SafetyCheckResult.safety_check_id == safety_check.id)
        .order_by(SafetyCheckResult.id.asc())
    ).all()

    child_ids = [result.child_id for result in check_results]

    children_by_id = {}

    if child_ids:
        children = db.scalars(
            select(Child).where(
                Child.id.in_(child_ids),
                Child.facility_id == current_user.facility_id,
            )
        ).all()

        children_by_id = {child.id: child for child in children}

    results = []

    for result in check_results:
        child = children_by_id.get(result.child_id)

        results.append(
            _with_display_fields(
                {
                "child_id": result.child_id,
                "child_name": child.name if child else "알 수 없는 아동",
                "status": result.status,
                "matched_rules": [],
                "matched_rule_code": result.matched_rule_code,
                "matched_profile": result.matched_profile,
                "matched_ingredient": result.matched_ingredient,
                "reason": result.reason,
                "explanation": result.explanation,
                }
            )
        )

    total_count = (
        safety_check.pass_count
        + safety_check.warn_count
        + safety_check.fail_count
        + safety_check.expired_count
        + safety_check.unknown_count
    )

    summary = {
        "overall_status": safety_check.overall_status,
        "pass_count": safety_check.pass_count,
        "warn_count": safety_check.warn_count,
        "fail_count": safety_check.fail_count,
        "expired_count": safety_check.expired_count,
        "unknown_count": safety_check.unknown_count,
        "total_count": total_count,
    }

    return {
        "id": safety_check.id,
        "product": {
            "id": product.id,
            "name": product.name,
            "category": product.category,
            "manufacturer": product.manufacturer,
            "barcode": product.barcode,
            "expiry_date": product.expiry_date,
            "ingredients": product.ingredients or [],
            "normalized_ingredients": product.normalized_ingredients or [],
        },
        "classroom_id": safety_check.classroom_id,
        "summary": summary,
        "results": results,
        "overall_explanation": _build_overall_explanation(
            product=product,
            summary=summary,
            results=results,
        ),
    }


async def generate_safety_check_explanations(
    db: Session,
    check_id: int,
    current_user: User,
    provider: AIProvider,
    knowledge_loader: KnowledgeLoader | None = None,
) -> dict:
    safety_check = db.scalar(
        select(SafetyCheck).where(
            SafetyCheck.id == check_id,
            SafetyCheck.facility_id == current_user.facility_id,
        )
    )

    if safety_check is None:
        raise SafetyCheckNotFoundError("Safety check not found")

    product = db.scalar(
        select(Product).where(
            Product.id == safety_check.product_id,
            Product.facility_id == current_user.facility_id,
        )
    )

    if product is None:
        raise SafetyCheckNotFoundError("Product not found")

    check_results = db.scalars(
        select(SafetyCheckResult)
        .where(SafetyCheckResult.safety_check_id == safety_check.id)
        .order_by(SafetyCheckResult.id.asc())
    ).all()

    generator = ExplanationGenerator(provider)

    generated_explanations: list[tuple[SafetyCheckResult, str]] = []

    for result in check_results:
        context = await _fetch_explanation_context(
            db=db,
            knowledge_loader=knowledge_loader,
            result=result,
        )
        explanation = await generator.generate(
            _build_explanation_input(result, product), context=context
        )
        generated_explanations.append((result, explanation))

    for result, explanation in generated_explanations:
        result.explanation = explanation

    db.commit()

    return get_safety_check_detail(
        db=db,
        check_id=check_id,
        current_user=current_user,
    )
