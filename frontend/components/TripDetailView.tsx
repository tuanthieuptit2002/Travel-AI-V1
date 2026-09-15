"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { TripDetail, getTrip } from "../lib/api";
import { PlanPageSkeleton } from "./Skeleton";
import { TripResultPanel } from "./TripResultPanel";

type TripDetailViewProps = {
  tripId: string;
};

export function TripDetailView({ tripId }: TripDetailViewProps) {
  const [trip, setTrip] = useState<TripDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const result = await getTrip(tripId);
        if (active) setTrip(result);
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : "Không thể tải chuyến đi.");
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [tripId]);

  if (loading) return <PlanPageSkeleton />;
  if (error || !trip) {
    return (
      <div className="space-y-4">
        <p className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error || "Không tìm thấy chuyến đi."}
        </p>
        <Link href="/trips" className="text-sm text-lagoon hover:underline">
          Quay lại danh sách chuyến đi
        </Link>
      </div>
    );
  }

  return (
    <TripResultPanel
      plan={{
        trip_id: trip.id,
        destination: trip.destination,
        origin: trip.origin,
        start_date: trip.start_date,
        end_date: trip.end_date,
        travelers: trip.travelers,
        budget: trip.budget ?? "0",
        currency: trip.currency,
        estimated_total_cost: trip.estimated_total_cost ?? "0",
        summary: trip.summary ?? "",
        itinerary: trip.itinerary,
        warnings: trip.warnings,
        recommendations: trip.recommendations,
        weather_notes: trip.weather_notes,
        is_valid: trip.status !== "needs_review",
      }}
    />
  );
}
