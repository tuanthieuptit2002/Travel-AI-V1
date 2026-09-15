type MapPlaceholderProps = {
  destination: string;
};

export function MapPlaceholder({ destination }: MapPlaceholderProps) {
  return (
    <section className="overflow-hidden rounded-2xl border border-tide/10 bg-foam/90">
      <div className="border-b border-tide/10 px-5 py-3">
        <h2 className="font-display text-xl text-tide">Bản đồ</h2>
        <p className="text-sm text-ink/60">{destination}</p>
      </div>
      <div className="relative flex h-48 items-center justify-center bg-[linear-gradient(135deg,#d7ebe4_0%,#f4fbf8_45%,#e7f3ef_100%)]">
        <div className="absolute inset-6 rounded-xl border border-dashed border-tide/25" />
        <p className="relative z-10 max-w-xs px-4 text-center text-sm text-tide/70">
          Xem trước bản đồ cho {destination}. Bản đồ trực tiếp sẽ được kết nối sau.
        </p>
      </div>
    </section>
  );
}
