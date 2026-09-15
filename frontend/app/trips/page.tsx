import { SiteHeader } from "../../components/SiteHeader";
import { TripsList } from "../../components/TripsList";

export default function TripsPage() {
  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,#f7fcfa_0%,#e7f3ef_100%)] text-ink">
      <SiteHeader active="trips" />
      <main className="mx-auto max-w-6xl px-6 py-8">
        <h1 className="font-display text-3xl text-tide sm:text-4xl">Chuyến đi</h1>
        <p className="mt-1 text-sm text-ink/65">Các kế hoạch đã lưu từ API TripMind.</p>
        <div className="mt-6">
          <TripsList />
        </div>
      </main>
    </div>
  );
}
