import { SiteHeader } from "../../../components/SiteHeader";
import { TripDetailView } from "../../../components/TripDetailView";

type TripDetailPageProps = {
  params: Promise<{ id: string }>;
};

export default async function TripDetailPage({ params }: TripDetailPageProps) {
  const { id } = await params;

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,#f7fcfa_0%,#e7f3ef_100%)] text-ink">
      <SiteHeader active="trips" />
      <main className="mx-auto max-w-6xl px-6 py-8">
        <h1 className="font-display text-3xl text-tide sm:text-4xl">Chi tiết chuyến đi</h1>
        <p className="mt-1 text-sm text-ink/65">Được tải từ backend thực.</p>
        <div className="mt-6">
          <TripDetailView tripId={id} />
        </div>
      </main>
    </div>
  );
}
