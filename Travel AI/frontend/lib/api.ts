import { authHeaders, getStoredTokenUserId, refreshGuestAccessToken } from "./auth";
import { getGuestUserId } from "./guest-user";

export type ProgressStep = {
  id: string;
  label: string;
  status: "pending" | "running" | "completed" | "failed" | string;
};

export type ItineraryActivity = {
  place_id: string;
  name: string;
  kind: string;
  start_time: string;
  end_time: string;
  estimated_cost: string;
  reason: string;
  travel_time_from_previous: number;
  rating?: number | null;
  opening_hours?: string | null;
};

export type ItineraryDay = {
  day_number: number;
  date: string;
  theme: string;
  activities: ItineraryActivity[];
};

export type WeatherForecast = {
  destination: string;
  forecast_date: string;
  condition: string;
  temperature_min_c: number;
  temperature_max_c: number;
  precipitation_probability: number;
  humidity_percent: number;
  wind_speed_kph: number;
};

export type TripPlanResponse = {
  trip_id?: string | null;
  summary: string;
  destination: string;
  origin?: string | null;
  start_date: string;
  end_date: string;
  travelers: number;
  budget: string;
  currency: string;
  estimated_total_cost: string;
  itinerary: ItineraryDay[];
  warnings: string[];
  recommendations: string[];
  weather?: WeatherForecast[];
  weather_notes?: string[];
  citations?: string[];
  optimization_notes?: string[];
  progress: ProgressStep[];
  is_valid: boolean;
};

export type TripSummary = {
  id: string;
  user_id?: string | null;
  destination: string;
  origin?: string | null;
  start_date: string;
  end_date: string;
  travelers: number;
  budget?: string | null;
  currency: string;
  status: string;
  summary?: string | null;
  estimated_total_cost?: string | null;
  created_at: string;
};

export type TripDetail = TripSummary & {
  itinerary: ItineraryDay[];
  warnings: string[];
  recommendations: string[];
  weather?: WeatherForecast[];
  weather_notes?: string[];
};

export type TripListResponse = {
  items: TripSummary[];
  total: number;
};

export type PlanTripPayload = {
  user_request: string;
  user_id?: string;
  origin?: string;
  destination?: string;
  start_date?: string;
  end_date?: string;
  travelers?: number;
  budget?: number;
  currency?: string;
};

export type UserMemory = {
  user_id: string;
  preferred_destinations: string[];
  preferred_activities: string[];
  food_preferences: string[];
  disliked_activities: string[];
  preferred_trip_pace?: string | null;
  budget_preference?: string | null;
  accommodation_preference?: string | null;
  transportation_preference?: string | null;
  updated_at: string;
};

export type MemoryField =
  | "preferred_destinations"
  | "preferred_activities"
  | "food_preferences"
  | "disliked_activities"
  | "preferred_trip_pace"
  | "budget_preference"
  | "accommodation_preference"
  | "transportation_preference";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string };
    if (typeof body.detail === "string") return body.detail;
  } catch {
    // ignore
  }
  return fallback;
}

/**
 * Authenticated fetch. A cached guest JWT can outlive its `exp`, so a `401`
 * almost always means the token expired: mint a fresh one once, then retry.
 */
async function authedFetch(url: string, init: RequestInit & { userId?: string } = {}): Promise<Response> {
  const { userId, ...requestInit } = init;
  const headers = {
    ...(await authHeaders(userId)),
    ...(requestInit.headers as Record<string, string> | undefined),
  };
  const response = await fetch(url, { ...requestInit, headers });
  if (response.status !== 401) return response;

  const refreshUserId = userId ?? getStoredTokenUserId() ?? getGuestUserId();
  const refreshed = await refreshGuestAccessToken(refreshUserId);
  if (!refreshed) return response;
  return fetch(url, { ...requestInit, headers: { ...headers, Authorization: `Bearer ${refreshed}` } });
}

export async function planTrip(payload: PlanTripPayload): Promise<TripPlanResponse> {
  const response = await authedFetch(`${API_BASE}/trips/plan`, {
    method: "POST",
    userId: payload.user_id,
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await readError(response, "Không thể lên kế hoạch chuyến đi lúc này."));
  }
  return (await response.json()) as TripPlanResponse;
}

export async function listTrips(userId?: string): Promise<TripListResponse> {
  const url = new URL(`${API_BASE}/trips`);
  if (userId) url.searchParams.set("user_id", userId);
  const response = await authedFetch(url.toString(), {
    cache: "no-store",
    userId,
  });
  if (!response.ok) {
    throw new Error(await readError(response, "Không thể tải danh sách chuyến đi."));
  }
  return (await response.json()) as TripListResponse;
}

export async function getTrip(tripId: string, userId?: string): Promise<TripDetail> {
  const response = await authedFetch(`${API_BASE}/trips/${tripId}`, {
    cache: "no-store",
    userId,
  });
  if (!response.ok) {
    throw new Error(await readError(response, "Không tìm thấy chuyến đi."));
  }
  return (await response.json()) as TripDetail;
}

export async function getUserMemory(userId: string): Promise<UserMemory> {
  const response = await authedFetch(`${API_BASE}/memory/${userId}`, {
    cache: "no-store",
    userId,
  });
  if (!response.ok) {
    throw new Error(await readError(response, "Không thể tải sở thích du lịch."));
  }
  return (await response.json()) as UserMemory;
}

export async function updateUserMemory(
  userId: string,
  payload: {
    field: MemoryField;
    value: string | string[];
    evidence?: "explicit_user_statement" | "confirmed_preference";
    source_excerpt?: string;
  },
): Promise<UserMemory> {
  const response = await authedFetch(`${API_BASE}/memory/${userId}`, {
    method: "POST",
    userId,
    body: JSON.stringify({
      evidence: "explicit_user_statement",
      ...payload,
    }),
  });
  if (!response.ok) {
    throw new Error(await readError(response, "Không thể lưu sở thích."));
  }
  return (await response.json()) as UserMemory;
}

export async function clearUserMemory(userId: string): Promise<void> {
  const response = await authedFetch(`${API_BASE}/memory/${userId}`, {
    method: "DELETE",
    userId,
  });
  if (!response.ok) {
    throw new Error(await readError(response, "Không thể xóa sở thích."));
  }
}

export async function clearMemoryField(userId: string, field: MemoryField): Promise<UserMemory> {
  const response = await authedFetch(`${API_BASE}/memory/${userId}/${field}`, {
    method: "DELETE",
    userId,
  });
  if (!response.ok) {
    throw new Error(await readError(response, "Không thể xóa mục sở thích."));
  }
  return (await response.json()) as UserMemory;
}

export function formatMoney(amount: string | number, currency = "VND"): string {
  const value = typeof amount === "string" ? Number(amount) : amount;
  if (Number.isNaN(value)) return `${amount} ${currency}`;
  return new Intl.NumberFormat("vi-VN", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatTime(value: string): string {
  return value.slice(0, 5);
}

export const PLANNING_STEPS: ProgressStep[] = [
  { id: "bootstrap", label: "Đang hiểu yêu cầu và tải ngữ cảnh", status: "pending" },
  { id: "supervisor", label: "Giám sát viên đang chọn agent cần chạy", status: "pending" },
  { id: "flight", label: "Flight Agent: tìm và xếp hạng vé máy bay", status: "pending" },
  { id: "hotel", label: "Hotel Agent: tìm và xếp hạng khách sạn", status: "pending" },
  { id: "place", label: "Place Agent: điểm tham quan và nhà hàng", status: "pending" },
  { id: "weather", label: "Weather Agent: phân tích thời tiết", status: "pending" },
  { id: "itinerary", label: "Itinerary Agent: dựng lịch trình", status: "pending" },
  { id: "budget", label: "Budget Agent: phân tích chi phí và tối ưu", status: "pending" },
  { id: "validation", label: "Validation Agent: kiểm tra lịch trình", status: "pending" },
  { id: "finalize", label: "Đang chuẩn bị gợi ý", status: "pending" },
  { id: "update_memory", label: "Đang lưu sở thích rõ ràng", status: "pending" },
];

/** Local-only progress animation used while the agent request is in flight. */
export function advanceLocalProgress(steps: ProgressStep[], tick: number): ProgressStep[] {
  return steps.map((step, index) => {
    if (index < tick) return { ...step, status: "completed" };
    if (index === tick) return { ...step, status: "running" };
    return { ...step, status: "pending" };
  });
}
