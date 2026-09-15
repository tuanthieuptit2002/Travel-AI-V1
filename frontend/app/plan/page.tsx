import { Suspense } from "react";

import { PlanWorkspace } from "../../components/PlanWorkspace";
import { SiteHeader } from "../../components/SiteHeader";
import { PlanPageSkeleton } from "../../components/Skeleton";

export default function PlanPage() {
  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,#f7fcfa_0%,#e7f3ef_100%)] text-ink">
      <SiteHeader active="plan" />
      <Suspense
        fallback={
          <div className="mx-auto max-w-6xl px-6 py-8">
            <PlanPageSkeleton />
          </div>
        }
      >
        <PlanWorkspace />
      </Suspense>
    </div>
  );
}
