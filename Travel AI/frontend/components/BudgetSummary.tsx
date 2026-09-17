import { formatMoney } from "../lib/api";

type BudgetSummaryProps = {
  budget: string | number;
  estimatedTotalCost: string | number;
  currency?: string;
};

export function BudgetSummary({
  budget,
  estimatedTotalCost,
  currency = "VND",
}: BudgetSummaryProps) {
  const budgetNumber = Number(budget);
  const costNumber = Number(estimatedTotalCost);
  const remaining = budgetNumber - costNumber;
  const spentPercent =
    budgetNumber > 0 ? Math.min(100, Math.round((costNumber / budgetNumber) * 100)) : 0;
  const overBudget = remaining < 0;

  return (
    <section className="rounded-2xl border border-tide/10 bg-foam/90 p-5 shadow-soft">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-display text-xl text-tide">Tóm tắt ngân sách</h2>
        <span
          className={[
            "rounded-full px-3 py-1 text-xs font-semibold",
            overBudget ? "bg-red-100 text-red-700" : "bg-mist text-lagoon",
          ].join(" ")}
        >
          {overBudget ? "Vượt ngân sách" : `Dùng ${spentPercent}%`}
        </span>
      </div>

      <div
        role="progressbar"
        aria-valuenow={spentPercent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Tỷ lệ ngân sách đã dùng"
        className="mt-4 h-2.5 overflow-hidden rounded-full bg-tide/10"
      >
        <div
          className={[
            "h-full rounded-full transition-all duration-700",
            overBudget
              ? "bg-gradient-to-r from-red-400 to-red-600"
              : "bg-gradient-to-r from-lagoon to-coral",
          ].join(" ")}
          style={{ width: `${spentPercent}%` }}
        />
      </div>

      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-tide/55">Tổng ngân sách</dt>
          <dd className="mt-1 font-semibold tabular-nums text-ink">{formatMoney(budget, currency)}</dd>
        </div>
        <div>
          <dt className="text-tide/55">Chi phí ước tính</dt>
          <dd className="mt-1 font-semibold tabular-nums text-ink">
            {formatMoney(estimatedTotalCost, currency)}
          </dd>
        </div>
        <div>
          <dt className="text-tide/55">Còn lại</dt>
          <dd
            className={`mt-1 font-semibold tabular-nums ${overBudget ? "text-red-700" : "text-lagoon"}`}
          >
            {formatMoney(remaining, currency)}
          </dd>
        </div>
      </dl>
    </section>
  );
}
