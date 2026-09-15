"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import {
  EMPTY_DRAFT,
  PlanDraft,
  TravelPace,
  savePlanDraft,
} from "../lib/plan-draft";

const EXAMPLE =
  "Tôi muốn đi Đà Nẵng 4 ngày 3 đêm cho 2 người. Ngân sách 8 triệu VND mỗi người. Tôi thích biển, ẩm thực địa phương và chụp ảnh.";

const fieldClass =
  "w-full rounded-xl border border-tide/15 bg-foam/90 px-3 py-2.5 text-sm text-ink outline-none ring-lagoon/25 focus:ring-2";

export function HomePlanForm() {
  const router = useRouter();
  const [draft, setDraft] = useState<PlanDraft>({
    ...EMPTY_DRAFT,
    user_request: EXAMPLE,
    destination: "Đà Nẵng",
    travelers: 2,
    budget: "16000000",
    interests: "biển, ẩm thực địa phương, chụp ảnh",
    travel_pace: "balanced",
  });

  function update<K extends keyof PlanDraft>(key: K, value: PlanDraft[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft.user_request.trim() && !draft.destination.trim()) return;
    savePlanDraft(draft);
    router.push("/plan?autostart=1");
  }

  return (
    <form onSubmit={onSubmit} className="space-y-5 rounded-[1.75rem] border border-white/50 bg-foam/75 p-5 shadow-[0_20px_60px_rgba(16,36,31,0.06)] backdrop-blur-sm sm:p-6">
      <label className="block">
        <span className="mb-2 block text-sm font-medium text-tide">Bạn muốn đi đâu?</span>
        <textarea
          value={draft.user_request}
          onChange={(event) => update("user_request", event.target.value)}
          rows={4}
          className={`${fieldClass} resize-y leading-6`}
          placeholder="Mô tả chuyến đi bằng ngôn ngữ tự nhiên…"
          required={!draft.destination}
        />
      </label>

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block">
          <span className="mb-1.5 block text-xs font-medium uppercase tracking-[0.12em] text-tide/55">
            Điểm đi
          </span>
          <input
            value={draft.origin}
            onChange={(event) => update("origin", event.target.value)}
            className={fieldClass}
            placeholder="vd: Hà Nội"
          />
        </label>
        <label className="block">
          <span className="mb-1.5 block text-xs font-medium uppercase tracking-[0.12em] text-tide/55">
            Điểm đến
          </span>
          <input
            value={draft.destination}
            onChange={(event) => update("destination", event.target.value)}
            className={fieldClass}
            placeholder="vd: Đà Nẵng"
          />
        </label>
        <label className="block">
          <span className="mb-1.5 block text-xs font-medium uppercase tracking-[0.12em] text-tide/55">
            Ngày bắt đầu
          </span>
          <input
            type="date"
            value={draft.start_date}
            onChange={(event) => update("start_date", event.target.value)}
            className={fieldClass}
          />
        </label>
        <label className="block">
          <span className="mb-1.5 block text-xs font-medium uppercase tracking-[0.12em] text-tide/55">
            Ngày kết thúc
          </span>
          <input
            type="date"
            value={draft.end_date}
            onChange={(event) => update("end_date", event.target.value)}
            className={fieldClass}
          />
        </label>
        <label className="block">
          <span className="mb-1.5 block text-xs font-medium uppercase tracking-[0.12em] text-tide/55">
            Số người
          </span>
          <input
            type="number"
            min={1}
            max={20}
            value={draft.travelers}
            onChange={(event) => update("travelers", Number(event.target.value) || 1)}
            className={fieldClass}
          />
        </label>
        <label className="block">
          <span className="mb-1.5 block text-xs font-medium uppercase tracking-[0.12em] text-tide/55">
            Ngân sách (VND)
          </span>
          <input
            value={draft.budget}
            onChange={(event) => update("budget", event.target.value)}
            className={fieldClass}
            placeholder="16000000"
            inputMode="numeric"
          />
        </label>
        <label className="block sm:col-span-2">
          <span className="mb-1.5 block text-xs font-medium uppercase tracking-[0.12em] text-tide/55">
            Sở thích
          </span>
          <input
            value={draft.interests}
            onChange={(event) => update("interests", event.target.value)}
            className={fieldClass}
            placeholder="biển, ẩm thực địa phương, chụp ảnh"
          />
        </label>
        <label className="block sm:col-span-2">
          <span className="mb-1.5 block text-xs font-medium uppercase tracking-[0.12em] text-tide/55">
            Nhịp độ chuyến đi
          </span>
          <select
            value={draft.travel_pace}
            onChange={(event) => update("travel_pace", event.target.value as TravelPace)}
            className={fieldClass}
          >
            <option value="relaxed">Thư thả</option>
            <option value="balanced">Cân bằng</option>
            <option value="packed">Dày đặc</option>
          </select>
        </label>
      </div>

      <div className="flex flex-wrap gap-3 pt-1">
        <button
          type="submit"
          className="rounded-full bg-tide px-6 py-3 text-sm font-semibold text-foam transition hover:bg-lagoon"
        >
          Lên kế hoạch với AI
        </button>
        <button
          type="button"
          className="rounded-full border border-tide/20 px-5 py-3 text-sm text-tide hover:border-lagoon"
          onClick={() =>
            setDraft({
              ...EMPTY_DRAFT,
              user_request: EXAMPLE,
              destination: "Đà Nẵng",
              travelers: 2,
              budget: "16000000",
              interests: "biển, ẩm thực địa phương, chụp ảnh",
              travel_pace: "balanced",
            })
          }
        >
          Dùng ví dụ Đà Nẵng
        </button>
      </div>
    </form>
  );
}
