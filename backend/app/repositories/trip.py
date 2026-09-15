from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.travel import Trip
from app.repositories.base import BaseRepository


class TripRepository(BaseRepository[Trip]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Trip)

    def get_by_id(self, trip_id: uuid.UUID) -> Trip | None:
        return self.get(trip_id)
