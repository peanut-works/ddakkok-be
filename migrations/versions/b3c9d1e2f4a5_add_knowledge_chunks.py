"""add knowledge_chunks table

Revision ID: b3c9d1e2f4a5
Revises: 40b0a8f4e6b2
Create Date: 2026-06-10 10:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

revision: str = "b3c9d1e2f4a5"
down_revision: str | Sequence[str] | None = "40b0a8f4e6b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 1536


def upgrade() -> None:
    # pgvector 익스텐션 활성화 (이미 있으면 무시)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # embedding 컬럼은 pgvector 네이티브 DDL로 생성.
    # 마이그레이션 파일에서 pgvector를 임포트하면 Alembic revision graph 빌드 시
    # (alembic history, alembic current 등) pgvector 미설치 환경에서 ModuleNotFoundError가
    # 발생하므로, 순수 SQL로 처리한다.
    op.execute(f"""
        CREATE TABLE knowledge_chunks (
            id          SERIAL PRIMARY KEY,
            title       VARCHAR(200) NOT NULL,
            content     TEXT        NOT NULL,
            category    VARCHAR(50) NOT NULL,
            source      VARCHAR(200) NOT NULL,
            embedding   vector({EMBEDDING_DIM}),
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # 코사인 유사도 검색을 위한 HNSW 인덱스
    op.execute(
        "CREATE INDEX ix_knowledge_chunks_embedding_hnsw "
        "ON knowledge_chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_embedding_hnsw")
    op.drop_table("knowledge_chunks")
