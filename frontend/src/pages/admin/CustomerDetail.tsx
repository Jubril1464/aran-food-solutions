import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import * as adminApi from "../../api/admin";
import type { CustomerDetail as CustomerDetailType } from "../../types";
import { formatDate, formatNaira, STATUS_COLORS, STATUS_LABELS } from "../../utils";

export function CustomerDetail() {
  const { customerId } = useParams();
  const [customer, setCustomer] = useState<CustomerDetailType | null>(null);

  const load = () => {
    if (customerId) adminApi.getCustomer(customerId).then(setCustomer);
  };

  useEffect(load, [customerId]);

  const toggleActive = async () => {
    if (!customer) return;
    await adminApi.setCustomerActive(customer.id, !customer.is_active);
    load();
  };

  if (!customer) {
    return <p className="p-8 text-center text-stone-500">Loading…</p>;
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-stone-900">{customer.full_name}</h1>
          <p className="text-sm text-stone-500">
            {customer.email} · {customer.phone_number}
          </p>
          {customer.business_name && <p className="text-sm text-stone-500">Business: {customer.business_name}</p>}
        </div>
        <button
          onClick={toggleActive}
          className={`rounded-md px-3 py-1.5 text-sm font-medium ${
            customer.is_active ? "border border-red-300 text-red-700 hover:bg-red-50" : "bg-brand-600 text-white hover:bg-brand-700"
          }`}
        >
          {customer.is_active ? "Deactivate account" : "Reactivate account"}
        </button>
      </div>

      <section className="mb-6 rounded-lg border border-stone-200 bg-white p-4">
        <h2 className="mb-3 font-semibold text-stone-900">Addresses</h2>
        {customer.addresses.length === 0 ? (
          <p className="text-sm text-stone-500">No addresses on file.</p>
        ) : (
          <ul className="space-y-1 text-sm text-stone-600">
            {customer.addresses.map((a) => (
              <li key={a.id}>
                <strong>{a.label}</strong> — {a.street}, {a.city}, {a.state}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded-lg border border-stone-200 bg-white p-4">
        <h2 className="mb-3 font-semibold text-stone-900">Order history</h2>
        {customer.orders.length === 0 ? (
          <p className="text-sm text-stone-500">No orders yet.</p>
        ) : (
          <div className="divide-y divide-stone-200">
            {customer.orders.map((o) => (
              <Link key={o.id} to={`/orders/${o.order_number}`} className="flex items-center justify-between py-3 hover:bg-stone-50">
                <div>
                  <p className="font-medium text-stone-900">{o.order_number}</p>
                  <p className="text-xs text-stone-500">{formatDate(o.created_at)}</p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-sm font-medium">{formatNaira(o.total)}</span>
                  <span className={`rounded-full px-2 py-1 text-xs font-medium ${STATUS_COLORS[o.status]}`}>
                    {STATUS_LABELS[o.status]}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
