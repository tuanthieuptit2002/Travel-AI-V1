import type { TripPlanResponse } from "../lib/api";
import { BudgetSummary } from "./BudgetSummary";
import { ItineraryPanel } from "./ItineraryPanel";
import { MapPlaceholder } from "./MapPlaceholder";
import { WeatherCards } from "./WeatherCards";

type TripResultPanelProps = {
  plan: Pick<
    TripPlanResponse,
    | "destination"
    | "origin"
    | "start_date"
    | "end_date"
    | "travelers"
    | "budget"
    | "currency"
    | "estimated_total_cost"
    | "summary"
    | "itinerary"
    | "warnings"
    | "recommendations"
    | "weather_notes"
    | "is_valid"
    | "trip_id"
  >;
};

export function TripResultPanel({ plan }: TripResultPanelProps) {
  return (
    <div className="space-y-5">
      <section className="relative overflow-hidden rounded-2xl border border-tide/10 bg-foam/90 p-5 shadow-soft">
        <div
          aria-hidden
          className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-[radial-gradient(circle,rgba(242,102,59,0.10),transparent_70%)]"
        />
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-lagoon">
          {plan.is_valid ? "Tóm tắt chuyến đi" : "Bản nháp cần xem lại"}
        </p>
        <h2 className="text-balance mt-2 font-display text-3xl tracking-tight text-tide">
          {plan.destination}
        </h2>
        <p className="mt-2 text-sm leading-6 text-ink/70">{plan.summary}</p>
        <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
          <div>
            <dt className="text-tide/55">Điểm đi</dt>
            <dd className="font-medium text-ink">{plan.origin || "—"}</dd>
          </div>
          <div>
            <dt className="text-tide/55">Số người</dt>
            <dd className="font-medium text-ink">{plan.travelers}</dd>
          </div>
          <div className="col-span-2">
            <dt className="text-tide/55">Thời gian</dt>
            <dd className="font-medium text-ink">
              {plan.start_date} → {plan.end_date}
            </dd>
          </div>
          {plan.trip_id ? (
            <div className="col-span-2">
              <dt className="text-tide/55">Mã chuyến đi đã lưu</dt>
              <dd className="break-all font-mono text-xs text-ink/70">{plan.trip_id}</dd>
            </div>
          ) : null}
        </dl>
      </section>

      <BudgetSummary
        budget={plan.budget}
        estimatedTotalCost={plan.estimated_total_cost}
        currency={plan.currency}
      />

      <WeatherCards notes={plan.weather_notes ?? []} />
      <MapPlaceholder destination={plan.destination} />

      {plan.warnings.length > 0 ? (
        <section className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
          <h3 className="text-sm font-semibold text-amber-950">Cảnh báo</h3>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-amber-950/90">
            {plan.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {plan.recommendations.length > 0 ? (
        <section className="rounded-2xl border border-tide/10 bg-foam/90 p-4">
          <h3 className="text-sm font-semibold text-tide">Gợi ý</h3>
          <ul className="mt-2 space-y-2 text-sm leading-6 text-ink/75">
            {plan.recommendations.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <section>
        <h2 className="mb-3 font-display text-2xl text-tide">Lịch trình</h2>
        <ItineraryPanel days={plan.itinerary} currency={plan.currency} />
      </section>
    </div>
  );
}
