import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import * as adminApi from "../../api/admin";
import type { AggregationReport, ProcurementCycle } from "../../types";
import { formatDate } from "../../utils";
import { ErrorBanner } from "../../components/ErrorBanner";
import { ApiError } from "../../api/client";

export function CycleDetail() {
  const { cycleId } = useParams();
  const [cycle, setCycle] = useState<ProcurementCycle | null>(null);
  const [report, setReport] = useState<AggregationReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    if (!cycleId) return;
    adminApi.listCycles().then((cycles) => setCycle(cycles.find((c) => c.id === cycleId) ?? null));
    adminApi.getAggregation(cycleId).then(setReport);
  };

  useEffect(load, [cycleId]);

  const handleOpen = async () => {
    if (!cycleId) return;
    setError(null);
    try {
      await adminApi.openCycle(cycleId);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not open cycle");
    }
  };

  const handleClose = async () => {
    if (!cycleId) return;
    if (!confirm("Close this cycle? This will lock new orders and advance every order in it to AGGREGATING/PROCUREMENT.")) return;
    setError(null);
    try {
      await adminApi.closeCycle(cycleId);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not close cycle");
    }
  };

  if (!cycle || !report) {
    return <p className="p-8 text-center text-stone-500">Loading…</p>;
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-stone-900">{cycle.name}</h1>
          <p className="text-sm text-stone-500">
            {formatDate(cycle.order_window_opens_at)} → {formatDate(cycle.order_window_closes_at)}
          </p>
        </div>
        <div className="flex gap-2">
          {cycle.status === "draft" && (
            <button onClick={handleOpen} className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white">
              Open cycle
            </button>
          )}
          {cycle.status === "open" && (
            <button onClick={handleClose} className="rounded-md bg-purple-600 px-3 py-1.5 text-sm font-medium text-white">
              Close cycle
            </button>
          )}
        </div>
      </div>

      <ErrorBanner message={error} />

      <section className="rounded-lg border border-stone-200 bg-white p-4">
        <h2 className="mb-3 font-semibold text-stone-900">Aggregated demand</h2>
        <p className="mb-3 text-sm text-stone-500">Total quantity ordered per product across every customer in this cycle.</p>
        {report.lines.length === 0 ? (
          <p className="text-sm text-stone-500">No orders in this cycle yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-stone-200 text-left text-stone-500">
                <th className="py-2">Product</th>
                <th className="py-2 text-right">Total quantity</th>
              </tr>
            </thead>
            <tbody>
              {report.lines.map((line) => (
                <tr key={line.product_id} className="border-b border-stone-100 last:border-0">
                  <td className="py-2">{line.product_name}</td>
                  <td className="py-2 text-right font-medium">
                    {line.total_quantity} {line.unit}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
