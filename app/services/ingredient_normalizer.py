from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product import IngredientAlias


def normalize_ingredients(
    db: Session,
    ingredients: list[str],
) -> list[str]:
    aliases = db.scalars(select(IngredientAlias)).all()

    alias_map = {
        alias.alias.strip(): alias.canonical_name.strip()
        for alias in aliases
    }

    normalized = []

    for ingredient in ingredients:
        clean_ingredient = ingredient.strip()

        if not clean_ingredient:
            continue

        normalized.append(
            alias_map.get(clean_ingredient, clean_ingredient)
        )

    return normalized