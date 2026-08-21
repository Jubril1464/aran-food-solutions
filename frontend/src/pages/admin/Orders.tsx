import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import * as adminApi from "../../api/admin";
import type { Order } from "../../types";
import { formatDate, formatNaira, STATUS_COLORS, STATUS_LABELS } from "../../utils";
import { ErrorBanner } from "../../components/ErrorBanner";
import { ApiError } from "../../api/client";

const CANCELLABLE = new Set(["PENDING_PAYMENT", "PAID", "CONFIRMED", "AGGREGATING", "PROCUREMENT"]);

export function Orders() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = () => adminApi.listAllOrders(statusFilter || undefined).then((res) => setOrders(res.orders));

  useEffect(() => {
    load();
  }, [statusFilter]);

  const handleCancel = async (orderNumber: string, refund: boolean) => {
    if (!confirm(`${refund ? "Refund" : "Cancel"} order ${orderNumber}?`)) return;
    setError(null);
    try {
      await adminApi.cancelOrder(orderNumber, refund);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not update order");
    }
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-stone-900">All orders</h1>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-md border border-stone-300 px-3 py-2 text-sm"
        >
          <option value="">All statuses</option>
          {Object.entries(STATUS_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>
      <ErrorBanner message={error} />
      <div className="divide-y divide-stone-200 rounded-lg border border-stone-200 bg-white">
        {orders.map((order) => (
          <div key={order.id} className="flex items-center justify-between p-4">
            <Link to={`/orders/${order.order_number}`} className="hover:text-brand-700">
              <p className="font-medium text-stone-900">{order.order_number}</p>
              <p className="text-sm text-stone-500">{formatDate(order.created_at)}</p>
            </Link>
            <div className="flex items-center gap-3">
              <span className="font-medium">{formatNaira(order.total)}</span>
              <span className={`rounded-full px-3 py-1 text-xs font-medium ${STATUS_COLORS[order.status]}`}>
                {STATUS_LABELS[order.status]}
              </span>
              {CANCELLABLE.has(order.status) && (
                <>
                  <button onClick={() => handleCancel(order.order_number, false)} className="text-sm text-stone-600 hover:underline">
                    Cancel
                  </button>
                  <button onClick={() => handleCancel(order.order_number, true)} className="text-sm text-red-600 hover:underline">
                    Refund
                  </button>
                </>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
