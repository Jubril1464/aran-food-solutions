import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import * as adminApi from "../../api/admin";
import * as shopApi from "../../api/shop";
import type { Category, ProcurementCycle } from "../../types";
import { formatDate } from "../../utils";
import { ErrorBanner } from "../../components/ErrorBanner";
import { ApiError } from "../../api/client";

const statusColor: Record<string, string> = {
  draft: "bg-stone-100 text-stone-700",
  open: "bg-brand-100 text-brand-700",
  closed: "bg-purple-100 text-purple-800",
  completed: "bg-blue-100 text-blue-800",
};

export function ProcurementCycles() {
  const [cycles, setCycles] = useState<ProcurementCycle[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [form, setForm] = useState({ name: "", category_id: "", order_window_opens_at: "", order_window_closes_at: "" });
  const [error, setError] = useState<string | null>(null);

  const load = () => adminApi.listCycles().then(setCycles);

  useEffect(() => {
    load();
    shopApi.listCategories().then(setCategories);
  }, []);

  const handleCreate = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await adminApi.createCycle({
        name: form.name,
        category_id: form.category_id || null,
        order_window_opens_at: new Date(form.order_window_opens_at).toISOString(),
        order_window_closes_at: new Date(form.order_window_closes_at).toISOString(),
      });
      setForm({ name: "", category_id: "", order_window_opens_at: "", order_window_closes_at: "" });
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create cycle");
    }
  };

  const handleOpen = async (cycleId: string) => {
    setError(null);
    try {
      await adminApi.openCycle(cycleId);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not open cycle");
    }
  };

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <h1 className="mb-6 text-2xl font-bold text-stone-900">Procurement cycles</h1>
      <ErrorBanner message={error} />

      <form onSubmit={handleCreate} className="mb-6 rounded-lg border border-stone-200 bg-white p-4">
        <h2 className="mb-3 font-semibold text-stone-900">New cycle</h2>
        <div className="grid grid-cols-2 gap-3">
          <input
            required
            placeholder="Name (e.g. Week 34 cycle)"
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            className="col-span-2 rounded-md border border-stone-300 px-3 py-2 text-sm"
          />
          <select
            value={form.category_id}
            onChange={(e) => setForm((f) => ({ ...f, category_id: e.target.value }))}
            className="col-span-2 rounded-md border border-stone-300 px-3 py-2 text-sm"
          >
            <option value="">All categories (global cycle)</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <label className="text-sm text-stone-600">
            Opens
            <input
              required
              type="datetime-local"
              value={form.order_window_opens_at}
              onChange={(e) => setForm((f) => ({ ...f, order_window_opens_at: e.target.value }))}
              className="mt-1 w-full rounded-md border border-stone-300 px-3 py-2 text-sm"
            />
          </label>
          <label className="text-sm text-stone-600">
            Closes
            <input
              required
              type="datetime-local"
              value={form.order_window_closes_at}
              onChange={(e) => setForm((f) => ({ ...f, order_window_closes_at: e.target.value }))}
              className="mt-1 w-full rounded-md border border-stone-300 px-3 py-2 text-sm"
            />
          </label>
        </div>
        <button type="submit" className="mt-3 w-full rounded-md bg-brand-600 px-3 py-2 text-sm font-medium text-white">
          Create cycle (draft)
        </button>
      </form>

      <div className="divide-y divide-stone-200 rounded-lg border border-stone-200 bg-white">
        {cycles.map((cycle) => (
          <div key={cycle.id} className="flex items-center justify-between p-4">
            <div>
              <Link to={`/admin/cycles/${cycle.id}`} className="font-medium text-stone-900 hover:text-brand-700">
                {cycle.name}
              </Link>
              <p className="text-sm text-stone-500">
                {formatDate(cycle.order_window_opens_at)} → {formatDate(cycle.order_window_closes_at)}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <span className={`rounded-full px-3 py-1 text-xs font-medium ${statusColor[cycle.status]}`}>
                {cycle.status}
              </span>
              {cycle.status === "draft" && (
                <button onClick={() => handleOpen(cycle.id)} className="text-sm text-brand-600 hover:underline">
                  Open
                </button>
              )}
              <Link to={`/admin/cycles/${cycle.id}`} className="text-sm text-stone-600 hover:underline">
                View
              </Link>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
