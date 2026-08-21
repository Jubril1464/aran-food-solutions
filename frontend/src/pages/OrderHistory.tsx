import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import * as shopApi from "../api/shop";
import type { Order } from "../types";
import { formatDate, formatNaira, STATUS_COLORS, STATUS_LABELS } from "../utils";

export function OrderHistory() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    shopApi
      .listMyOrders(statusFilter || undefined)
      .then((res) => setOrders(res.orders))
      .finally(() => setLoading(false));
  }, [statusFilter]);

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-stone-900">Your orders</h1>
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
      {loading ? (
        <p className="text-stone-500">Loading…</p>
      ) : orders.length === 0 ? (
        <p className="text-stone-500">No orders yet.</p>
      ) : (
        <div className="divide-y divide-stone-200 rounded-lg border border-stone-200 bg-white">
          {orders.map((order) => (
            <Link
              key={order.id}
              to={`/orders/${order.order_number}`}
              className="flex items-center justify-between p-4 hover:bg-stone-50"
            >
              <div>
                <p className="font-medium text-stone-900">{order.order_number}</p>
                <p className="text-sm text-stone-500">{formatDate(order.created_at)}</p>
              </div>
              <div className="flex items-center gap-4">
                <span className="font-medium">{formatNaira(order.total)}</span>
                <span className={`rounded-full px-3 py-1 text-xs font-medium ${STATUS_COLORS[order.status]}`}>
                  {STATUS_LABELS[order.status]}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
