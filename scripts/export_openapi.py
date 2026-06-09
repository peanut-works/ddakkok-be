from __future__ import annotations

import importlib
import sys
from pathlib import Path

import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
OPENAPI_PATH = ROOT_DIR / "docs" / "openapi.yml"


def export_openapi() -> None:
    sys.path.insert(0, str(ROOT_DIR))
    app = importlib.import_module("main").app

    OPENAPI_PATH.write_text(
        yaml.safe_dump(app.openapi(), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"OpenAPI schema exported to {OPENAPI_PATH.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    export_openapi()
