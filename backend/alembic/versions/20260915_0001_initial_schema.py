"""Create TripMind's initial relational and vector schema.

Revision ID: 20260915_0001
Revises:
Create Date: 2026-09-15 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "20260915_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    uuid = postgresql.UUID(as_uuid=True)
    jsonb = postgresql.JSONB(astext_type=sa.Text())

    op.create_table(
        "users",
        sa.Column("id", uuid, primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "user_preferences",
        sa.Column("id", uuid, primary_key=True, nullable=False),
        sa.Column("user_id", uuid, nullable=False),
        sa.Column("preferred_activities", jsonb, nullable=False),
        sa.Column("food_preferences", jsonb, nullable=False),
        sa.Column("budget_level", sa.String(length=50)),
        sa.Column("preferred_trip_pace", sa.String(length=50)),
        sa.Column("dislikes", jsonb, nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_table(
        "trips",
        sa.Column("id", uuid, primary_key=True, nullable=False),
        sa.Column("user_id", uuid, nullable=False),
        sa.Column("destination", sa.String(length=255), nullable=False),
        sa.Column("origin", sa.String(length=255)),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("travelers", sa.Integer(), nullable=False),
        sa.Column("budget", sa.Numeric(precision=14, scale=2)),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_table(
        "places",
        sa.Column("id", uuid, primary_key=True, nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("provider_place_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6)),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6)),
        sa.Column("address", sa.Text()),
        sa.Column("rating", sa.Numeric(precision=2, scale=1)),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("metadata", jsonb, nullable=False),
        sa.UniqueConstraint("provider", "provider_place_id", name="uq_places_provider_place_id"),
    )
    op.create_table(
        "trip_days",
        sa.Column("id", uuid, primary_key=True, nullable=False),
        sa.Column("trip_id", uuid, nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("day_number", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("trip_id", "date", name="uq_trip_days_trip_date"),
        sa.UniqueConstraint("trip_id", "day_number", name="uq_trip_days_trip_day_number"),
    )
    op.create_table(
        "trip_activities",
        sa.Column("id", uuid, primary_key=True, nullable=False),
        sa.Column("trip_day_id", uuid, nullable=False),
        sa.Column("place_id", uuid),
        sa.Column("start_time", sa.Time()),
        sa.Column("end_time", sa.Time()),
        sa.Column("activity_type", sa.String(length=100), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("estimated_cost", sa.Numeric(precision=14, scale=2)),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["trip_day_id"], ["trip_days.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["place_id"], ["places.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("trip_day_id", "order_index", name="uq_trip_activities_day_order"),
    )
    op.create_table(
        "restaurants",
        sa.Column("place_id", uuid, primary_key=True, nullable=False),
        sa.Column("cuisine_types", jsonb, nullable=False),
        sa.Column("price_level", sa.String(length=50)),
        sa.ForeignKeyConstraint(["place_id"], ["places.id"], ondelete="CASCADE"),
    )
    op.create_table(
        "hotels",
        sa.Column("place_id", uuid, primary_key=True, nullable=False),
        sa.Column("nightly_rate", sa.Numeric(precision=14, scale=2)),
        sa.Column("amenities", jsonb, nullable=False),
        sa.ForeignKeyConstraint(["place_id"], ["places.id"], ondelete="CASCADE"),
    )
    op.create_table(
        "flights",
        sa.Column("id", uuid, primary_key=True, nullable=False),
        sa.Column("trip_id", uuid),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("provider_flight_id", sa.String(length=255)),
        sa.Column("airline", sa.String(length=100)),
        sa.Column("flight_number", sa.String(length=50)),
        sa.Column("departure_airport", sa.String(length=10), nullable=False),
        sa.Column("arrival_airport", sa.String(length=10), nullable=False),
        sa.Column("departure_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("arrival_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price", sa.Numeric(precision=14, scale=2)),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"], ondelete="SET NULL"),
    )
    op.create_table(
        "travel_knowledge_documents",
        sa.Column("id", uuid, primary_key=True, nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=1000)),
        sa.Column("embedding", Vector(1536)),
    )


def downgrade() -> None:
    op.drop_table("travel_knowledge_documents")
    op.drop_table("flights")
    op.drop_table("hotels")
    op.drop_table("restaurants")
    op.drop_table("trip_activities")
    op.drop_table("trip_days")
    op.drop_table("places")
    op.drop_table("trips")
    op.drop_table("user_preferences")
    op.drop_table("users")
