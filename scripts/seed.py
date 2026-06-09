from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import delete, text
from sqlalchemy.orm import Session

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app.core.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Child,
    ChildHealthProfile,
    Classroom,
    Facility,
    IngredientAlias,
    Product,
    SafetyCheck,
    SafetyCheckResult,
    SafetyRule,
    User,
)

SEED_DIR = ROOT_DIR / "app" / "data" / "01_seed"


def load_collection(filename: str, key: str) -> list[dict[str, Any]]:
    payload = json.loads((SEED_DIR / filename).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or key not in payload:
        raise ValueError(f"{filename} must contain a top-level '{key}' array")

    items = payload[key]
    if not isinstance(items, list):
        raise ValueError(f"{filename}.{key} must be a list")

    return items


def parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    return date.fromisoformat(value)


def pick(item: dict[str, Any], fields: Iterable[str]) -> dict[str, Any]:
    return {field: item[field] for field in fields if field in item}


def reset_seed_tables(db: Session) -> None:
    for model in (
        SafetyCheckResult,
        SafetyCheck,
        ChildHealthProfile,
        Product,
        Child,
        User,
        Classroom,
        SafetyRule,
        IngredientAlias,
        Facility,
    ):
        db.execute(delete(model))


def reset_sequences(db: Session) -> None:
    for table_name in (
        "facilities",
        "classrooms",
        "users",
        "children",
        "child_health_profiles",
        "products",
        "ingredient_aliases",
        "safety_rules",
    ):
        db.execute(
            text(
                f"""
                SELECT setval(
                    pg_get_serial_sequence(:table_name, 'id'),
                    COALESCE((SELECT MAX(id) FROM {table_name}), 1),
                    true
                )
                """
            ),
            {"table_name": table_name},
        )


def seed_facilities(db: Session) -> int:
    items = load_collection("01_facilities.json", "facilities")
    db.add_all(
        Facility(**pick(item, {"id", "name", "address", "phone"})) for item in items
    )
    return len(items)


def seed_classrooms(db: Session) -> int:
    items = load_collection("02_classrooms.json", "classrooms")
    db.add_all(
        Classroom(**pick(item, {"id", "facility_id", "name", "age_group"}))
        for item in items
    )
    return len(items)


def seed_users(db: Session) -> int:
    items = load_collection("08_users.json", "users")
    db.add_all(
        User(
            **pick(
                item,
                {"id", "facility_id", "email", "password_hash", "name", "role"},
            )
        )
        for item in items
    )
    return len(items)


def seed_children(db: Session) -> int:
    items = load_collection("03_children.json", "children")
    children = []
    for item in items:
        child_data = pick(
            item,
            {
                "id",
                "facility_id",
                "classroom_id",
                "name",
                "birth_date",
                "gender",
                "memo",
                "is_active",
            },
        )
        child_data["birth_date"] = parse_date(child_data.get("birth_date"))
        children.append(Child(**child_data))

    db.add_all(children)
    return len(items)


def seed_child_health_profiles(db: Session) -> int:
    items = load_collection("04_child_health_profiles.json", "child_health_profiles")
    db.add_all(
        ChildHealthProfile(
            **pick(
                item,
                {
                    "id",
                    "child_id",
                    "allergies",
                    "skin_conditions",
                    "sensitive_ingredients",
                    "notes",
                },
            )
        )
        for item in items
    )
    return len(items)


def seed_products(db: Session) -> int:
    items = load_collection("05_products.json", "products")
    products = []
    for item in items:
        product_data = pick(
            item,
            {
                "id",
                "facility_id",
                "name",
                "category",
                "manufacturer",
                "barcode",
                "expiry_date",
                "raw_ingredients_text",
                "ingredients",
                "normalized_ingredients",
                "image_url",
                "ocr_raw_text",
                "created_by_id",
            },
        )
        product_data["expiry_date"] = parse_date(product_data.get("expiry_date"))
        product_data.setdefault("ingredients", [])
        product_data.setdefault(
            "normalized_ingredients",
            product_data["ingredients"],
        )
        products.append(Product(**product_data))

    db.add_all(products)
    return len(items)


def seed_ingredient_aliases(db: Session) -> int:
    items = load_collection("06_ingredient_aliases.json", "ingredient_aliases")
    db.add_all(
        IngredientAlias(**pick(item, {"id", "alias", "canonical_name"}))
        for item in items
    )
    return len(items)


def seed_safety_rules(db: Session) -> int:
    items = load_collection("07_safety_rules.json", "safety_rules")
    db.add_all(
        SafetyRule(
            **pick(
                item,
                {
                    "id",
                    "rule_code",
                    "target_type",
                    "trigger_name",
                    "ingredient_keywords",
                    "severity",
                    "reason",
                    "source_name",
                    "is_active",
                },
            )
        )
        for item in items
    )
    return len(items)


def seed(db: Session) -> dict[str, int]:
    reset_seed_tables(db)

    counts = {
        "facilities": seed_facilities(db),
        "classrooms": seed_classrooms(db),
        "users": seed_users(db),
        "children": seed_children(db),
        "child_health_profiles": seed_child_health_profiles(db),
        "ingredient_aliases": seed_ingredient_aliases(db),
        "safety_rules": seed_safety_rules(db),
        "products": seed_products(db),
    }

    db.flush()
    reset_sequences(db)
    db.commit()

    return counts


def main() -> None:
    db = SessionLocal()
    try:
        counts = seed(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print("Seed completed")
    for key, count in counts.items():
        print(f"- {key}: {count}")


if __name__ == "__main__":
    main()
