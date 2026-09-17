"""Validate grounded itineraries before returning a final response."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Sequence, Set

from app.agent.models import TripItinerary


MAX_TRAVEL_MINUTES = 180
DAY_START = datetime.strptime("08:00", "%H:%M").time()
DAY_END = datetime.strptime("22:00", "%H:%M").time()


def validate_itinerary(
    itinerary: TripItinerary,
    *,
    known_place_ids: Sequence[str],
    require_weather: bool = True,
    weather_available: bool = True,
) -> List[str]:
    errors: List[str] = []
    known: Set[str] = set(known_place_ids)

    if itinerary.end_date < itinerary.start_date:
        errors.append("Ngày kết thúc trước ngày bắt đầu.")

    expected_days = (itinerary.end_date - itinerary.start_date).days + 1
    if len(itinerary.days) != expected_days:
        errors.append(
            f"Cần {expected_days} ngày lịch trình nhưng chỉ có {len(itinerary.days)}."
        )

    for day in itinerary.days:
        if not day.activities:
            errors.append(f"Ngày {day.day_number} không có hoạt động.")
            continue

        seen_place_ids: Set[str] = set()
        previous_end = None
        for activity in day.activities:
            if activity.place_id in seen_place_ids:
                errors.append(
                    f"Trùng place_id trong ngày {day.day_number}: {activity.place_id}."
                )
            seen_place_ids.add(activity.place_id)

            if activity.place_id not in known:
                errors.append(
                    f"Hoạt động {activity.name} dùng place_id không hợp lệ {activity.place_id}."
                )

            if activity.end_time <= activity.start_time:
                errors.append(
                    f"{activity.name} kết thúc trước hoặc bằng giờ bắt đầu vào ngày {day.day_number}."
                )

            if activity.start_time < DAY_START or activity.end_time > DAY_END:
                errors.append(
                    f"{activity.name} vào ngày {day.day_number} nằm ngoài giờ hoạt động."
                )

            if previous_end and activity.start_time < previous_end:
                errors.append(
                    f"Các hoạt động chồng giờ vào ngày {day.day_number} quanh {activity.name}."
                )
            previous_end = activity.end_time

            if activity.travel_time_from_previous > MAX_TRAVEL_MINUTES:
                errors.append(
                    f"Thời gian di chuyển tới {activity.name} ({activity.travel_time_from_previous} phút) "
                    "vượt giới hạn hợp lý."
                )

        expected_date = itinerary.start_date + timedelta(days=day.day_number - 1)
        if day.date != expected_date:
            errors.append(
                f"Ngày {day.day_number} ({day.date.isoformat()}) không khớp "
                f"ngày kỳ vọng {expected_date.isoformat()}."
            )

    if itinerary.estimated_total_cost > itinerary.total_budget:
        errors.append(
            f"Chi phí ước tính {itinerary.estimated_total_cost} vượt ngân sách "
            f"{itinerary.total_budget} {itinerary.currency}."
        )

    if require_weather and not weather_available:
        errors.append("Thiếu dữ liệu thời tiết từ công cụ.")

    if not known_place_ids:
        errors.append("Thiếu dữ liệu địa điểm từ công cụ.")

    return errors


def known_ids_from_candidates(
    places: Sequence[Dict],
    restaurants: Sequence[Dict],
    hotels: Sequence[Dict] | None = None,
) -> List[str]:
    payloads = list(places) + list(restaurants) + list(hotels or [])
    return [str(item["id"]) for item in payloads if "id" in item]
