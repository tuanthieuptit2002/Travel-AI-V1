from sqlalchemy import inspect
from sqlalchemy.orm import configure_mappers

import app.models  # noqa: F401
from app.db.base import Base
from app.models.travel import Place, TravelKnowledgeDocument, Trip, TripActivity, TripDay
from app.models.user import User, UserPreference


def test_initial_model_tables_are_registered() -> None:
    assert set(Base.metadata.tables) == {
        "users",
        "user_preferences",
        "trips",
        "trip_days",
        "trip_activities",
        "places",
        "restaurants",
        "hotels",
        "flights",
        "travel_knowledge_documents",
    }


def test_relationships_and_vector_column_are_mapped() -> None:
    configure_mappers()

    assert inspect(User).relationships["preference"].uselist is False
    assert inspect(User).relationships["trips"].mapper.class_ is Trip
    assert inspect(Trip).relationships["days"].mapper.class_ is TripDay
    assert inspect(TripDay).relationships["activities"].mapper.class_ is TripActivity
    assert inspect(Place).relationships["restaurant"].uselist is False
    assert "metadata" in Place.__table__.c
    assert "vector" in str(TravelKnowledgeDocument.__table__.c.embedding.type).lower()


def test_user_preference_is_one_to_one() -> None:
    assert UserPreference.__table__.c.user_id.unique is True
