type MapPlaceholderProps = {
  destination: string;
};

function googleMapsSearchUrl(query: string): string {
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`;
}

export function MapPlaceholder({ destination }: MapPlaceholderProps) {
  return (
    <section className="overflow-hidden rounded-2xl border border-tide/10 bg-foam/90 shadow-soft">
      <div className="border-b border-tide/10 px-5 py-3">
        <h2 className="font-display text-xl text-tide">Bản đồ</h2>
        <p className="text-sm text-ink/60">{destination}</p>
      </div>
      <div className="relative flex h-52 items-center justify-center bg-[linear-gradient(135deg,#d7ebe4_0%,#f4fbf8_45%,#e7f3ef_100%)]">
        {/* Grid hint evokes map tiles without loading an external map. */}
        <div
          aria-hidden
          className="absolute inset-0 opacity-40 [background-image:linear-gradient(rgba(19,78,74,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(19,78,74,0.08)_1px,transparent_1px)] [background-size:32px_32px]"
        />
        <div
          aria-hidden
          className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2"
        >
          <span className="absolute -inset-5 animate-ping rounded-full bg-lagoon/15" />
          <span className="relative flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-lagoon to-tide shadow-lift">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="#f4fbf8"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-4 w-4"
              aria-hidden
            >
              <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 1 1 16 0Z" />
              <circle cx="12" cy="10" r="3" />
            </svg>
          </span>
        </div>
        <a
          href={googleMapsSearchUrl(destination)}
          target="_blank"
          rel="noreferrer"
          className="absolute bottom-3 z-10 inline-flex items-center gap-1.5 rounded-full bg-tide px-3 py-2 text-xs font-semibold text-foam shadow-soft transition hover:bg-lagoon focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lagoon focus-visible:ring-offset-2"
        >
          Mở {destination} trên Google Maps
          <span aria-hidden>↗</span>
        </a>
      </div>
    </section>
  );
}
