from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.ai.base import AIProvider
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
            {
                "child_id": result.child_id,
                "child_name": child.name if child else "알 수 없는 아동",
                "status": result.status,
                "matched_rule_code": result.matched_rule_code,
                "matched_profile": result.matched_profile,
                "matched_ingredient": result.matched_ingredient,
                "reason": result.reason,
                "explanation": result.explanation,
            }
        )

    total_count = (
        safety_check.pass_count
        + safety_check.warn_count
        + safety_check.fail_count
        + safety_check.expired_count
        + safety_check.unknown_count
    )

    explanations = [
        result.explanation
        for result in check_results
        if result.explanation
    ]

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
        "summary": {
            "overall_status": safety_check.overall_status,
            "pass_count": safety_check.pass_count,
            "warn_count": safety_check.warn_count,
            "fail_count": safety_check.fail_count,
            "expired_count": safety_check.expired_count,
            "unknown_count": safety_check.unknown_count,
            "total_count": total_count,
        },
        "results": results,
        "overall_explanation": "\n".join(explanations) if explanations else None,
    }


async def generate_safety_check_explanations(
    db: Session,
    check_id: int,
    current_user: User,
    provider: AIProvider,
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

    for result in check_results:
        result.explanation = await generator.generate(
            _build_explanation_input(result, product)
        )

    db.commit()

    return get_safety_check_detail(
        db=db,
        check_id=check_id,
        current_user=current_user,
    )
