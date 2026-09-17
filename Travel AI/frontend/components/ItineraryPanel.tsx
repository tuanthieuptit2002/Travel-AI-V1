import type { ItineraryActivity, ItineraryDay } from "../lib/api";
import { formatMoney, formatTime } from "../lib/api";

type ActivityItemProps = {
  activity: ItineraryActivity;
  currency: string;
  destination: string;
};

const KIND_LABEL: Record<string, string> = {
  activity: "hoạt động",
  restaurant: "nhà hàng",
};

function ActivityItem({ activity, currency, destination }: ActivityItemProps) {
  const mapsQuery = `${activity.name}, ${destination}`;
  const mapsUrl = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(mapsQuery)}`;

  return (
    <li className="relative pl-7">
      <span
        aria-hidden
        className={[
          "absolute left-0 top-1.5 flex h-3.5 w-3.5 items-center justify-center rounded-full border-2 border-foam ring-2",
          activity.kind === "restaurant" ? "bg-coral ring-coral/20" : "bg-lagoon ring-lagoon/20",
        ].join(" ")}
      />
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm font-semibold text-ink">
          {activity.name}
          <span className="ml-2 rounded-full bg-mist px-2 py-0.5 text-[0.65rem] font-medium uppercase tracking-wide text-tide/60">
            {KIND_LABEL[activity.kind] || activity.kind}
          </span>
        </p>
        <p className="font-mono text-xs tabular-nums text-ink/55">
          {formatTime(activity.start_time)}–{formatTime(activity.end_time)}
        </p>
      </div>
      <p className="mt-1 text-sm leading-6 text-ink/70">{activity.reason}</p>
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-tide/70">
        <span className="rounded-full bg-mist/80 px-2 py-0.5 font-medium tabular-nums text-tide">
          {formatMoney(activity.estimated_cost, currency)}
        </span>
        {activity.rating != null ? (
          <span className="tabular-nums">★ {activity.rating.toFixed(1)}</span>
        ) : null}
        {activity.travel_time_from_previous > 0 ? (
          <span>· {activity.travel_time_from_previous} phút từ điểm trước</span>
        ) : null}
        {activity.opening_hours ? <span>· {activity.opening_hours}</span> : null}
        <a
          href={mapsUrl}
          target="_blank"
          rel="noreferrer"
          className="font-semibold text-lagoon underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lagoon"
        >
          Xem trên Google Maps ↗
        </a>
      </div>
    </li>
  );
}

type ItineraryDayCardProps = {
  day: ItineraryDay;
  currency: string;
  destination: string;
};

export function ItineraryDayCard({ day, currency, destination }: ItineraryDayCardProps) {
  const attractions = day.activities.filter((item) => item.kind !== "restaurant");
  const restaurants = day.activities.filter((item) => item.kind === "restaurant");
  const dayCost = day.activities.reduce((sum, item) => sum + Number(item.estimated_cost), 0);

  return (
    <article className="group overflow-hidden rounded-2xl border border-tide/10 bg-foam/90 shadow-soft transition duration-300 hover:shadow-lift">
      <header className="flex flex-wrap items-end justify-between gap-3 border-b border-tide/10 bg-gradient-to-r from-mist/70 to-transparent px-5 py-4">
        <div className="flex items-end gap-3.5">
          <span
            aria-hidden
            className="font-display text-4xl leading-none tracking-tight text-coral/90 transition-transform duration-300 group-hover:-translate-y-0.5"
          >
            {String(day.day_number).padStart(2, "0")}
          </span>
          <div>
            <h3 className="font-display text-xl text-tide">Ngày {day.day_number}</h3>
            <p className="text-xs text-ink/55">{day.date}</p>
            {day.theme ? (
              <p className="mt-0.5 text-[0.68rem] font-semibold uppercase tracking-[0.14em] text-lagoon">
                {day.theme}
              </p>
            ) : null}
          </div>
        </div>
        <p className="rounded-full bg-tide px-3 py-1 text-xs font-medium tabular-nums text-foam">
          Ước tính ngày: {formatMoney(dayCost, currency)}
        </p>
      </header>

      <div className="grid gap-5 p-5 lg:grid-cols-2">
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
                destination={destination}
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
  destination: string;
};

export function ItineraryPanel({ days, currency, destination }: ItineraryPanelProps) {
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
        <ItineraryDayCard
          key={`${day.day_number}-${day.date}`}
          day={day}
          currency={currency}
          destination={destination}
        />
      ))}
    </div>
  );
}
