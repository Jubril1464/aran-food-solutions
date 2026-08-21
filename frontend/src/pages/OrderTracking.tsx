import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import * as shopApi from "../api/shop";
import type { OrderDetail } from "../types";
import { formatDate, formatNaira, STATUS_COLORS, STATUS_LABELS } from "../utils";
import { ErrorBanner } from "../components/ErrorBanner";
import { ApiError } from "../api/client";

const TIMELINE_ORDER = [
  "PENDING_PAYMENT",
  "PAID",
  "CONFIRMED",
  "AGGREGATING",
  "PROCUREMENT",
  "RECEIVED",
  "PROCESSING",
  "PACKAGED",
  "DISPATCHED",
  "DELIVERED",
];

export function OrderTracking() {
  const { orderNumber } = useParams();
  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!orderNumber) return;
    shopApi
      .getOrder(orderNumber)
      .then(setOrder)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Order not found"));
  }, [orderNumber]);

  if (error) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-8">
        <ErrorBanner message={error} />
      </div>
    );
  }
  if (!order) {
    return <p className="p-8 text-center text-stone-500">Loading…</p>;
  }

  const reachedStatuses = new Set(order.status_history.map((h) => h.status));
  const isException = !TIMELINE_ORDER.includes(order.status);

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-stone-900">{order.order_number}</h1>
          <p className="text-sm text-stone-500">{formatDate(order.created_at)}</p>
        </div>
        <span className={`rounded-full px-3 py-1 text-sm font-medium ${STATUS_COLORS[order.status]}`}>
          {STATUS_LABELS[order.status]}
        </span>
      </div>

      {!isException && (
        <ol className="mb-8 flex flex-wrap gap-2">
          {TIMELINE_ORDER.map((status) => {
            const reached = reachedStatuses.has(status as never);
            return (
              <li
                key={status}
                className={`rounded-full border px-3 py-1 text-xs font-medium ${
                  reached ? "border-brand-500 bg-brand-50 text-brand-700" : "border-stone-200 text-stone-400"
                }`}
              >
                {STATUS_LABELS[status]}
              </li>
            );
          })}
        </ol>
      )}

      <section className="mb-6 rounded-lg border border-stone-200 bg-white p-4">
        <h2 className="mb-3 font-semibold text-stone-900">Items</h2>
        <ul className="space-y-1 text-sm text-stone-600">
          {order.items.map((item) => (
            <li key={item.id} className="flex justify-between">
              <span>
                {item.product_name} × {item.quantity}
              </span>
              <span>{formatNaira(item.line_total)}</span>
            </li>
          ))}
        </ul>
        <div className="mt-3 flex justify-between border-t border-stone-200 pt-2 text-base font-bold">
          <span>Total</span>
          <span>{formatNaira(order.total)}</span>
        </div>
      </section>

      <section className="rounded-lg border border-stone-200 bg-white p-4">
        <h2 className="mb-3 font-semibold text-stone-900">History</h2>
        <ul className="space-y-2 text-sm">
          {order.status_history.map((entry, idx) => (
            <li key={idx} className="flex justify-between text-stone-600">
              <span>{STATUS_LABELS[entry.status] ?? entry.status}</span>
              <span>{formatDate(entry.created_at)}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
