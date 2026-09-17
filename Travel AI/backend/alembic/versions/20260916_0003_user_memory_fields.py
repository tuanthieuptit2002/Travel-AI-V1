"""Extend user_preferences for full structured travel memory fields.

Revision ID: 20260916_0003
Revises: 20260916_0002
Create Date: 2026-09-16 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260916_0003"
down_revision = "20260916_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.add_column(
        "user_preferences",
        sa.Column("preferred_destinations", jsonb, nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column(
        "user_preferences",
        sa.Column("accommodation_preference", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "user_preferences",
        sa.Column("transportation_preference", sa.String(length=50), nullable=True),
    )
    op.alter_column("user_preferences", "preferred_destinations", server_default=None)


def downgrade() -> None:
    op.drop_column("user_preferences", "transportation_preference")
    op.drop_column("user_preferences", "accommodation_preference")
    op.drop_column("user_preferences", "preferred_destinations")
