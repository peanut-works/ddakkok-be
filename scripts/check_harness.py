#!/usr/bin/env python3
"""Run local harness checks for ddakkok-be (FastAPI + uv)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> None:
    print(f"\n>>> {' '.join(command)}")
    subprocess.run(command, cwd=ROOT, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ddakkok-be harness checks.")
    parser.add_argument("--skip-mypy", action="store_true", help="Skip mypy (before mypy is fully configured).")
    parser.add_argument("--skip-tests", action="store_true", help="Skip pytest.")
    parser.add_argument("--tests", default="tests", help="Test directory for pytest discovery.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    run(["uv", "run", "ruff", "check", "."])

    if not args.skip_mypy:
        run([
            "uv", "run", "mypy",
            "--exclude", r"(harness-starter-kit|\.venv|__pycache__)",
            ".",
        ])

    if not args.skip_tests and Path(ROOT / args.tests).exists():
        run(["uv", "run", "pytest", args.tests, "-v"])

    run(["uv", "run", "python", "scripts/check_docs_drift.py"])
    run(["uv", "run", "python", "scripts/check_structure.py"])

    print("\n✓ All harness checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
