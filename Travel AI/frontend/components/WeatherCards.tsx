import type { WeatherForecast } from "../lib/api";

type WeatherCardsProps = {
  forecasts: WeatherForecast[];
  notes: string[];
};

const conditionDetails: Array<{ match: string; label: string; icon: string }> = [
  { match: "thunder", label: "Dông", icon: "⛈️" },
  { match: "snow", label: "Có tuyết", icon: "❄️" },
  { match: "fog", label: "Sương mù", icon: "🌫️" },
  { match: "drizzle", label: "Mưa phùn", icon: "🌦️" },
  { match: "rain", label: "Có mưa", icon: "🌧️" },
  { match: "shower", label: "Mưa rào", icon: "🌧️" },
  { match: "overcast", label: "Âm u", icon: "☁️" },
  { match: "cloud", label: "Có mây", icon: "🌤️" },
  { match: "clear", label: "Trời quang", icon: "☀️" },
];

function weatherVisual(condition: string) {
  const normalized = condition.toLowerCase();
  return conditionDetails.find((item) => normalized.includes(item.match)) ?? {
    label: "Dự báo thời tiết",
    icon: "🌤️",
  };
}

function formatForecastDate(value: string) {
  const date = new Date(`${value}T12:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("vi-VN", {
    weekday: "short",
    day: "2-digit",
    month: "2-digit",
  }).format(date);
}

export function WeatherCards({ forecasts, notes }: WeatherCardsProps) {
  if (!forecasts.length && !notes.length) {
    return (
      <section className="rounded-2xl border border-tide/10 bg-foam/90 p-5">
        <h2 className="font-display text-xl text-tide">Thời tiết</h2>
        <p className="mt-2 text-sm text-ink/60">Chưa có dữ liệu dự báo cho ngày đi đã chọn.</p>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-tide/10 bg-foam/90 p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="font-display text-xl text-tide">Thời tiết</h2>
          <p className="mt-1 text-xs text-ink/55">Dự báo thực tế · Open-Meteo</p>
        </div>
        <span className="rounded-full bg-sun/15 px-3 py-1 text-xs font-medium text-tide">Theo ngày</span>
      </div>

      {forecasts.length ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {forecasts.map((forecast) => {
            const visual = weatherVisual(forecast.condition);
            return (
              <article
                key={`${forecast.forecast_date}-${forecast.destination}`}
                className="overflow-hidden rounded-2xl border border-lagoon/15 bg-[linear-gradient(135deg,rgba(255,255,255,0.94),rgba(224,243,238,0.82))] p-4 shadow-[0_8px_22px_rgba(12,91,83,0.06)]"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.12em] text-lagoon">
                      {formatForecastDate(forecast.forecast_date)}
                    </p>
                    <p className="mt-1 text-sm font-medium text-ink/80">{visual.label}</p>
                  </div>
                  <span aria-label={visual.label} className="text-4xl leading-none">
                    {visual.icon}
                  </span>
                </div>
                <div className="mt-4 flex items-end gap-2 text-tide">
                  <span className="font-display text-4xl leading-none">{Math.round(forecast.temperature_max_c)}°</span>
                  <span className="pb-0.5 text-sm text-ink/60">thấp {Math.round(forecast.temperature_min_c)}°C</span>
                </div>
                <dl className="mt-4 grid grid-cols-3 gap-2 border-t border-tide/10 pt-3 text-center text-xs">
                  <div>
                    <dt className="text-base">💧</dt>
                    <dd className="mt-1 font-medium text-ink/75">{forecast.precipitation_probability}%</dd>
                    <dd className="text-ink/45">mưa</dd>
                  </div>
                  <div>
                    <dt className="text-base">◌</dt>
                    <dd className="mt-1 font-medium text-ink/75">{forecast.humidity_percent}%</dd>
                    <dd className="text-ink/45">ẩm</dd>
                  </div>
                  <div>
                    <dt className="text-base">〰</dt>
                    <dd className="mt-1 font-medium text-ink/75">{Math.round(forecast.wind_speed_kph)} km/h</dd>
                    <dd className="text-ink/45">gió</dd>
                  </div>
                </dl>
              </article>
            );
          })}
        </div>
      ) : (
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {notes.map((note) => (
          <article
            key={note}
            className="rounded-xl border border-lagoon/15 bg-mist/60 px-4 py-3 text-sm text-ink/80"
          >
            {note}
          </article>
          ))}
        </div>
      )}
    </section>
  );
}
