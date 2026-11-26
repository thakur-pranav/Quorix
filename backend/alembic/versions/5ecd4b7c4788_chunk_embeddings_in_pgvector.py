"""chunk embeddings in pgvector

Vectors move from Chroma into chunks.embedding (Day 6): one datastore, one transaction.
Postgres: enable the pgvector extension and add a vector(384) column. SQLite (tests, local dev):
the same column as JSON. Existing rows get NULL; scripts/backfill_embeddings.py fills them.

The dimension is fixed here on purpose: it's part of the schema. A different embedding model
means a new migration and re-embedding every chunk.

Revision ID: 5ecd4b7c4788
Revises: c841fdef07b2
Create Date: 2026-11-26 16:20:41.512063

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "5ecd4b7c4788"
down_revision: Union[str, Sequence[str], None] = "c841fdef07b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIMENSION = 384  # all-MiniLM-L6-v2


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    with op.batch_alter_table("chunks", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("embedding", sa.JSON(none_as_null=True).with_variant(Vector(EMBEDDING_DIMENSION), "postgresql"), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("chunks", schema=None) as batch_op:
        batch_op.drop_column("embedding")
    # The extension stays: other database objects may use it, and dropping it is a DBA decision.
