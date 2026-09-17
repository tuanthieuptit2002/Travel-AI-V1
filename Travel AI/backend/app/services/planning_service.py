"""Application service that runs the travel agent and maps to public API models."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from app.agent.graph import run_travel_agent
from app.agent.models import FinalTravelResponse, TripItinerary
from app.api.schemas.trips import (
    CreateTripRequest,
    ItineraryActivityOut,
    ItineraryDayOut,
    PlanTripRequest,
    ProgressStepOut,
    TripDetailOut,
    TripListOut,
    TripPlanResponse,
    TripSummaryOut,
    WeatherForecastOut,
)
from app.services.trip_store import StoredTrip, TripStore, get_trip_store
from app.tools import ToolDependencies

logger = logging.getLogger(__name__)

PROGRESS_BLUEPRINT = [
    ("bootstrap", "Đang hiểu yêu cầu và tải ngữ cảnh"),
    ("supervisor", "Giám sát viên đang chọn agent cần chạy"),
    ("flight", "Flight Agent: tìm và xếp hạng vé máy bay"),
    ("hotel", "Hotel Agent: tìm và xếp hạng khách sạn"),
    ("place", "Place Agent: điểm tham quan và nhà hàng"),
    ("weather", "Weather Agent: phân tích thời tiết"),
    ("itinerary", "Itinerary Agent: dựng lịch trình"),
    ("budget", "Budget Agent: phân tích chi phí và tối ưu"),
    ("validation", "Validation Agent: kiểm tra lịch trình"),
    ("finalize", "Đang chuẩn bị gợi ý"),
    ("update_memory", "Đang lưu sở thích rõ ràng"),
]


class PlanningService:
    def __init__(
        self,
        *,
        store: Optional[TripStore] = None,
        dependencies: Optional[ToolDependencies] = None,
        reference_date: Optional[date] = None,
    ) -> None:
        self.store = store or get_trip_store()
        self.dependencies = dependencies or ToolDependencies.with_mocks()
        self.reference_date = reference_date

    def plan(self, request: PlanTripRequest) -> TripPlanResponse:
        from app.observability import bind_cost_tracker, get_cost_tracker, trace_span
        from app.security import detect_injection, sanitize_user_request

        bind_cost_tracker()
        raw_request = request.user_request
        injection_hits = detect_injection(raw_request)
        safe_request = sanitize_user_request(raw_request)
        if injection_hits:
            logger.warning(
                "Prompt-injection patterns filtered count=%s",
                len(injection_hits),
            )

        logger.info(
            "Planning trip request destination=%s travelers=%s",
            request.destination,
            request.travelers,
        )
        with trace_span("agent", "run_travel_agent"):
            agent_state = run_travel_agent(
                safe_request,
                user_id=str(request.user_id) if request.user_id else None,
                dependencies=self.dependencies,
                reference_date=self.reference_date or date.today(),
            )
        final_raw = agent_state.get("final_response")
        if not final_raw:
            logger.error("Travel agent returned no final_response")
            raise ValueError("Trợ lý du lịch không tạo được kế hoạch.")

        final = FinalTravelResponse.model_validate(final_raw)
        itinerary = self._apply_overrides(final.itinerary, request)
        warnings = list(final.validation_errors)
        if not final.is_valid and not warnings:
            warnings.append("Kế hoạch tạo ra chưa vượt qua kiểm tra.")
        if injection_hits:
            warnings.append("Một số đoạn trong yêu cầu đã được lọc vì lý do an toàn.")

        recommendations = self._build_recommendations(final, itinerary)
        weather = [WeatherForecastOut.model_validate(item.model_dump()) for item in final.weather]
        weather_notes = list(final.weather_notes)
        citations = list(final.citations)
        optimization_notes = list(final.optimization_notes)
        progress = [
            ProgressStepOut(id=step_id, label=label, status="completed")
            for step_id, label in PROGRESS_BLUEPRINT
        ]
        if not final.is_valid:
            for step in progress:
                if step.id == "validation":
                    step.status = "failed"
                    break
        # Mark flight step skipped when origin was absent (supervisor omitted it).
        completed = set(agent_state.get("completed_agents") or [])
        if "flight" not in completed:
            for step in progress:
                if step.id == "flight":
                    step.status = "skipped"
                    break

        tracker = get_cost_tracker()
        if tracker:
            logger.info("Agent cost summary %s", tracker.summary())

        response = TripPlanResponse(
            summary=final.overview or itinerary.summary,
            destination=itinerary.destination,
            origin=request.origin or itinerary.origin,
            start_date=itinerary.start_date,
            end_date=itinerary.end_date,
            travelers=itinerary.travelers,
            budget=itinerary.total_budget,
            currency=itinerary.currency,
            estimated_total_cost=itinerary.estimated_total_cost,
            itinerary=[self._day_out(day) for day in itinerary.days],
            warnings=warnings,
            recommendations=recommendations
            + list(final.knowledge_notes[:3])
            + optimization_notes[:3],
            weather=weather,
            weather_notes=weather_notes,
            citations=citations,
            optimization_notes=optimization_notes,
            progress=progress,
            is_valid=final.is_valid,
        )

        stored = self.store.create(
            StoredTrip(
                id=uuid4(),
                user_id=request.user_id,
                destination=response.destination,
                origin=response.origin,
                start_date=response.start_date,
                end_date=response.end_date,
                travelers=response.travelers,
                budget=response.budget,
                currency=response.currency,
                status="planned" if response.is_valid else "needs_review",
                summary=response.summary,
                estimated_total_cost=response.estimated_total_cost,
                itinerary=[day.model_dump(mode="json") for day in response.itinerary],
                warnings=response.warnings,
                recommendations=response.recommendations,
                weather=[item.model_dump(mode="json") for item in response.weather],
                weather_notes=response.weather_notes,
            )
        )
        response.trip_id = stored.id
        logger.info("Saved planned trip id=%s valid=%s", stored.id, response.is_valid)
        return response

    def create_trip(self, request: CreateTripRequest) -> TripDetailOut:
        stored = self.store.create(
            StoredTrip(
                id=uuid4(),
                user_id=request.user_id,
                destination=request.destination,
                origin=request.origin,
                start_date=request.start_date,
                end_date=request.end_date,
                travelers=request.travelers,
                budget=request.budget,
                currency=request.currency.upper(),
                status=request.status,
                summary=request.summary,
                estimated_total_cost=request.estimated_total_cost,
                itinerary=[day.model_dump(mode="json") for day in request.itinerary or []],
                warnings=request.warnings,
                recommendations=request.recommendations,
                weather_notes=request.weather_notes,
            )
        )
        return self._detail_out(stored)

    def get_trip(self, trip_id: UUID) -> Optional[TripDetailOut]:
        stored = self.store.get(trip_id)
        return self._detail_out(stored) if stored else None

    def list_trips(self, user_id: Optional[UUID] = None) -> TripListOut:
        items = [self._summary_out(trip) for trip in self.store.list(user_id=user_id)]
        return TripListOut(items=items, total=len(items))

    def _apply_overrides(self, itinerary: TripItinerary, request: PlanTripRequest) -> TripItinerary:
        data = itinerary.model_dump()
        if request.destination:
            data["destination"] = request.destination
        if request.origin is not None:
            data["origin"] = request.origin
        if request.start_date:
            data["start_date"] = request.start_date
        if request.end_date:
            data["end_date"] = request.end_date
        if request.travelers:
            data["travelers"] = request.travelers
        if request.budget is not None:
            data["total_budget"] = request.budget
        if request.currency:
            data["currency"] = request.currency.upper()
        return TripItinerary.model_validate(data)

    def _build_recommendations(
        self, final: FinalTravelResponse, itinerary: TripItinerary
    ) -> List[str]:
        recommendations: List[str] = []
        if itinerary.preferences:
            recommendations.append(
                "Ưu tiên các điểm khớp với: " + ", ".join(itinerary.preferences) + "."
            )
        recommendations.extend(final.budget_notes[:2])
        if itinerary.estimated_total_cost < itinerary.total_budget:
            remaining = itinerary.total_budget - itinerary.estimated_total_cost
            recommendations.append(
                f"Bạn còn khoảng {remaining} {itinerary.currency} ngân sách linh hoạt."
            )
        return recommendations

    def _day_out(self, day: Any) -> ItineraryDayOut:
        return ItineraryDayOut(
            day_number=day.day_number,
            date=day.date,
            theme=day.theme,
            activities=[
                ItineraryActivityOut(
                    place_id=activity.place_id,
                    name=activity.name,
                    kind=activity.kind.value if hasattr(activity.kind, "value") else str(activity.kind),
                    start_time=activity.start_time,
                    end_time=activity.end_time,
                    estimated_cost=activity.estimated_cost,
                    reason=activity.reason,
                    travel_time_from_previous=activity.travel_time_from_previous,
                    rating=activity.rating,
                    opening_hours=activity.opening_hours,
                )
                for activity in day.activities
            ],
        )

    def _summary_out(self, trip: StoredTrip) -> TripSummaryOut:
        return TripSummaryOut(
            id=trip.id,
            user_id=trip.user_id,
            destination=trip.destination,
            origin=trip.origin,
            start_date=trip.start_date,
            end_date=trip.end_date,
            travelers=trip.travelers,
            budget=trip.budget,
            currency=trip.currency,
            status=trip.status,
            summary=trip.summary,
            estimated_total_cost=trip.estimated_total_cost,
            created_at=trip.created_at,
        )

    def _detail_out(self, trip: StoredTrip) -> TripDetailOut:
        summary = self._summary_out(trip)
        itinerary = [ItineraryDayOut.model_validate(day) for day in trip.itinerary]
        return TripDetailOut(
            **summary.model_dump(),
            itinerary=itinerary,
            warnings=list(trip.warnings),
            recommendations=list(trip.recommendations),
            weather=[WeatherForecastOut.model_validate(item) for item in trip.weather],
            weather_notes=list(trip.weather_notes),
        )
