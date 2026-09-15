import type { ItineraryActivity, ItineraryDay } from "../lib/api";
import { formatMoney, formatTime } from "../lib/api";

type ActivityItemProps = {
  activity: ItineraryActivity;
  currency: string;
};

const KIND_LABEL: Record<string, string> = {
  activity: "hoạt động",
  restaurant: "nhà hàng",
};

function ActivityItem({ activity, currency }: ActivityItemProps) {
  return (
    <li className="relative pl-6">
      <span className="absolute left-0 top-1.5 h-2.5 w-2.5 rounded-full bg-lagoon" aria-hidden />
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm font-semibold text-ink">
          {activity.name}
          <span className="ml-2 text-xs font-normal uppercase tracking-wide text-tide/50">
            {KIND_LABEL[activity.kind] || activity.kind}
          </span>
        </p>
        <p className="text-xs text-ink/55">
          {formatTime(activity.start_time)}–{formatTime(activity.end_time)}
        </p>
      </div>
      <p className="mt-1 text-sm text-ink/70">{activity.reason}</p>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-tide/70">
        <span>{formatMoney(activity.estimated_cost, currency)}</span>
        {activity.rating != null ? <span>Đánh giá {activity.rating.toFixed(1)}</span> : null}
        {activity.travel_time_from_previous > 0 ? (
          <span>{activity.travel_time_from_previous} phút từ điểm trước</span>
        ) : null}
        {activity.opening_hours ? <span>{activity.opening_hours}</span> : null}
      </div>
    </li>
  );
}

type ItineraryDayCardProps = {
  day: ItineraryDay;
  currency: string;
};

export function ItineraryDayCard({ day, currency }: ItineraryDayCardProps) {
  const attractions = day.activities.filter((item) => item.kind !== "restaurant");
  const restaurants = day.activities.filter((item) => item.kind === "restaurant");
  const dayCost = day.activities.reduce((sum, item) => sum + Number(item.estimated_cost), 0);

  return (
    <article className="rounded-2xl border border-tide/10 bg-foam/90 p-5">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h3 className="font-display text-2xl text-tide">Ngày {day.day_number}</h3>
          <p className="text-sm text-ink/55">{day.date}</p>
          {day.theme ? (
            <p className="mt-1 text-xs uppercase tracking-[0.14em] text-lagoon">{day.theme}</p>
          ) : null}
        </div>
        <p className="text-sm font-medium text-ink">
          Ước tính ngày: {formatMoney(dayCost, currency)}
        </p>
      </header>

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-[0.14em] text-tide/55">
            Dòng thời gian
          </h4>
          <ol className="relative mt-3 space-y-4 before:absolute before:bottom-1 before:left-[4px] before:top-1 before:w-px before:bg-tide/15">
            {day.activities.map((activity) => (
              <ActivityItem
                key={`${day.day_number}-${activity.place_id}-${activity.start_time}`}
                activity={activity}
                currency={currency}
              />
            ))}
          </ol>
        </div>

        <div className="space-y-4">
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-[0.14em] text-tide/55">
              Điểm tham quan
            </h4>
            <ul className="mt-2 space-y-1 text-sm text-ink/75">
              {attractions.length ? (
                attractions.map((item) => <li key={item.place_id}>{item.name}</li>)
              ) : (
                <li className="text-ink/45">Chưa có điểm tham quan</li>
              )}
            </ul>
          </div>
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-[0.14em] text-tide/55">
              Nhà hàng
            </h4>
            <ul className="mt-2 space-y-1 text-sm text-ink/75">
              {restaurants.length ? (
                restaurants.map((item) => <li key={item.place_id}>{item.name}</li>)
              ) : (
                <li className="text-ink/45">Chưa có nhà hàng</li>
              )}
            </ul>
          </div>
        </div>
      </div>
    </article>
  );
}

type ItineraryPanelProps = {
  days: ItineraryDay[];
  currency: string;
};

export function ItineraryPanel({ days, currency }: ItineraryPanelProps) {
  if (!days.length) {
    return (
      <section className="rounded-2xl border border-dashed border-tide/20 bg-foam/60 p-6 text-sm text-ink/60">
        Chưa có ngày lịch trình.
      </section>
    );
  }

  return (
    <div className="space-y-4">
      {days.map((day) => (
        <ItineraryDayCard key={`${day.day_number}-${day.date}`} day={day} currency={currency} />
      ))}
    </div>
  );
}
