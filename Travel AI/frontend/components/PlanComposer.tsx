"use client";

import { FormEvent, KeyboardEvent, useState } from "react";

import type { PlanTripPayload } from "../lib/api";
import {
  EMPTY_DRAFT,
  PlanDraft,
  TravelPace,
  draftToPayload,
} from "../lib/plan-draft";

const EXAMPLE_DRAFT: PlanDraft = {
  ...EMPTY_DRAFT,
  user_request:
    "Tôi muốn đi Đà Nẵng 4 ngày 3 đêm cho 2 người. Ngân sách 8 triệu VND mỗi người. Tôi thích biển, ẩm thực địa phương và chụp ảnh.",
  destination: "Đà Nẵng",
  travelers: 2,
  budget: "16000000",
  interests: "biển, ẩm thực địa phương, chụp ảnh",
  travel_pace: "balanced",
};

const PROMPT_CHIPS: { label: string; prompt: string }[] = [
  {
    label: "Đà Nẵng 4 ngày",
    prompt:
      "Lên kế hoạch Đà Nẵng 4 ngày 3 đêm cho 2 người, ngân sách 16 triệu VND, thích biển và ẩm thực địa phương.",
  },
  {
    label: "Hội An cuối tuần",
    prompt:
      "Gợi ý chuyến Hội An 3 ngày cho gia đình 4 người, ưu tiên phố cổ, làng gốm và món ăn địa phương.",
  },
  {
    label: "Sa Pa săn mây",
    prompt:
      "Tôi muốn đi Sa Pa 3 ngày 2 đêm cho 2 người, thích trekking nhẹ và chụp ảnh ruộng bậc thang.",
  },
  {
    label: "Phú Quốc nghỉ dưỡng",
    prompt:
      "Lên kế hoạch Phú Quốc 5 ngày nghỉ dưỡng cho 2 người, ngân sách 25 triệu VND, thích bãi biển yên tĩnh.",
  },
];

const fieldClass =
  "w-full rounded-xl border border-tide/15 bg-white/85 px-3 py-2.5 text-sm text-ink outline-none ring-lagoon/25 focus:ring-2";
const labelClass = "mb-1.5 block text-xs font-medium uppercase tracking-[0.12em] text-tide/55";

type PlanComposerProps = {
  draft: PlanDraft;
  onDraftChange: (draft: PlanDraft) => void;
  onSubmit: (payload: PlanTripPayload) => void;
  busy: boolean;
  variant?: "hero" | "docked";
};

export function PlanComposer({
  draft,
  onDraftChange,
  onSubmit,
  busy,
  variant = "hero",
}: PlanComposerProps) {
  const [showOptions, setShowOptions] = useState(false);

  // `travelers` and `travel_pace` always have defaults, so `buildUserRequest` is never
  // empty. A real trip needs a free-text prompt or at least a destination.
  const hasIntent = draft.user_request.trim().length > 0 || draft.destination.trim().length > 0;

  function update<K extends keyof PlanDraft>(key: K, value: PlanDraft[K]) {
    onDraftChange({ ...draft, [key]: value });
  }

  function submit() {
    if (busy || !hasIntent) return;
    onSubmit(draftToPayload(draft));
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    submit();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  const filledOptions = (Object.keys(EMPTY_DRAFT) as (keyof PlanDraft)[]).filter(
    (key) =>
      key !== "user_request" && key !== "travelers" && String(draft[key] ?? "").trim() !== "",
  ).length;

  return (
    <form
      onSubmit={handleSubmit}
      className={[
        "rounded-[1.75rem] border border-white/60 bg-foam/85 p-4 shadow-lift backdrop-blur-sm transition duration-300 focus-within:border-lagoon/30 focus-within:shadow-pop sm:p-5",
        variant === "docked" ? "animate-fade-up" : "",
      ].join(" ")}
    >
      <label className="block">
        <span className="sr-only">Mô tả chuyến đi</span>
        <textarea
          value={draft.user_request}
          onChange={(event) => update("user_request", event.target.value)}
          onKeyDown={handleKeyDown}
          rows={variant === "hero" ? 3 : 2}
          className="w-full resize-none bg-transparent text-base leading-7 text-ink outline-none placeholder:text-ink/40"
          placeholder={
            variant === "hero"
              ? "Mô tả chuyến đi của bạn… ví dụ: Đà Nẵng 4 ngày cho 2 người, thích biển và ẩm thực"
              : "Nhập yêu cầu tiếp theo… ví dụ: rút ngắn còn 3 ngày và thêm 1 buổi lặn biển"
          }
          disabled={busy}
        />
      </label>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-tide/10 pt-3">
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setShowOptions((value) => !value)}
            aria-expanded={showOptions}
            className="rounded-full border border-tide/20 px-3 py-1.5 text-xs font-medium text-tide transition hover:border-lagoon hover:text-lagoon"
          >
            {showOptions ? "Ẩn tùy chọn chuyến đi" : "Tùy chọn chuyến đi"}
            {filledOptions > 0 ? (
              <span className="ml-2 rounded-full bg-mist px-2 py-0.5 text-[0.65rem] text-tide">
                {filledOptions}
              </span>
            ) : null}
          </button>
          {variant === "hero" ? (
            <button
              type="button"
              onClick={() => onDraftChange(EXAMPLE_DRAFT)}
              className="rounded-full px-3 py-1.5 text-xs text-tide/70 underline-offset-2 transition hover:text-lagoon hover:underline"
            >
              Dùng ví dụ Đà Nẵng
            </button>
          ) : null}
        </div>
        <button
          type="submit"
          disabled={busy || !hasIntent}
          className={[
            "group inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-semibold text-foam shadow-lift transition duration-200",
            "bg-gradient-to-r from-lagoon to-tide hover:shadow-pop hover:brightness-110 active:scale-[0.98]",
            "disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-none disabled:hover:brightness-100",
          ].join(" ")}
        >
          {busy ? (
            <>
              <span
                aria-hidden
                className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-foam/40 border-t-foam"
              />
              Đang lập kế hoạch…
            </>
          ) : (
            <>
              Lên kế hoạch với AI
              <span aria-hidden className="transition-transform duration-200 group-hover:translate-x-0.5">
                →
              </span>
            </>
          )}
        </button>
      </div>

      {showOptions ? (
        <div className="mt-4 grid animate-fade-up gap-3 sm:grid-cols-2">
          <label className="block">
            <span className={labelClass}>Điểm đi</span>
            <input
              value={draft.origin}
              onChange={(event) => update("origin", event.target.value)}
              className={fieldClass}
              placeholder="vd: Hà Nội"
              disabled={busy}
            />
          </label>
          <label className="block">
            <span className={labelClass}>Điểm đến</span>
            <input
              value={draft.destination}
              onChange={(event) => update("destination", event.target.value)}
              className={fieldClass}
              placeholder="vd: Đà Nẵng"
              disabled={busy}
            />
          </label>
          <label className="block">
            <span className={labelClass}>Ngày bắt đầu</span>
            <input
              type="date"
              value={draft.start_date}
              onChange={(event) => update("start_date", event.target.value)}
              className={fieldClass}
              disabled={busy}
            />
          </label>
          <label className="block">
            <span className={labelClass}>Ngày kết thúc</span>
            <input
              type="date"
              value={draft.end_date}
              onChange={(event) => update("end_date", event.target.value)}
              className={fieldClass}
              disabled={busy}
            />
          </label>
          <label className="block">
            <span className={labelClass}>Số người</span>
            <input
              type="number"
              min={1}
              max={20}
              value={draft.travelers}
              onChange={(event) => update("travelers", Number(event.target.value) || 1)}
              className={fieldClass}
              disabled={busy}
            />
          </label>
          <label className="block">
            <span className={labelClass}>Ngân sách (VND)</span>
            <input
              value={draft.budget}
              onChange={(event) => update("budget", event.target.value)}
              className={fieldClass}
              placeholder="16000000"
              inputMode="numeric"
              disabled={busy}
            />
          </label>
          <label className="block sm:col-span-2">
            <span className={labelClass}>Sở thích</span>
            <input
              value={draft.interests}
              onChange={(event) => update("interests", event.target.value)}
              className={fieldClass}
              placeholder="biển, ẩm thực địa phương, chụp ảnh"
              disabled={busy}
            />
          </label>
          <label className="block sm:col-span-2">
            <span className={labelClass}>Nhịp độ chuyến đi</span>
            <select
              value={draft.travel_pace}
              onChange={(event) => update("travel_pace", event.target.value as TravelPace)}
              className={fieldClass}
              disabled={busy}
            >
              <option value="relaxed">Thư thả</option>
              <option value="balanced">Cân bằng</option>
              <option value="packed">Dày đặc</option>
            </select>
          </label>
        </div>
      ) : null}

      {variant === "hero" ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {PROMPT_CHIPS.map((chip) => (
            <button
              key={chip.label}
              type="button"
              disabled={busy}
              onClick={() => onDraftChange({ ...draft, user_request: chip.prompt })}
              className="rounded-full border border-tide/15 bg-white/60 px-3 py-1.5 text-xs text-tide/80 transition duration-200 hover:-translate-y-px hover:border-coral/40 hover:text-coral disabled:opacity-50 disabled:hover:translate-y-0"
            >
              {chip.label}
            </button>
          ))}
        </div>
      ) : null}
    </form>
  );
}
