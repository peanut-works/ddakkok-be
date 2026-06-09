#!/usr/bin/env python3
"""Prepare a SQL file that imports JSON documents into PostgreSQL JSONB tables."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a PostgreSQL import SQL file from JSON documents.",
    )
    parser.add_argument(
        "--database",
        default="ddakkok",
        help="Target PostgreSQL database name.",
    )
    parser.add_argument(
        "--input",
        dest="inputs",
        action="append",
        help="JSON file or directory relative to the workspace. Repeat to add more sources.",
    )
    parser.add_argument(
        "--output-dir",
        default=".docker/postgres-import",
        help="Directory where run-import.sql will be written.",
    )
    return parser.parse_args()


def resolve_workspace_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (ROOT / path).resolve()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_json_files(path: Path) -> list[Path]:
    if path.is_file():
        if path.suffix.lower() != ".json":
            raise ValueError(f"Expected a .json file: {path}")
        return [path]

    if not path.is_dir():
        raise ValueError(f"Input path does not exist: {path}")

    return sorted(item for item in path.iterdir() if item.is_file() and item.suffix.lower() == ".json")


def normalize_table_name(value: str) -> str:
    parts = value.split("_", maxsplit=1)
    return parts[1] if len(parts) == 2 and parts[0].isdigit() else value


def to_table_job(name: str, value: Any) -> dict[str, Any] | None:
    if value is None:
        return None

    table_name = "seed_meta" if name == "meta" else name

    if isinstance(value, list):
        return {"name": table_name, "documents": value}

    if isinstance(value, dict):
        return {"name": table_name, "documents": [value]}

    return None


def add_jobs_from_payload(jobs: list[dict[str, Any]], payload: Any, source_path: Path) -> None:
    if isinstance(payload, list):
        table_name = normalize_table_name(source_path.stem)
        jobs.append({"name": table_name, "documents": payload})
        return

    if not isinstance(payload, dict):
        raise ValueError("Top-level JSON must be an object or array.")

    for name, value in payload.items():
        job = to_table_job(name, value)
        if job is not None:
            jobs.append(job)


def escape_sql_literal(value: str) -> str:
    return value.replace("'", "''")


def quote_identifier(identifier: str) -> str:
    return f'"{identifier.replace(chr(34), chr(34) * 2)}"'


def build_import_sql(jobs: list[dict[str, Any]], database_name: str) -> str:
    lines: list[str] = [f"\\connect {database_name}", "BEGIN;", ""]

    for job in jobs:
        table_name = quote_identifier(job["name"])
        lines.extend([
            f"CREATE TABLE IF NOT EXISTS public.{table_name} (",
            "  id BIGSERIAL PRIMARY KEY,",
            "  data JSONB NOT NULL",
            ");",
            f"TRUNCATE TABLE public.{table_name} RESTART IDENTITY;",
        ])

        documents = job["documents"]
        if documents:
            values = ",\n".join(
                f"('{escape_sql_literal(json.dumps(document, ensure_ascii=False))}'::jsonb)"
                for document in documents
            )
            lines.extend([
                f"INSERT INTO public.{table_name} (data) VALUES",
                f"{values};",
            ])

        lines.append("")

    lines.extend(["COMMIT;", ""])
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    jobs: list[dict[str, Any]] = []
    raw_inputs = args.inputs or [
        "app/data/01_seed/00_seed_data.json",
        "app/data/02_mock",
        "app/data/03_scenarios",
    ]

    for raw_input in raw_inputs:
        input_path = resolve_workspace_path(raw_input)
        for json_file in iter_json_files(input_path):
            add_jobs_from_payload(jobs, load_json(json_file), json_file)

    output_dir = resolve_workspace_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "run-import.sql"
    output_path.write_text(build_import_sql(jobs, args.database), encoding="utf-8")

    table_names = ", ".join(job["name"] for job in jobs) or "(none)"
    print(f"Prepared PostgreSQL import SQL: {output_path}")
    print(f"Tables to replace: {table_names}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
