import { useEffect, useState } from "react";
import * as adminApi from "../../api/admin";
import type { AnalyticsSummary } from "../../types";
import { formatNaira } from "../../utils";

export function Dashboard() {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);

  useEffect(() => {
    adminApi.getAnalyticsSummary().then(setSummary);
  }, []);

  if (!summary) {
    return <p className="p-8 text-center text-stone-500">Loading…</p>;
  }

  const tiles = [
    { label: "Customers", value: summary.customers },
    { label: "Products", value: summary.products },
    { label: "Total orders", value: summary.orders },
    { label: "Awaiting payment", value: summary.orders_awaiting_payment },
    { label: "Active procurement cycles", value: summary.active_procurement_cycles },
    { label: "GMV", value: formatNaira(summary.gmv) },
  ];

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <h1 className="mb-6 text-2xl font-bold text-stone-900">Admin dashboard</h1>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        {tiles.map((t) => (
          <div key={t.label} className="rounded-lg border border-stone-200 bg-white p-4">
            <p className="text-sm text-stone-500">{t.label}</p>
            <p className="text-2xl font-bold text-stone-900">{t.value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
