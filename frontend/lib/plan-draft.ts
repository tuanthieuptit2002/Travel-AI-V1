import type { PlanTripPayload } from "./api";
import { getGuestUserId } from "./guest-user";

export type TravelPace = "relaxed" | "balanced" | "packed";

export type PlanDraft = {
  user_request: string;
  origin: string;
  destination: string;
  start_date: string;
  end_date: string;
  travelers: number;
  budget: string;
  interests: string;
  travel_pace: TravelPace;
};

export const PLAN_DRAFT_KEY = "tripmind.planDraft";

export const EMPTY_DRAFT: PlanDraft = {
  user_request: "",
  origin: "",
  destination: "",
  start_date: "",
  end_date: "",
  travelers: 2,
  budget: "",
  interests: "",
  travel_pace: "balanced",
};

const PACE_LABEL: Record<TravelPace, string> = {
  relaxed: "thư thả",
  balanced: "cân bằng",
  packed: "dày đặc",
};

export function savePlanDraft(draft: PlanDraft): void {
  if (typeof window === "undefined") return;
  sessionStorage.setItem(PLAN_DRAFT_KEY, JSON.stringify(draft));
}

export function loadPlanDraft(): PlanDraft | null {
  if (typeof window === "undefined") return null;
  const raw = sessionStorage.getItem(PLAN_DRAFT_KEY);
  if (!raw) return null;
  try {
    return { ...EMPTY_DRAFT, ...(JSON.parse(raw) as PlanDraft) };
  } catch {
    return null;
  }
}

export function clearPlanDraft(): void {
  if (typeof window === "undefined") return;
  sessionStorage.removeItem(PLAN_DRAFT_KEY);
}

export function buildUserRequest(draft: PlanDraft): string {
  const primary = draft.user_request.trim();
  if (primary) return primary;

  const parts: string[] = [];
  if (draft.destination) {
    parts.push(
      draft.origin
        ? `Tôi muốn đi từ ${draft.origin} đến ${draft.destination}.`
        : `Tôi muốn đi ${draft.destination}.`,
    );
  }
  if (draft.start_date && draft.end_date) {
    parts.push(`Thời gian: ${draft.start_date} đến ${draft.end_date}.`);
  }
  if (draft.travelers) {
    parts.push(`Cho ${draft.travelers} người.`);
  }
  if (draft.budget) {
    parts.push(`Ngân sách ${draft.budget} VND tổng.`);
  }
  if (draft.interests.trim()) {
    parts.push(`Tôi thích ${draft.interests.trim()}.`);
  }
  if (draft.travel_pace) {
    parts.push(`Ưu tiên nhịp độ ${PACE_LABEL[draft.travel_pace]}.`);
  }
  return parts.join(" ");
}

export function draftToPayload(draft: PlanDraft): PlanTripPayload {
  const budgetNumber = draft.budget ? Number(draft.budget.replace(/,/g, "")) : undefined;
  return {
    user_request: buildUserRequest(draft),
    user_id: typeof window !== "undefined" ? getGuestUserId() : undefined,
    origin: draft.origin || undefined,
    destination: draft.destination || undefined,
    start_date: draft.start_date || undefined,
    end_date: draft.end_date || undefined,
    travelers: draft.travelers || undefined,
    budget: Number.isFinite(budgetNumber) ? budgetNumber : undefined,
    currency: "VND",
  };
}
