type SkeletonProps = {
  className?: string;
};

export function Skeleton({ className = "" }: SkeletonProps) {
  return <div className={`animate-pulse rounded-lg bg-tide/10 ${className}`} />;
}

export function PlanPageSkeleton() {
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="space-y-3 rounded-2xl border border-tide/10 bg-foam/80 p-5">
        <Skeleton className="h-5 w-40" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-5/6" />
        <Skeleton className="h-4 w-4/6" />
        <Skeleton className="mt-4 h-28 w-full" />
      </div>
      <div className="space-y-3 rounded-2xl border border-tide/10 bg-foam/80 p-5">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    </div>
  );
}

export function TripListSkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2, 3].map((item) => (
        <div key={item} className="rounded-2xl border border-tide/10 bg-foam/80 p-5">
          <Skeleton className="h-5 w-40" />
          <Skeleton className="mt-3 h-4 w-64" />
          <Skeleton className="mt-2 h-4 w-52" />
        </div>
      ))}
    </div>
  );
}

export function ChatLandingSkeleton() {
  return (
    <div className="flex min-h-screen flex-col bg-[linear-gradient(165deg,#f7fcfa_0%,#e3f1ec_45%,#cfe6de_100%)] text-ink">
      <div className="border-b border-tide/10 bg-foam/70 px-6 py-4">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <Skeleton className="h-6 w-32" />
          <Skeleton className="h-8 w-52" />
        </div>
      </div>
      <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-center px-6 py-16">
        <Skeleton className="h-6 w-44 rounded-full" />
        <Skeleton className="mt-6 h-12 w-80" />
        <Skeleton className="mt-4 h-4 w-64" />
        <Skeleton className="mt-10 h-44 w-full rounded-[1.75rem]" />
      </div>
    </div>
  );
}
