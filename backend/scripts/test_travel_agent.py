"""Run the TripMind LangGraph travel agent without an external LLM API.

Usage from backend/:
    PYTHONPATH=. python scripts/test_travel_agent.py
"""

from __future__ import annotations

import json
from datetime import date

from app.agent import run_travel_agent


def main() -> None:
    request = (
        "I want to travel to Da Nang for 4 days and 3 nights for 2 people. "
        "Budget 8 million VND per person. I like beaches, local food and photography."
    )
    result = run_travel_agent(request, reference_date=date(2026, 10, 12))
    final = result.get("final_response") or {}
    print("Destination:", result.get("destination"))
    print("Travelers:", result.get("travelers"))
    print("Budget:", result.get("budget"), result.get("currency"))
    print("Valid:", final.get("is_valid"))
    print("Headline:", final.get("headline"))
    print("Overview:", final.get("overview"))
    print("\nItinerary:")
    print(json.dumps(final.get("itinerary"), indent=2, ensure_ascii=False))
    print("\nWeather notes:")
    for note in final.get("weather_notes") or []:
        print("-", note)
    print("\nBudget notes:")
    for note in final.get("budget_notes") or []:
        print("-", note)


if __name__ == "__main__":
    main()
