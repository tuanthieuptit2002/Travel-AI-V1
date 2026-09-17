"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

import {
  PLANNING_STEPS,
  advanceLocalProgress,
  planTrip,
  type PlanTripPayload,
} from "../lib/api";
import {
  EMPTY_DRAFT,
  PlanDraft,
  draftToPayload,
  loadPlanDraft,
  savePlanDraft,
} from "../lib/plan-draft";
import { ChatTurn, type ConversationTurn } from "./ChatTurn";
import { PlanComposer } from "./PlanComposer";
import { PreferencesPanel } from "./PreferencesPanel";
import { SiteHeader, type PanelKey } from "./SiteHeader";
import { SlideOver } from "./SlideOver";
import { TripsList } from "./TripsList";

let turnSequence = 0;

function nextTurnId(prefix: string): string {
  turnSequence += 1;
  return `${prefix}-${Date.now()}-${turnSequence}`;
}

/**
 * `travelers` and `travel_pace` always carry defaults, so `buildUserRequest` is never
 * empty. Auto-starting a plan only makes sense with a real prompt or destination.
 */
function planDraftHasIntent(draft: PlanDraft): boolean {
  return draft.user_request.trim().length > 0 || draft.destination.trim().length > 0;
}

const HIGHLIGHTS = [
  { icon: "🗓️", title: "Lịch trình chi tiết", text: "Theo từng ngày và khung giờ" },
  { icon: "💰", title: "Ngân sách minh bạch", text: "Chi phí ước tính và phần còn lại" },
  { icon: "🌤️", title: "Thời tiết thực", text: "Dự báo và cảnh báo cho ngày đi" },
];

/**
 * Single landing page experience: hero composer → inline conversation → results.
 * Secondary surfaces (saved trips, preferences) open as drawers instead of routes.
 */
export function ChatLanding() {
  const searchParams = useSearchParams();
  const [draft, setDraft] = useState<PlanDraft>(EMPTY_DRAFT);
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const [activeTurnId, setActiveTurnId] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const [panel, setPanel] = useState<PanelKey | null>(null);
  const [tripsRefreshKey, setTripsRefreshKey] = useState(0);

  const bootstrappedRef = useRef(false);
  const activeTurnRef = useRef<string | null>(null);
  const lastTurnRef = useRef<HTMLDivElement | null>(null);

  const busy = activeTurnId !== null;

  useEffect(() => {
    activeTurnRef.current = activeTurnId;
  }, [activeTurnId]);

  useEffect(() => {
    const stored = loadPlanDraft();
    if (stored) setDraft(stored);
  }, []);

  useEffect(() => {
    if (!activeTurnId) return;
    setTurns((current) =>
      current.map((turn) =>
        turn.id === activeTurnId
          ? { ...turn, progress: advanceLocalProgress(PLANNING_STEPS, tick) }
          : turn,
      ),
    );
  }, [activeTurnId, tick]);

  useEffect(() => {
    if (!activeTurnId) return;
    if (tick >= PLANNING_STEPS.length - 1) return;
    const timer = window.setTimeout(() => setTick((value) => value + 1), 420);
    return () => window.clearTimeout(timer);
  }, [activeTurnId, tick]);

  useEffect(() => {
    if (!turns.length) return;
    lastTurnRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [turns.length]);


  const syncUrl = useCallback((nextPanel: PanelKey | null) => {
    if (typeof window === "undefined") return;
    const url = new URL(window.location.href);
    url.searchParams.delete("autostart");
    url.searchParams.delete("draft");
    url.searchParams.delete("trip");
    if (nextPanel) url.searchParams.set("panel", nextPanel);
    else url.searchParams.delete("panel");
    const query = url.searchParams.toString();
    window.history.pushState(null, "", `${url.pathname}${query ? `?${query}` : ""}`);
  }, []);

  const updateDraft = useCallback((next: PlanDraft) => {
    setDraft(next);
    savePlanDraft(next);
  }, []);

  const runPlan = useCallback(async (payload: PlanTripPayload) => {
    const request = payload.user_request.trim();
    if (!request || activeTurnRef.current) return;

    const turnId = nextTurnId("plan");
    activeTurnRef.current = turnId;

    setTurns((current) => [
      ...current,
      {
        id: turnId,
        kind: "plan",
        request,
        status: "planning",
        progress: advanceLocalProgress(PLANNING_STEPS, 0),
        plan: null,
        error: null,
      },
    ]);
    setTick(0);
    setActiveTurnId(turnId);
    setDraft((current) => {
      const next = { ...current, user_request: "" };
      savePlanDraft(next);
      return next;
    });

    try {
      const result = await planTrip(payload);
      setTurns((current) =>
        current.map((turn) =>
          turn.id === turnId
            ? {
                ...turn,
                status: "ready",
                plan: result,
                progress: result.progress.length
                  ? result.progress
                  : PLANNING_STEPS.map((step) => ({ ...step, status: "completed" })),
              }
            : turn,
        ),
      );
      setTripsRefreshKey((value) => value + 1);
    } catch (err) {
      setTurns((current) =>
        current.map((turn) =>
          turn.id === turnId
            ? {
                ...turn,
                status: "error",
                error:
                  err instanceof Error ? err.message : "Không thể lên kế hoạch chuyến đi lúc này.",
              }
            : turn,
        ),
      );
    } finally {
      activeTurnRef.current = null;
      setActiveTurnId(null);
    }
  }, []);

  const openSavedTrip = useCallback((tripId: string) => {
    setTurns((current) => {
      if (current.some((turn) => turn.kind === "trip" && turn.tripId === tripId)) return current;
      return [
        ...current,
        {
          id: nextTurnId("trip"),
          kind: "trip",
          request: "Xem lại chuyến đi đã lưu của tôi.",
          status: "ready",
          tripId,
          progress: [],
        },
      ];
    });
  }, []);

  const retryTurn = useCallback(
    (turn: ConversationTurn) => {
      void runPlan({ ...draftToPayload(draft), user_request: turn.request });
    },
    [draft, runPlan],
  );

  function openPanel(key: PanelKey) {
    const next = panel === key ? null : key;
    setPanel(next);
    syncUrl(next);
  }

  function closePanel() {
    setPanel(null);
    syncUrl(null);
  }

  function newConversation() {
    setTurns([]);
    setActiveTurnId(null);
    activeTurnRef.current = null;
    syncUrl(null);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  useEffect(() => {
    if (bootstrappedRef.current) return;
    bootstrappedRef.current = true;

    const stored = loadPlanDraft();
    const wantsAutostart =
      searchParams.get("autostart") === "1" || searchParams.get("draft") === "1";
    const tripParam = searchParams.get("trip");
    const panelParam = searchParams.get("panel");

    if (stored) setDraft(stored);
    if (panelParam === "trips" || panelParam === "preferences") setPanel(panelParam);

    if (tripParam) {
      openSavedTrip(tripParam);
      return;
    }
    if (wantsAutostart && stored && planDraftHasIntent(stored)) {
      void runPlan(draftToPayload(stored));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  const hasConversation = turns.length > 0;

  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden text-ink">
      {/* Ambient background: layered glows that drift slowly behind the content. */}
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute inset-0 bg-[linear-gradient(165deg,#f7fcfa_0%,#e3f1ec_45%,#cfe6de_100%)]" />
        <div className="absolute -top-32 right-[-10%] h-[32rem] w-[32rem] rounded-full bg-[radial-gradient(circle,rgba(15,118,110,0.16),transparent_65%)] animate-drift-a" />
        <div className="absolute bottom-[-20%] left-[-8%] h-[36rem] w-[36rem] rounded-full bg-[radial-gradient(circle,rgba(242,102,59,0.12),transparent_65%)] animate-drift-b" />
      </div>
      <SiteHeader
        activePanel={panel}
        hasConversation={hasConversation}
        onOpenPanel={openPanel}
        onNewConversation={newConversation}
      />

      {hasConversation ? (
        <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col px-4 pb-4 pt-6 sm:px-6">
          <div className="flex-1 space-y-8 pb-8">
            {turns.map((turn, index) => (
              <div
                key={turn.id}
                ref={index === turns.length - 1 ? lastTurnRef : undefined}
                className="scroll-mt-24"
              >
                <ChatTurn turn={turn} onRetry={retryTurn} />
              </div>
            ))}
          </div>

          <div className="sticky bottom-0 z-20 -mx-4 bg-[linear-gradient(180deg,rgba(247,252,250,0)_0%,rgba(227,241,236,0.9)_35%,rgba(207,230,222,1)_100%)] px-4 pb-4 pt-6 sm:-mx-6 sm:px-6">
            <PlanComposer
              draft={draft}
              onDraftChange={updateDraft}
              onSubmit={runPlan}
              busy={busy}
              variant="docked"
            />
            <p className="mt-2 text-center text-[0.7rem] text-tide/50">
              Nhấn Enter để gửi · Shift + Enter để xuống dòng · {turns.length} lượt trong cuộc trò chuyện này
            </p>
          </div>
        </main>
      ) : (
        <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center px-4 py-14 sm:px-6 lg:py-20">
          <div className="animate-fade-up text-center">
            <p className="inline-flex items-center gap-2 rounded-full border border-lagoon/20 bg-foam/70 px-4 py-1.5 text-[0.7rem] font-semibold uppercase tracking-[0.28em] text-lagoon backdrop-blur">
              <span aria-hidden className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-coral" />
              Lên kế hoạch bằng AI
            </p>
            <h1 className="text-balance mt-6 font-display text-5xl leading-[1.05] tracking-tight text-tide sm:text-6xl">
              Bạn muốn đi <em className="font-display italic text-coral">đâu</em> hôm nay?
            </h1>
            <p className="mx-auto mt-5 max-w-xl text-base leading-8 text-ink/70">
              Một trang duy nhất cho cả chuyến đi. Mô tả bằng ngôn ngữ tự nhiên — các agent lịch
              trình, ngân sách và thời tiết sẽ chạy và trả kết quả ngay trong cuộc trò chuyện.
            </p>
          </div>

          <div className="mt-9 animate-fade-up [animation-delay:120ms]">
            <PlanComposer
              draft={draft}
              onDraftChange={updateDraft}
              onSubmit={runPlan}
              busy={busy}
              variant="hero"
            />
          </div>

          <ul className="mt-8 grid gap-3 sm:grid-cols-3">
            {HIGHLIGHTS.map((item, index) => (
              <li
                key={item.title}
                className="group animate-fade-up rounded-2xl border border-white/60 bg-white/55 px-4 py-4 shadow-soft backdrop-blur-sm transition duration-300 hover:-translate-y-0.5 hover:bg-white/80 hover:shadow-lift"
                style={{ animationDelay: `${240 + index * 90}ms` }}
              >
                <span aria-hidden className="text-lg">{item.icon}</span>
                <p className="mt-1.5 text-sm font-semibold text-tide">{item.title}</p>
                <p className="mt-0.5 text-xs leading-5 text-tide/65">{item.text}</p>
              </li>
            ))}
          </ul>

          <p className="mt-8 text-center text-xs leading-6 text-tide/50 animate-fade-up [animation-delay:520ms]">
            Muốn xem lại kế hoạch cũ? Mở
            <button
              type="button"
              onClick={() => openPanel("trips")}
              className="mx-1 font-medium text-lagoon underline-offset-2 hover:underline"
            >
              Chuyến đi đã lưu
            </button>
            hoặc tinh chỉnh
            <button
              type="button"
              onClick={() => openPanel("preferences")}
              className="mx-1 font-medium text-lagoon underline-offset-2 hover:underline"
            >
              Sở thích
            </button>
            của bạn.
          </p>
        </main>
      )}

      <SlideOver
        open={panel === "trips"}
        title="Chuyến đi đã lưu"
        description="Chọn một chuyến đi để xem lại ngay trong cuộc trò chuyện."
        onClose={closePanel}
      >
        <TripsList
          refreshKey={tripsRefreshKey}
          onStartPlanning={() => {
            closePanel();
            window.scrollTo({ top: 0, behavior: "smooth" });
          }}
          onSelect={(trip) => {
            openSavedTrip(trip.id);
            closePanel();
          }}
        />
      </SlideOver>

      <SlideOver
        open={panel === "preferences"}
        title="Sở thích du lịch"
        description="Sở thích dài hạn được tải trước khi lập kế hoạch."
        onClose={closePanel}
      >
        <PreferencesPanel />
      </SlideOver>
    </div>
  );
}