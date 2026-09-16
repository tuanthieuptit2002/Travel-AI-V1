"use client";

import { useEffect, useRef } from "react";

type SlideOverProps = {
  open: boolean;
  title: string;
  description?: string;
  onClose: () => void;
  children: React.ReactNode;
};

/**
 * Right-hand drawer used for secondary surfaces (saved trips, preferences) so the
 * landing page never navigates away from the conversation.
 */
export function SlideOver({ open, title, description, onClose, children }: SlideOverProps) {
  const panelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKeyDown);
    panelRef.current?.focus();
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button
        type="button"
        aria-label="Đóng bảng"
        onClick={onClose}
        className="absolute inset-0 h-full w-full animate-fade-in cursor-default bg-ink/35 backdrop-blur-[2px]"
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className="relative flex h-full w-full max-w-xl animate-slide-in-right flex-col border-l border-tide/10 bg-foam shadow-[0_24px_80px_rgba(16,36,31,0.18)] outline-none"
      >
        <header className="flex items-start justify-between gap-4 border-b border-tide/10 px-6 py-4">
          <div>
            <h2 className="font-display text-2xl text-tide">{title}</h2>
            {description ? <p className="mt-1 text-sm text-ink/60">{description}</p> : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Đóng bảng"
            className="rounded-full border border-tide/15 p-2 text-tide transition duration-200 hover:border-lagoon hover:bg-mist hover:text-lagoon"
          >
            <svg
              aria-hidden
              viewBox="0 0 20 20"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              className="h-4 w-4"
            >
              <path d="M5 5l10 10M15 5L5 15" />
            </svg>
          </button>
        </header>
        <div className="flex-1 overflow-y-auto px-6 py-5">{children}</div>
      </div>
    </div>
  );
}