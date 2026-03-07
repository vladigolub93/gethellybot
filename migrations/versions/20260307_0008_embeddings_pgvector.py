"""add pgvector embeddings for candidate and vacancy versions

Revision ID: 20260307_0008
Revises: 20260307_0007
Create Date: 2026-03-07 18:40:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260307_0008"
down_revision = "20260307_0007"
branch_labels = None
depends_on = None

EMBEDDING_DIMENSIONS = 256


def upgrade() -> None:
    op.execute(f"ALTER TABLE candidate_profile_versions ADD COLUMN semantic_embedding vector({EMBEDDING_DIMENSIONS})")
    op.execute(f"ALTER TABLE vacancy_versions ADD COLUMN semantic_embedding vector({EMBEDDING_DIMENSIONS})")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_candidate_profile_versions_semantic_embedding_ivfflat "
        "ON candidate_profile_versions USING ivfflat (semantic_embedding vector_cosine_ops) "
        "WITH (lists = 100)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_vacancy_versions_semantic_embedding_ivfflat "
        "ON vacancy_versions USING ivfflat (semantic_embedding vector_cosine_ops) "
        "WITH (lists = 50)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_vacancy_versions_semantic_embedding_ivfflat")
    op.execute("DROP INDEX IF EXISTS ix_candidate_profile_versions_semantic_embedding_ivfflat")
    op.drop_column("vacancy_versions", "semantic_embedding")
    op.drop_column("candidate_profile_versions", "semantic_embedding")
