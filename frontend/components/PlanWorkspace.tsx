"use client";

import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

import {
  PLANNING_STEPS,
  ProgressStep,
  TripPlanResponse,
  planTrip,
} from "../lib/api";
import {
  EMPTY_DRAFT,
  PlanDraft,
  buildUserRequest,
  draftToPayload,
  loadPlanDraft,
  savePlanDraft,
} from "../lib/plan-draft";
import { ProgressList } from "./ProgressList";
import { PlanPageSkeleton } from "./Skeleton";
import { TripResultPanel } from "./TripResultPanel";

type ConversationMessage = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
};

function advanceLocalProgress(steps: ProgressStep[], tick: number): ProgressStep[] {
  return steps.map((step, index) => {
    if (index < tick) return { ...step, status: "completed" };
    if (index === tick) return { ...step, status: "running" };
    return { ...step, status: "pending" };
  });
}

export function PlanWorkspace() {
  const searchParams = useSearchParams();
  const autostart = searchParams.get("autostart") === "1";
  const startedRef = useRef(false);

  const [draft, setDraft] = useState<PlanDraft>(EMPTY_DRAFT);
  const [followUp, setFollowUp] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [plan, setPlan] = useState<TripPlanResponse | null>(null);
  const [progress, setProgress] = useState<ProgressStep[]>(PLANNING_STEPS);
  const [tick, setTick] = useState(0);
  const [messages, setMessages] = useState<ConversationMessage[]>([
    {
      id: "welcome",
      role: "system",
      content: "Mô tả chuyến đi hoặc chỉnh chi tiết, rồi chạy lập kế hoạch với API TripMind.",
    },
  ]);

  useEffect(() => {
    const stored = loadPlanDraft();
    if (stored) setDraft(stored);
  }, []);

  useEffect(() => {
    if (!loading) return;
    setProgress(advanceLocalProgress(PLANNING_STEPS, tick));
    if (tick >= PLANNING_STEPS.length - 1) return;
    const timer = window.setTimeout(() => setTick((value) => value + 1), 400);
    return () => window.clearTimeout(timer);
  }, [loading, tick]);

  useEffect(() => {
    if (!autostart || startedRef.current) return;
    const stored = loadPlanDraft();
    if (!stored) return;
    startedRef.current = true;
    setDraft(stored);
    void runPlan(stored);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autostart]);

  async function runPlan(nextDraft: PlanDraft) {
    const payload = draftToPayload(nextDraft);
    if (!payload.user_request.trim()) {
      setError("Hãy thêm yêu cầu du lịch hoặc điểm đến trước khi lên kế hoạch.");
      return;
    }

    setError(null);
    setPlan(null);
    setLoading(true);
    setTick(0);
    setProgress(advanceLocalProgress(PLANNING_STEPS, 0));
    setMessages((current) => [
      ...current,
      { id: `user-${Date.now()}`, role: "user", content: payload.user_request },
      {
        id: `assistant-start-${Date.now()}`,
        role: "assistant",
        content: "Đang gọi trợ lý du lịch TripMind…",
      },
    ]);

    try {
      const result = await planTrip(payload);
      setPlan(result);
      setProgress(
        result.progress.length
          ? result.progress
          : PLANNING_STEPS.map((step) => ({ ...step, status: "completed" })),
      );
      setMessages((current) => [
        ...current,
        {
          id: `assistant-done-${Date.now()}`,
          role: "assistant",
          content: result.is_valid
            ? `Đã sẵn sàng lịch trình cho ${result.destination}. Xem chi tiết bên phải.`
            : `Đã có bản nháp cho ${result.destination}, nhưng vẫn còn vấn đề cần xem lại.`,
        },
      ]);
      savePlanDraft(nextDraft);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Đã xảy ra lỗi.";
      setError(message);
      setProgress((current) =>
        current.map((step) => (step.status === "running" ? { ...step, status: "failed" } : step)),
      );
      setMessages((current) => [
        ...current,
        { id: `assistant-error-${Date.now()}`, role: "assistant", content: message },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function onFollowUp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextDraft: PlanDraft = followUp.trim()
      ? { ...draft, user_request: followUp.trim() }
      : draft;
    setDraft(nextDraft);
    setFollowUp("");
    void runPlan(nextDraft);
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-3xl text-tide sm:text-4xl">Lên kế hoạch</h1>
          <p className="mt-1 text-sm text-ink/65">
            Kết quả trực tiếp từ <code className="text-xs">POST /api/v1/trips/plan</code>
          </p>
        </div>
        {plan?.trip_id ? (
          <Link
            href={`/trips/${plan.trip_id}`}
            className="rounded-full border border-tide/20 px-4 py-2 text-sm text-tide hover:border-lagoon"
          >
            Mở chuyến đi đã lưu
          </Link>
        ) : null}
      </div>

      <div className="grid gap-6 lg:grid-cols-2 lg:items-start">
        <section className="space-y-5 rounded-2xl border border-tide/10 bg-foam/85 p-5">
          <div className="space-y-3">
            <h2 className="text-sm font-semibold uppercase tracking-[0.16em] text-tide/60">
              Hội thoại AI
            </h2>
            <div className="max-h-[28rem] space-y-3 overflow-y-auto rounded-xl border border-tide/10 bg-white/50 p-4">
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={[
                    "rounded-xl px-3 py-2 text-sm leading-6",
                    message.role === "user"
                      ? "ml-6 bg-tide text-foam"
                      : message.role === "assistant"
                        ? "mr-6 bg-mist text-ink"
                        : "bg-transparent text-ink/60",
                  ].join(" ")}
                >
                  {message.content}
                </div>
              ))}
            </div>
          </div>

          <ProgressList steps={progress} title="Tiến trình lập kế hoạch" />

          {error ? (
            <p className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
              {error}
            </p>
          ) : null}

          <form onSubmit={onFollowUp} className="space-y-3">
            <label className="block">
              <span className="mb-1.5 block text-xs font-medium uppercase tracking-[0.12em] text-tide/55">
                Tiếp tục lập kế hoạch
              </span>
              <textarea
                value={followUp}
                onChange={(event) => setFollowUp(event.target.value)}
                rows={3}
                className="w-full rounded-xl border border-tide/15 bg-white/70 px-3 py-2 text-sm outline-none ring-lagoon/25 focus:ring-2"
                placeholder="Chỉnh yêu cầu, hoặc để trống để chạy lại bản nháp hiện tại…"
                disabled={loading}
              />
            </label>
            <div className="flex flex-wrap gap-2">
              <button
                type="submit"
                disabled={loading || (!followUp.trim() && !buildUserRequest(draft))}
                className="rounded-full bg-tide px-5 py-2.5 text-sm font-semibold text-foam disabled:opacity-50"
              >
                {loading ? "Đang lập kế hoạch…" : followUp.trim() ? "Gửi & lập kế hoạch" : "Chạy lại bản nháp"}
              </button>
              <button
                type="button"
                disabled={loading}
                className="rounded-full border border-tide/20 px-4 py-2.5 text-sm text-tide disabled:opacity-50"
                onClick={() => void runPlan(draft)}
              >
                Chạy bản nháp hiện tại
              </button>
            </div>
          </form>
        </section>

        <section>
          {loading && !plan ? <PlanPageSkeleton /> : null}
          {!loading && !plan ? (
            <div className="rounded-2xl border border-dashed border-tide/20 bg-foam/70 p-8">
              <h2 className="font-display text-2xl text-tide">Tóm tắt chuyến đi</h2>
              <p className="mt-2 text-sm leading-6 text-ink/65">
                Bắt đầu từ trang chủ hoặc chạy lập kế hoạch tại đây. Lịch trình, ngân sách, thời tiết và
                bản đồ sẽ hiện sau khi API phản hồi.
              </p>
              <p className="mt-4 text-xs text-tide/55">
                Bản nháp hiện tại: {buildUserRequest(draft) || "trống"}
              </p>
            </div>
          ) : null}
          {plan ? <TripResultPanel plan={plan} /> : null}
        </section>
      </div>
    </div>
  );
}
