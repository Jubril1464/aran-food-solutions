import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import * as adminApi from "../../api/admin";
import type { CustomerSummary } from "../../types";
import { formatDate } from "../../utils";

export function Customers() {
  const [customers, setCustomers] = useState<CustomerSummary[]>([]);
  const [search, setSearch] = useState("");

  useEffect(() => {
    adminApi.listCustomers({ search: search || undefined }).then((res) => setCustomers(res.customers));
  }, [search]);

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-stone-900">Customers</h1>
        <input
          type="search"
          placeholder="Search name, email, phone…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="rounded-md border border-stone-300 px-3 py-2 text-sm"
        />
      </div>
      <div className="divide-y divide-stone-200 rounded-lg border border-stone-200 bg-white">
        {customers.map((c) => (
          <Link key={c.id} to={`/admin/customers/${c.id}`} className="flex items-center justify-between p-4 hover:bg-stone-50">
            <div>
              <p className="font-medium text-stone-900">{c.full_name}</p>
              <p className="text-sm text-stone-500">
                {c.email} · {c.phone_number}
              </p>
            </div>
            <div className="flex items-center gap-3 text-sm">
              <span className="text-stone-400">Joined {formatDate(c.created_at)}</span>
              {!c.is_active && <span className="rounded bg-stone-200 px-2 py-1 text-xs">Deactivated</span>}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
