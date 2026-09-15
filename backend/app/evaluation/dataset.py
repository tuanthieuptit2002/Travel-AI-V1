"""Gold evaluation dataset for TripMind travel agent."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import List

from app.evaluation.models import EvalCase

REFERENCE_DATE = date(2026, 10, 12)

_BASE_REQUIRED = [
    "search_places",
    "search_attractions",
    "search_restaurants",
    "get_place_details",
    "get_weather",
    "search_hotels",
]


def load_eval_dataset() -> List[EvalCase]:
    """Five deterministic Vietnam scenarios covering the required destinations."""
    return [
        EvalCase(
            id="danang_4d",
            user_request=(
                "I want to travel to Da Nang for 4 days and 3 nights for 2 people. "
                "Budget 8 million VND per person. I like beaches, local food and photography."
            ),
            expected_destination="Da Nang",
            expected_days=4,
            expected_travelers=2,
            expected_budget_total=Decimal("16000000"),
            expected_budget_per_person=Decimal("8000000"),
            expected_preferences=["beaches", "local food", "photography"],
            reference_date=REFERENCE_DATE,
            required_tools=_BASE_REQUIRED,
            forbidden_tools=["search_flights"],
        ),
        EvalCase(
            id="hanoi_3d",
            user_request=(
                "Plan a Hanoi trip for 3 days for 2 people. Budget 12 million VND. "
                "I like culture, photography and local food."
            ),
            expected_destination="Hanoi",
            expected_days=3,
            expected_travelers=2,
            expected_budget_total=Decimal("12000000"),
            expected_preferences=["culture", "photography", "local food"],
            reference_date=REFERENCE_DATE,
            required_tools=_BASE_REQUIRED,
            forbidden_tools=["search_flights"],
        ),
        EvalCase(
            id="dalat_5d",
            user_request=(
                "I want to visit Da Lat for 5 days for 2 people. Budget 15 million VND. "
                "I like photography, cafe and scenery."
            ),
            expected_destination="Da Lat",
            expected_days=5,
            expected_travelers=2,
            expected_budget_total=Decimal("15000000"),
            expected_preferences=["photography", "cafe", "scenery"],
            reference_date=REFERENCE_DATE,
            required_tools=_BASE_REQUIRED,
            forbidden_tools=["search_flights"],
        ),
        EvalCase(
            id="phuquoc_4d",
            user_request=(
                "Travel from Ho Chi Minh City to Phu Quoc for 4 days for 2 people. "
                "Budget 18 million VND. I like beaches, seafood and relaxed."
            ),
            expected_destination="Phu Quoc",
            expected_origin="Ho Chi Minh City",
            expected_days=4,
            expected_travelers=2,
            expected_budget_total=Decimal("18000000"),
            expected_preferences=["beaches", "seafood", "relaxed"],
            reference_date=REFERENCE_DATE,
            required_tools=[*_BASE_REQUIRED, "search_flights"],
            forbidden_tools=[],
        ),
        EvalCase(
            id="hoian_2d",
            user_request=(
                "Hoi An weekend for 2 days for 2 people. Budget 6 million VND. "
                "I like culture, photography and local food."
            ),
            expected_destination="Hoi An",
            expected_days=2,
            expected_travelers=2,
            expected_budget_total=Decimal("6000000"),
            expected_preferences=["culture", "photography", "local food"],
            reference_date=REFERENCE_DATE,
            required_tools=_BASE_REQUIRED,
            forbidden_tools=["search_flights"],
        ),
    ]
