"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { TripSummary, formatMoney, listTrips } from "../lib/api";
import { TripListSkeleton } from "./Skeleton";

const STATUS_LABEL: Record<string, string> = {
  planned: "đã lên kế hoạch",
  needs_review: "cần xem lại",
  draft: "nháp",
};

export function TripsList() {
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
  }, []);

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
      <div className="rounded-2xl border border-dashed border-tide/20 bg-foam/70 p-8 text-sm text-ink/65">
        Chưa có chuyến đi nào được lưu.{" "}
        <Link href="/" className="font-medium text-lagoon underline-offset-2 hover:underline">
          Lên kế hoạch
        </Link>{" "}
        để tạo mới.
      </div>
    );
  }

  return (
    <ul className="space-y-3">
      {items.map((trip) => (
        <li key={trip.id}>
          <Link
            href={`/trips/${trip.id}`}
            className="block rounded-2xl border border-tide/10 bg-foam/90 p-5 transition hover:border-lagoon/40"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="font-display text-2xl text-tide">{trip.destination}</h2>
                <p className="mt-1 text-sm text-ink/60">
                  {trip.start_date} → {trip.end_date} · {trip.travelers} người
                </p>
                {trip.summary ? (
                  <p className="mt-2 line-clamp-2 text-sm text-ink/70">{trip.summary}</p>
                ) : null}
              </div>
              <div className="text-right text-sm">
                <p className="rounded-full bg-mist px-3 py-1 text-xs uppercase tracking-wide text-tide">
                  {STATUS_LABEL[trip.status] || trip.status}
                </p>
                {trip.estimated_total_cost != null ? (
                  <p className="mt-3 font-medium text-ink">
                    {formatMoney(trip.estimated_total_cost, trip.currency)}
                  </p>
                ) : null}
              </div>
            </div>
          </Link>
        </li>
      ))}
    </ul>
  );
}
