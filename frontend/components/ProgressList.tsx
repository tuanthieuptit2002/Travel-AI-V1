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
};

export function ProgressList({ steps, title = "Tiến trình lập kế hoạch" }: ProgressListProps) {
  return (
    <section>
      <h2 className="text-sm font-semibold uppercase tracking-[0.16em] text-tide/60">{title}</h2>
      <ol className="mt-3 space-y-2">
        {steps.map((step) => (
          <li key={step.id} className="flex items-start gap-3 text-sm text-ink/80">
            <span
              className={[
                "mt-1 inline-flex h-2.5 w-2.5 shrink-0 rounded-full",
                step.status === "completed" ? "bg-lagoon" : "",
                step.status === "running" ? "bg-sand" : "",
                step.status === "failed" ? "bg-red-600" : "",
                step.status === "pending" ? "bg-tide/20" : "",
              ].join(" ")}
              aria-hidden
            />
            <span>
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
