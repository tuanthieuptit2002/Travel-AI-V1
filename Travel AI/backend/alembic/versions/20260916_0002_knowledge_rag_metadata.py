"""Create Date: 2026-09-16 00:30:00

Revision ID: 20260916_0002
Revises: 20260915_0001
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260916_0002"
down_revision = "20260915_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("travel_knowledge_documents", sa.Column("destination", sa.String(length=255), nullable=True))
    op.add_column("travel_knowledge_documents", sa.Column("category", sa.String(length=100), nullable=True))
    op.add_column(
        "travel_knowledge_documents",
        sa.Column("chunk_index", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "travel_knowledge_documents",
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_travel_knowledge_destination", "travel_knowledge_documents", ["destination"])
    op.create_index("ix_travel_knowledge_category", "travel_knowledge_documents", ["category"])


def downgrade() -> None:
    op.drop_index("ix_travel_knowledge_category", table_name="travel_knowledge_documents")
    op.drop_index("ix_travel_knowledge_destination", table_name="travel_knowledge_documents")
    op.drop_column("travel_knowledge_documents", "metadata")
    op.drop_column("travel_knowledge_documents", "chunk_index")
    op.drop_column("travel_knowledge_documents", "category")
    op.drop_column("travel_knowledge_documents", "destination")
