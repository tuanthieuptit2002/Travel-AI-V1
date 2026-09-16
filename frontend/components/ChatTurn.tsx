"use client";

import type { ProgressStep, TripPlanResponse } from "../lib/api";
import { ProgressList } from "./ProgressList";
import { TripDetailView } from "./TripDetailView";
import { TripResultPanel } from "./TripResultPanel";

export type ConversationTurn = {
  id: string;
  kind: "plan" | "trip";
  request: string;
  status: "planning" | "ready" | "error";
  tripId?: string;
  plan?: TripPlanResponse | null;
  progress: ProgressStep[];
  error?: string | null;
};

type ChatTurnProps = {
  turn: ConversationTurn;
  onRetry?: (turn: ConversationTurn) => void;
};

export function ChatTurn({ turn, onRetry }: ChatTurnProps) {
  return (
    <article className="animate-fade-up space-y-4">
      <div className="flex justify-end">
        <p className="max-w-[85%] rounded-2xl rounded-br-sm bg-gradient-to-br from-lagoon to-tide px-4 py-2.5 text-sm leading-6 text-foam shadow-soft">
          {turn.request}
        </p>
      </div>

      <div className="rounded-2xl border border-tide/10 bg-foam/85 p-5 shadow-soft backdrop-blur-sm">
        <div className="flex items-center gap-2.5">
          <span
            aria-hidden
            className="inline-flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-lagoon to-tide text-[0.65rem] font-bold text-foam"
          >
            ✦
          </span>
          <span className="text-xs font-semibold uppercase tracking-[0.16em] text-tide/60">
            {turn.kind === "trip" ? "Chuyến đi đã lưu" : "TripMind"}
          </span>
        </div>

        <div className="mt-4 space-y-5">
          {turn.kind === "trip" && turn.tripId ? (
            <TripDetailView tripId={turn.tripId} />
          ) : null}

          {turn.status === "planning" ? (
            <>
              <p className="text-sm leading-6 text-ink/70">
                Đang gọi trợ lý du lịch TripMind… Các agent đang truy vấn địa điểm, thời tiết và ngân sách.
              </p>
              <ProgressList steps={turn.progress} />
            </>
          ) : null}

          {turn.status === "error" ? (
            <div className="space-y-3">
              <p className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
                {turn.error || "Không thể lên kế hoạch chuyến đi lúc này."}
              </p>
              {onRetry ? (
                <button
                  type="button"
                  onClick={() => onRetry(turn)}
                  className="rounded-full border border-tide/20 px-4 py-2 text-sm text-tide transition hover:border-lagoon hover:text-lagoon"
                >
                  Thử lại yêu cầu này
                </button>
              ) : null}
            </div>
          ) : null}

          {turn.status === "ready" && turn.plan ? <TripResultPanel plan={turn.plan} /> : null}
        </div>
      </div>
    </article>
  );
}