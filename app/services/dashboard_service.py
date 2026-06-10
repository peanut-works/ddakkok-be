from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.child import Child
from app.models.product import Product
from app.models.recall_notice import RecallNotice
from app.models.safety_check import SafetyCheck, SafetyCheckResult
from app.models.user import User

DASHBOARD_RECALL_LIMIT = 5
DASHBOARD_EXPIRY_LIMIT = 5
DASHBOARD_ATTENTION_LIMIT = 5
EXPIRING_DAYS = 30
NEW_RECALL_DAYS = 14

NON_PASS_STATUSES = {"WARN", "FAIL", "EXPIRED", "UNKNOWN"}


def _status_label(status: str) -> str:
    labels = {
        "PASS": "사용 가능",
        "WARN": "주의 필요",
        "FAIL": "사용 보류",
        "EXPIRED": "사용 불가",
        "UNKNOWN": "확인 필요",
    }
    return labels.get(status, status)


def _severity_for_status(status: str) -> str:
    if status in {"FAIL", "EXPIRED", "UNKNOWN"}:
        return "HIGH"
    return "MEDIUM"


def _get_recall_alerts(
    db: Session,
    facility_id: int,
    today: date,
) -> list[dict]:
    notices = db.scalars(
        select(RecallNotice)
        .where(
            RecallNotice.is_active.is_(True),
            or_(
                RecallNotice.facility_id.is_(None),
                RecallNotice.facility_id == facility_id,
            ),
        )
        .order_by(RecallNotice.recall_date.desc(), RecallNotice.id.desc())
        .limit(DASHBOARD_RECALL_LIMIT)
    ).all()

    return [
        {
            "id": notice.id,
            "product_name": notice.product_name,
            "manufacturer": notice.manufacturer,
            "category": notice.category,
            "recall_date": notice.recall_date,
            "reason": notice.reason,
            "action_guide": notice.action_guide,
            "is_new": notice.recall_date >= today - timedelta(days=NEW_RECALL_DAYS),
            "severity": "HIGH",
        }
        for notice in notices
    ]


def _get_expiry_alerts(
    db: Session,
    facility_id: int,
    today: date,
) -> list[dict]:
    threshold = today + timedelta(days=EXPIRING_DAYS)
    products = db.scalars(
        select(Product)
        .where(
            Product.facility_id == facility_id,
            Product.expiry_date.is_not(None),
            Product.expiry_date <= threshold,
        )
        .order_by(Product.expiry_date.asc(), Product.id.asc())
    ).all()

    alerts = []
    for product in products:
        if product.expiry_date is None:
            continue

        is_expired = product.expiry_date < today
        alert_type = "EXPIRED" if is_expired else "EXPIRING"
        alerts.append(
            {
                "product_id": product.id,
                "product_name": product.name,
                "expiry_date": product.expiry_date,
                "alert_type": alert_type,
                "message": (
                    "유통기한이 만료된 제품입니다."
                    if is_expired
                    else "유통기한이 30일 이내로 임박한 제품입니다."
                ),
                "severity": "HIGH" if is_expired else "MEDIUM",
            }
        )

    return sorted(
        alerts,
        key=lambda alert: (
            0 if alert["alert_type"] == "EXPIRED" else 1,
            alert["expiry_date"],
            alert["product_id"],
        ),
    )[:DASHBOARD_EXPIRY_LIMIT]


def _summary_for_check(check: SafetyCheck) -> str:
    parts = []
    if check.fail_count > 0:
        parts.append(f"사용 보류 {check.fail_count}명")
    if check.warn_count > 0:
        parts.append(f"주의 필요 {check.warn_count}명")
    if check.expired_count > 0:
        parts.append(f"사용 불가 {check.expired_count}명")
    if check.unknown_count > 0:
        parts.append(f"확인 필요 {check.unknown_count}명")
    return ", ".join(parts) if parts else _status_label(check.overall_status)


def _get_attention_products(
    db: Session,
    facility_id: int,
    classroom_id: int | None,
) -> list[dict]:
    query = (
        select(SafetyCheck)
        .where(
            SafetyCheck.facility_id == facility_id,
            SafetyCheck.overall_status.in_(NON_PASS_STATUSES),
        )
        .order_by(SafetyCheck.checked_at.desc(), SafetyCheck.id.desc())
    )
    if classroom_id is not None:
        query = query.where(SafetyCheck.classroom_id == classroom_id)

    checks = db.scalars(query).all()

    attention_items = []
    seen_product_ids: set[int] = set()

    for check in checks:
        if check.product_id in seen_product_ids:
            continue

        product = db.get(Product, check.product_id)
        if product is None or product.facility_id != facility_id:
            continue

        non_pass_results = db.scalars(
            select(SafetyCheckResult)
            .where(
                SafetyCheckResult.safety_check_id == check.id,
                SafetyCheckResult.status.in_(NON_PASS_STATUSES),
            )
            .order_by(SafetyCheckResult.id.asc())
        ).all()

        child_ids = [result.child_id for result in non_pass_results]
        children_by_id = {}
        if child_ids:
            children = db.scalars(
                select(Child).where(
                    Child.id.in_(child_ids),
                    Child.facility_id == facility_id,
                )
            ).all()
            children_by_id = {child.id: child for child in children}

        attention_items.append(
            {
                "check_id": check.id,
                "product_id": product.id,
                "product_name": product.name,
                "overall_status": check.overall_status,
                "status_label": _status_label(check.overall_status),
                "summary": _summary_for_check(check),
                "children": [
                    {
                        "child_id": result.child_id,
                        "child_name": (
                            children_by_id[result.child_id].name
                            if result.child_id in children_by_id
                            else "알 수 없는 아동"
                        ),
                        "status": result.status,
                        "status_label": _status_label(result.status),
                    }
                    for result in non_pass_results
                ],
            }
        )

        seen_product_ids.add(check.product_id)
        if len(attention_items) >= DASHBOARD_ATTENTION_LIMIT:
            break

    return attention_items


def get_dashboard_summary(
    db: Session,
    current_user: User,
    classroom_id: int | None = None,
) -> dict:
    today = date.today()

    return {
        "recall_alerts": _get_recall_alerts(
            db=db,
            facility_id=current_user.facility_id,
            today=today,
        ),
        "expiry_alerts": _get_expiry_alerts(
            db=db,
            facility_id=current_user.facility_id,
            today=today,
        ),
        "attention_products": _get_attention_products(
            db=db,
            facility_id=current_user.facility_id,
            classroom_id=classroom_id,
        ),
    }
