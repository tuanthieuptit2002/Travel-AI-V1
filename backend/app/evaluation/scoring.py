"""Scoring helpers for TripMind agent evaluation."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from app.agent.models import TripItinerary
from app.agent.parser import DeterministicRequestParser
from app.agent.validator import known_ids_from_candidates, validate_itinerary
from app.evaluation.models import CaseScores, EvalCase
from app.providers.mock import MockPlacesProvider


def score_case(
    case: EvalCase,
    *,
    agent_state: Dict[str, Any],
    tools_used: Set[str],
) -> CaseScores:
    parser = DeterministicRequestParser()
    try:
        parsed = parser.parse(case.user_request, reference_date=case.reference_date)
        parse_ok = True
    except Exception as exc:  # noqa: BLE001
        parsed = None
        parse_ok = False
        parse_error = str(exc)

    destination_score = (
        1.0
        if parse_ok and parsed and parsed.destination == case.expected_destination
        else 0.0
    )
    # Prefer agent state destination (post-bootstrap) when present.
    state_dest = agent_state.get("destination")
    if state_dest == case.expected_destination:
        destination_score = 1.0

    travelers_score = (
        1.0
        if int(agent_state.get("travelers") or 0) == case.expected_travelers
        else 0.0
    )

    dates_score = _score_dates(case, agent_state, parsed)
    budget_score = _score_budget(case, agent_state, parsed)
    pref_score = _score_preferences(
        case.expected_preferences, list(agent_state.get("preferences") or [])
    )

    understanding = _mean(
        [destination_score, dates_score, budget_score, travelers_score, pref_score]
    )

    tool_score = _score_tools(case, tools_used)
    itinerary_score, itinerary_details = _score_itinerary(case, agent_state)
    budget_validity, budget_details = _score_budget_validity(agent_state)
    duplicate_score, dup_details = _score_duplicates(agent_state)
    unsupported_rate, claim_details = _score_unsupported_claims(agent_state)
    halluc_rate, halluc_details = _score_hallucinations(agent_state)

    return CaseScores(
        case_id=case.id,
        destination=destination_score,
        dates=dates_score,
        budget=budget_score,
        travelers=travelers_score,
        preferences=pref_score,
        request_understanding=understanding,
        tool_selection=tool_score,
        itinerary_validity=itinerary_score,
        budget_validity=budget_validity,
        duplicate_free=duplicate_score,
        unsupported_claims_rate=unsupported_rate,
        hallucination_rate=halluc_rate,
        details={
            "destination_actual": state_dest,
            "travelers_actual": agent_state.get("travelers"),
            "budget_actual": agent_state.get("budget"),
            "preferences_actual": agent_state.get("preferences"),
            "origin_actual": agent_state.get("origin"),
            "tools_used": sorted(tools_used),
            "parse_ok": parse_ok,
            **({"parse_error": parse_error} if not parse_ok else {}),
            **itinerary_details,
            **budget_details,
            **dup_details,
            **claim_details,
            **halluc_details,
        },
    )


def _score_dates(case: EvalCase, state: Dict[str, Any], parsed: Any) -> float:
    start = state.get("start_date")
    end = state.get("end_date")
    if not start or not end:
        return 0.0
    try:
        from datetime import date as date_cls

        start_d = date_cls.fromisoformat(str(start))
        end_d = date_cls.fromisoformat(str(end))
    except ValueError:
        return 0.0
    days = (end_d - start_d).days + 1
    expected_start = case.reference_date
    expected_end = expected_start + timedelta(days=case.expected_days - 1)
    checks = [
        1.0 if days == case.expected_days else 0.0,
        1.0 if start_d == expected_start else 0.0,
        1.0 if end_d == expected_end else 0.0,
    ]
    if parsed is not None:
        checks.append(1.0 if parsed.days == case.expected_days else 0.0)
    return _mean(checks)


def _score_budget(case: EvalCase, state: Dict[str, Any], parsed: Any) -> float:
    actual = Decimal(str(state.get("budget") or "0"))
    if actual == case.expected_budget_total:
        return 1.0
    if parsed is not None and parsed.budget_total == case.expected_budget_total:
        return 1.0
    # Allow 1% tolerance for formatting drift.
    if case.expected_budget_total == 0:
        return 0.0
    delta = abs(actual - case.expected_budget_total) / case.expected_budget_total
    return 1.0 if delta <= Decimal("0.01") else 0.0


def _score_preferences(expected: Sequence[str], actual: Sequence[str]) -> float:
    if not expected:
        return 1.0 if not actual else 0.5
    exp = {item.casefold() for item in expected}
    act = {item.casefold() for item in actual}
    if not act:
        return 0.0
    precision = len(exp & act) / len(act)
    recall = len(exp & act) / len(exp)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _score_tools(case: EvalCase, used: Set[str]) -> float:
    required = set(case.required_tools)
    forbidden = set(case.forbidden_tools)
    if not required and not forbidden:
        return 1.0
    recall = len(required & used) / len(required) if required else 1.0
    forbidden_hits = len(forbidden & used)
    forbidden_penalty = (
        1.0 - (forbidden_hits / len(forbidden)) if forbidden else 1.0
    )
    return _mean([recall, forbidden_penalty])


def _score_itinerary(case: EvalCase, state: Dict[str, Any]) -> tuple[float, Dict[str, Any]]:
    raw = state.get("itinerary")
    if not raw:
        return 0.0, {"itinerary_errors": ["missing itinerary"]}

    itinerary = TripItinerary.model_validate(raw)
    known = known_ids_from_candidates(
        state.get("candidate_places") or [],
        state.get("candidate_restaurants") or [],
        state.get("candidate_hotels") or [],
    )
    errors = validate_itinerary(
        itinerary,
        known_place_ids=known,
        require_weather=True,
        weather_available=bool(state.get("weather")),
    )
    # Also require correct day count and destination.
    day_ok = len(itinerary.days) == case.expected_days
    dest_ok = itinerary.destination == case.expected_destination
    validation_ok = not errors
    score = _mean(
        [
            1.0 if day_ok else 0.0,
            1.0 if dest_ok else 0.0,
            1.0 if validation_ok else 0.0,
            1.0 if bool(itinerary.days) and all(day.activities for day in itinerary.days) else 0.0,
        ]
    )
    return score, {
        "itinerary_errors": errors,
        "itinerary_days": len(itinerary.days),
        "itinerary_destination": itinerary.destination,
    }


def _score_budget_validity(state: Dict[str, Any]) -> tuple[float, Dict[str, Any]]:
    raw = state.get("itinerary")
    if not raw:
        return 0.0, {"budget_note": "no itinerary"}
    itinerary = TripItinerary.model_validate(raw)
    within = itinerary.estimated_total_cost <= itinerary.total_budget
    breakdown = state.get("budget_breakdown") or {}
    breakdown_ok = True
    if breakdown:
        breakdown_ok = bool(breakdown.get("within_budget", within))
        try:
            total = Decimal(str(breakdown.get("total") or 0))
            budget = Decimal(str(breakdown.get("budget") or itinerary.total_budget))
            breakdown_ok = breakdown_ok and total <= budget
        except Exception:  # noqa: BLE001
            breakdown_ok = False
    score = _mean([1.0 if within else 0.0, 1.0 if breakdown_ok else 0.0])
    return score, {
        "estimated_total_cost": str(itinerary.estimated_total_cost),
        "total_budget": str(itinerary.total_budget),
        "within_budget": within,
        "breakdown_within": breakdown.get("within_budget"),
    }


def _score_duplicates(state: Dict[str, Any]) -> tuple[float, Dict[str, Any]]:
    raw = state.get("itinerary")
    if not raw:
        return 0.0, {"duplicate_days": []}
    itinerary = TripItinerary.model_validate(raw)
    bad_days: List[int] = []
    for day in itinerary.days:
        ids = [a.place_id for a in day.activities]
        if len(ids) != len(set(ids)):
            bad_days.append(day.day_number)
    if not itinerary.days:
        return 0.0, {"duplicate_days": []}
    score = 1.0 - (len(bad_days) / len(itinerary.days))
    return score, {"duplicate_days": bad_days}


def _grounded_names(state: Dict[str, Any]) -> Set[str]:
    names: Set[str] = set()
    for key in ("candidate_places", "candidate_restaurants", "candidate_hotels"):
        for item in state.get(key) or []:
            if item.get("name"):
                names.add(str(item["name"]).casefold())
    raw = state.get("itinerary")
    if raw:
        itinerary = TripItinerary.model_validate(raw)
        for day in itinerary.days:
            for activity in day.activities:
                names.add(activity.name.casefold())
    return names


def _catalog_names_by_destination() -> Dict[str, Set[str]]:
    provider = MockPlacesProvider()
    by_dest: Dict[str, Set[str]] = {}
    for place in provider._places.values():  # noqa: SLF001 - evaluation needs full catalog
        by_dest.setdefault(place.destination.casefold(), set()).add(place.name.casefold())
    return by_dest


def _score_unsupported_claims(state: Dict[str, Any]) -> tuple[float, Dict[str, Any]]:
    """Rate of catalog place names from other cities mentioned in free text."""
    grounded = _grounded_names(state)
    destination = str(state.get("destination") or "").casefold()
    by_dest = _catalog_names_by_destination()
    foreign: Set[str] = set()
    for dest, names in by_dest.items():
        if dest == destination:
            continue
        foreign |= names

    final = state.get("final_response") or {}
    blobs: List[str] = [
        str(final.get("headline") or ""),
        str(final.get("overview") or ""),
        *[str(x) for x in final.get("knowledge_notes") or []],
        *[str(x) for x in final.get("optimization_notes") or []],
        *[str(x) for x in final.get("budget_notes") or []],
        *[str(x) for x in final.get("weather_notes") or []],
    ]
    text = " ".join(blobs).casefold()
    # Longest names first to avoid partial overlaps.
    hits = []
    for name in sorted(foreign, key=len, reverse=True):
        if len(name) < 5:
            continue
        if name in text and name not in grounded:
            hits.append(name)

    # Rate relative to checked foreign names (cap denominator).
    checked = max(len([n for n in foreign if len(n) >= 5]), 1)
    rate = min(1.0, len(hits) / checked)
    # Also scale: if any hit, report at least a small rate; primary metric is count/checked.
    return rate, {"unsupported_claim_names": hits, "unsupported_claim_count": len(hits)}


def _score_hallucinations(state: Dict[str, Any]) -> tuple[float, Dict[str, Any]]:
    """Fraction of itinerary activities whose place_id is not in the mock catalog."""
    provider = MockPlacesProvider()
    known_catalog = set(provider._places.keys())  # noqa: SLF001
    raw = state.get("itinerary")
    if not raw:
        return 1.0, {"hallucinated_place_ids": ["missing_itinerary"]}
    itinerary = TripItinerary.model_validate(raw)
    activities = [a for day in itinerary.days for a in day.activities]
    if not activities:
        return 1.0, {"hallucinated_place_ids": ["empty_itinerary"]}
    bad = [a.place_id for a in activities if a.place_id not in known_catalog]
    # Also treat unknown-to-candidates as hallucinations.
    known_candidates = set(
        known_ids_from_candidates(
            state.get("candidate_places") or [],
            state.get("candidate_restaurants") or [],
            state.get("candidate_hotels") or [],
        )
    )
    bad_candidate = [
        a.place_id
        for a in activities
        if a.place_id not in known_candidates and a.place_id not in bad
    ]
    all_bad = bad + bad_candidate
    rate = len(all_bad) / len(activities)
    return rate, {
        "hallucinated_place_ids": all_bad,
        "activity_count": len(activities),
    }


def _mean(values: Iterable[float]) -> float:
    items = list(values)
    if not items:
        return 0.0
    return sum(items) / len(items)
