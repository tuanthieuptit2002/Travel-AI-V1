"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { TripSummary, formatMoney, listTrips } from "../lib/api";
import { TripListSkeleton } from "./Skeleton";

const STATUS_STYLE: Record<string, string> = {
  planned: "bg-mist text-lagoon",
  needs_review: "bg-amber-100 text-amber-800",
  draft: "bg-tide/10 text-tide/70",
};

const STATUS_LABEL: Record<string, string> = {
  planned: "đã lên kế hoạch",
  needs_review: "cần xem lại",
  draft: "nháp",
};

type TripsListProps = {
  onStartPlanning?: () => void;
  refreshKey?: number;
};

export function TripsList({ onStartPlanning, refreshKey = 0 }: TripsListProps) {
  const [items, setItems] = useState<TripSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const result = await listTrips();
        if (active) setItems(result.items);
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : "Không thể tải danh sách chuyến đi.");
        }
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [refreshKey]);

  if (loading) return <TripListSkeleton />;
  if (error) {
    return (
      <p className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
        {error}
      </p>
    );
  }
  if (!items.length) {
    return (
      <div className="rounded-2xl border border-dashed border-tide/20 bg-foam/70 p-6 text-sm text-ink/65">
        Chưa có chuyến đi nào được lưu.
        {onStartPlanning ? (
          <>
            {" "}
            <button
              type="button"
              onClick={onStartPlanning}
              className="font-medium text-lagoon underline-offset-2 hover:underline"
            >
              Lên kế hoạch
            </button>{" "}
            để tạo mới.
          </>
        ) : null}
      </div>
    );
  }

  const cardClass =
    "block w-full rounded-2xl border border-tide/10 bg-foam/90 p-5 text-left shadow-soft transition duration-300 hover:-translate-y-0.5 hover:border-lagoon/40 hover:shadow-lift";

  return (
    <ul className="space-y-3">
      {items.map((trip) => {
        const content = (
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="font-display text-2xl text-tide">{trip.destination}</h3>
              <p className="mt-1 text-sm text-ink/60">
                {trip.start_date} → {trip.end_date} · {trip.travelers} người
              </p>
              {trip.summary ? (
                <p className="mt-2 line-clamp-2 text-sm text-ink/70">{trip.summary}</p>
              ) : null}
            </div>
            <div className="text-right text-sm">
              <p
                className={`rounded-full px-3 py-1 text-xs font-medium ${
                  STATUS_STYLE[trip.status] || "bg-tide/10 text-tide/70"
                }`}
              >
                {STATUS_LABEL[trip.status] || trip.status}
              </p>
              {trip.estimated_total_cost != null ? (
                <p className="mt-3 font-semibold tabular-nums text-ink">
                  {formatMoney(trip.estimated_total_cost, trip.currency)}
                </p>
              ) : null}
            </div>
          </div>
        );

        return (
          <li key={trip.id}>
            <Link href={`/${encodeURIComponent(trip.id)}`} className={cardClass}>
              {content}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
