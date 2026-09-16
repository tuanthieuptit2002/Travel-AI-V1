import { redirect } from "next/navigation";

/**
 * Legacy route. The planner now lives inside the single landing page conversation,
 * so deep links forward to `/?draft=1` which auto-runs the stored draft.
 */
export default function PlanPage() {
  redirect("/?draft=1");
}
