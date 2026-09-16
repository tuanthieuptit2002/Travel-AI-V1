"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

import {
  clearMemoryField,
  clearUserMemory,
  getUserMemory,
  type MemoryField,
  type UserMemory,
  updateUserMemory,
} from "../lib/api";
import { getGuestUserId } from "../lib/guest-user";

const LIST_FIELDS: MemoryField[] = [
  "preferred_destinations",
  "preferred_activities",
  "food_preferences",
  "disliked_activities",
];

const SCALAR_FIELDS: MemoryField[] = [
  "preferred_trip_pace",
  "budget_preference",
  "accommodation_preference",
  "transportation_preference",
];

const LABELS: Record<MemoryField, string> = {
  preferred_destinations: "Điểm đến ưa thích",
  preferred_activities: "Hoạt động ưa thích",
  food_preferences: "Sở thích ẩm thực",
  disliked_activities: "Hoạt động không thích",
  preferred_trip_pace: "Nhịp độ chuyến đi",
  budget_preference: "Ngân sách",
  accommodation_preference: "Chỗ ở",
  transportation_preference: "Phương tiện",
};

const emptyMemory = (userId: string): UserMemory => ({
  user_id: userId,
  preferred_destinations: [],
  preferred_activities: [],
  food_preferences: [],
  disliked_activities: [],
  preferred_trip_pace: null,
  budget_preference: null,
  accommodation_preference: null,
  transportation_preference: null,
  updated_at: new Date().toISOString(),
});

export function PreferencesPanel() {
  const [userId, setUserId] = useState("");
  const [memory, setMemory] = useState<UserMemory | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [draftField, setDraftField] = useState<MemoryField>("preferred_activities");
  const [draftValue, setDraftValue] = useState("");

  const load = useCallback(async (id: string) => {
    setBusy(true);
    setError(null);
    try {
      const data = await getUserMemory(id);
      setMemory(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể tải sở thích.");
      setMemory(emptyMemory(id));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    async function bootstrap() {
      const id = getGuestUserId();
      if (!active) return;
      setUserId(id);
      await load(id);
    }
    void bootstrap();
    return () => {
      active = false;
    };
  }, [load]);

  async function handleAdd(event: FormEvent) {
    event.preventDefault();
    if (!userId || !draftValue.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const isList = LIST_FIELDS.includes(draftField);
      const value = isList
        ? draftValue.split(",").map((part) => part.trim()).filter(Boolean)
        : draftValue.trim();
      const data = await updateUserMemory(userId, {
        field: draftField,
        value,
        source_excerpt: draftValue.trim().slice(0, 200),
      });
      setMemory(data);
      setDraftValue("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể lưu sở thích.");
    } finally {
      setBusy(false);
    }
  }

  async function handleClearField(field: MemoryField) {
    if (!userId) return;
    setBusy(true);
    setError(null);
    try {
      setMemory(await clearMemoryField(userId, field));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể xóa sở thích.");
    } finally {
      setBusy(false);
    }
  }

  async function handleClearAll() {
    if (!userId) return;
    setBusy(true);
    setError(null);
    try {
      await clearUserMemory(userId);
      setMemory(emptyMemory(userId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể xóa toàn bộ sở thích.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-8">
      <section className="max-w-2xl">
        <h1 className="font-display text-4xl tracking-tight text-tide">Sở thích du lịch</h1>
        <p className="mt-3 text-base leading-7 text-ink/70">
          TripMind chỉ lưu sở thích dài hạn có cấu trúc—không lưu hội thoại. Các gợi ý này được tải
          trước khi lập kế hoạch và tách biệt với kho kiến thức du lịch Việt Nam (RAG).
        </p>
      </section>

      {error ? (
        <p className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </p>
      ) : null}

      <form onSubmit={handleAdd} className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <label className="flex flex-1 flex-col gap-1 text-sm text-ink/70">
          Trường
          <select
            className="rounded-md border border-tide/15 bg-foam px-3 py-2 text-ink"
            value={draftField}
            onChange={(event) => setDraftField(event.target.value as MemoryField)}
          >
            {[...LIST_FIELDS, ...SCALAR_FIELDS].map((field) => (
              <option key={field} value={field}>
                {LABELS[field]}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-[2] flex-col gap-1 text-sm text-ink/70">
          Giá trị
          <input
            className="rounded-md border border-tide/15 bg-foam px-3 py-2 text-ink"
            value={draftValue}
            onChange={(event) => setDraftValue(event.target.value)}
            placeholder={
              LIST_FIELDS.includes(draftField)
                ? "biển, chụp ảnh"
                : draftField === "preferred_trip_pace"
                  ? "relaxed | balanced | packed"
                  : "vd: hotel, medium, train"
            }
          />
        </label>
        <button
          type="submit"
          disabled={busy}
          className="rounded-full bg-tide px-5 py-2.5 text-sm font-medium text-foam disabled:opacity-60"
        >
          Lưu
        </button>
      </form>

      <div className="space-y-4">
        {[...LIST_FIELDS, ...SCALAR_FIELDS].map((field) => {
          const value = memory?.[field];
          const isEmpty =
            value == null || value === "" || (Array.isArray(value) && value.length === 0);
          return (
            <div key={field} className="border-b border-tide/10 pb-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-lagoon">
                    {LABELS[field]}
                  </h2>
                  {isEmpty ? (
                    <p className="mt-2 text-sm text-ink/45">Chưa có sở thích</p>
                  ) : Array.isArray(value) ? (
                    <ul className="mt-2 flex flex-wrap gap-2">
                      {value.map((item) => (
                        <li key={item} className="bg-mist px-2.5 py-1 text-sm text-tide">
                          {item}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-2 text-base text-ink">{String(value)}</p>
                  )}
                </div>
                {!isEmpty ? (
                  <button
                    type="button"
                    onClick={() => void handleClearField(field)}
                    className="text-sm text-ink/55 underline-offset-2 hover:text-red-700 hover:underline"
                    disabled={busy}
                  >
                    Xóa
                  </button>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>

      <button
        type="button"
        onClick={() => void handleClearAll()}
        disabled={busy}
        className="text-sm text-red-700 underline-offset-2 hover:underline disabled:opacity-60"
      >
        Xóa toàn bộ sở thích
      </button>
    </div>
  );
}
