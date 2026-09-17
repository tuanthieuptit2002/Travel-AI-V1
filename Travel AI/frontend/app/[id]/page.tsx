import Link from "next/link";

import { TripDetailView } from "../../components/TripDetailView";

type SavedTripPageProps = {
  params: Promise<{ id: string }>;
};

export default async function SavedTripPage({ params }: SavedTripPageProps) {
  const { id } = await params;

  return (
    <div className="min-h-screen bg-[linear-gradient(165deg,#f7fcfa_0%,#e3f1ec_45%,#cfe6de_100%)] text-ink">
      <header className="border-b border-tide/10 bg-foam/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
          <Link href="/" className="font-display text-2xl tracking-tight text-tide hover:text-lagoon">
            TripMind<span className="text-coral">.</span>
          </Link>
          <Link
            href="/"
            className="rounded-full border border-tide/20 px-4 py-2 text-sm text-tide transition hover:border-lagoon hover:text-lagoon"
          >
            Lên kế hoạch mới
          </Link>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl px-4 py-10 sm:px-6 md:py-12">
        <div className="mb-7 flex flex-wrap items-end justify-between gap-3 border-b border-tide/10 pb-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-lagoon">Chuyến đi đã lưu</p>
            <h1 className="mt-1 font-display text-3xl text-tide">Lịch trình của bạn</h1>
          </div>
          <p className="break-all font-mono text-xs text-tide/50">{id}</p>
        </div>
        <TripDetailView tripId={id} />
      </main>
    </div>
  );
}
