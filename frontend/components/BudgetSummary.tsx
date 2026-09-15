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
  const remaining = Number(budget) - Number(estimatedTotalCost);
  return (
    <section className="rounded-2xl border border-tide/10 bg-foam/90 p-5">
      <h2 className="font-display text-xl text-tide">Tóm tắt ngân sách</h2>
      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-tide/55">Tổng ngân sách</dt>
          <dd className="mt-1 font-semibold text-ink">{formatMoney(budget, currency)}</dd>
        </div>
        <div>
          <dt className="text-tide/55">Chi phí ước tính</dt>
          <dd className="mt-1 font-semibold text-ink">
            {formatMoney(estimatedTotalCost, currency)}
          </dd>
        </div>
        <div>
          <dt className="text-tide/55">Còn lại</dt>
          <dd className={`mt-1 font-semibold ${remaining < 0 ? "text-red-700" : "text-lagoon"}`}>
            {formatMoney(remaining, currency)}
          </dd>
        </div>
      </dl>
    </section>
  );
}
