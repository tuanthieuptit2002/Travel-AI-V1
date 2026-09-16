import type { ProgressStep } from "../lib/api";

type ProgressListProps = {
  steps: ProgressStep[];
  title?: string;
};

const STATUS_LABEL: Record<string, string> = {
  pending: "chờ",
  running: "đang chạy",
  completed: "xong",
  failed: "lỗi",
  skipped: "bỏ qua",
};

export function ProgressList({ steps, title = "Tiến trình lập kế hoạch" }: ProgressListProps) {
  return (
    <section>
      <h2 className="text-sm font-semibold uppercase tracking-[0.16em] text-tide/60">{title}</h2>
      <ol className="mt-3 space-y-2.5">
        {steps.map((step) => (
          <li key={step.id} className="flex items-start gap-3 text-sm text-ink/80">
            <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center" aria-hidden>
              {step.status === "completed" ? (
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-lagoon text-[0.6rem] font-bold text-foam">
                  ✓
                </span>
              ) : step.status === "running" ? (
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-coral/30 border-t-coral" />
              ) : step.status === "failed" ? (
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-red-600 text-[0.6rem] font-bold text-white">
                  ✕
                </span>
              ) : (
                <span className="h-2.5 w-2.5 rounded-full bg-tide/20" />
              )}
            </span>
            <span className={step.status === "pending" ? "text-ink/45" : undefined}>
              <span className="font-medium text-ink">{step.label}</span>
              <span className="ml-2 text-xs uppercase tracking-wide text-tide/50">
                {STATUS_LABEL[step.status] || step.status}
              </span>
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}
