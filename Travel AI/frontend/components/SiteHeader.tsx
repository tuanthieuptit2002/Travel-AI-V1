"use client";

export type PanelKey = "trips" | "preferences";

type SiteHeaderProps = {
  activePanel?: PanelKey | null;
  hasConversation?: boolean;
  onOpenPanel?: (panel: PanelKey) => void;
  onNewConversation?: () => void;
};

const PANEL_BUTTONS: { key: PanelKey; label: string }[] = [
  { key: "trips", label: "Chuyến đi đã lưu" },
  { key: "preferences", label: "Sở thích" },
];

export function SiteHeader({
  activePanel = null,
  hasConversation = false,
  onOpenPanel,
  onNewConversation,
}: SiteHeaderProps) {
  return (
    <header className="sticky top-0 z-30 border-b border-tide/10 bg-foam/75 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-6 py-3">
        <button
          type="button"
          onClick={onNewConversation}
          className="group flex items-center gap-2.5"
          aria-label="TripMind AI — về đầu trang"
        >
          <span
            aria-hidden
            className="inline-flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-lagoon to-tide text-sm shadow-soft transition-transform duration-300 group-hover:-rotate-6 group-hover:scale-105"
          >
            <svg viewBox="0 0 24 24" className="h-4.5 w-4.5 text-foam" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 18, height: 18 }}>
              <circle cx="12" cy="12" r="10" />
              <polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76" fill="currentColor" stroke="none" />
            </svg>
          </span>
          <span className="font-display text-xl tracking-tight text-tide transition group-hover:text-lagoon">
            TripMind<span className="text-coral">.</span>
          </span>
        </button>
        <nav className="flex items-center gap-1.5 sm:gap-2">
          {PANEL_BUTTONS.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => onOpenPanel?.(item.key)}
              aria-pressed={activePanel === item.key}
              className={[
                "relative rounded-full px-3.5 py-1.5 text-sm transition duration-200",
                activePanel === item.key
                  ? "bg-tide text-foam shadow-soft"
                  : "text-tide/70 hover:bg-mist hover:text-tide",
              ].join(" ")}
            >
              {item.label}
            </button>
          ))}
          {hasConversation ? (
            <button
              type="button"
              onClick={onNewConversation}
              className="hidden rounded-full border border-tide/20 px-3.5 py-1.5 text-sm text-tide transition duration-200 hover:-translate-y-px hover:border-lagoon hover:text-lagoon sm:block"
            >
              Cuộc trò chuyện mới
            </button>
          ) : null}
        </nav>
      </div>
    </header>
  );
}
