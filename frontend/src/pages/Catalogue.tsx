import { useEffect, useState } from "react";
import * as shopApi from "../api/shop";
import type { Category, Product } from "../types";
import { ProductCard } from "../components/ProductCard";
import { ErrorBanner } from "../components/ErrorBanner";
import { ApiError } from "../api/client";

export function Catalogue() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [categoryId, setCategoryId] = useState("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    shopApi.listCategories().then(setCategories).catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    shopApi
      .listProducts({ category_id: categoryId || undefined, search: search || undefined })
      .then(setProducts)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load products"))
      .finally(() => setLoading(false));
  }, [categoryId, search]);

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="mb-6 text-2xl font-bold text-stone-900">Browse products</h1>
      <div className="mb-6 flex flex-wrap gap-3">
        <input
          type="search"
          placeholder="Search products…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="rounded-md border border-stone-300 px-3 py-2 text-sm"
        />
        <select
          value={categoryId}
          onChange={(e) => setCategoryId(e.target.value)}
          className="rounded-md border border-stone-300 px-3 py-2 text-sm"
        >
          <option value="">All categories</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>
      <ErrorBanner message={error} />
      {loading ? (
        <p className="text-stone-500">Loading…</p>
      ) : products.length === 0 ? (
        <p className="text-stone-500">No products found.</p>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {products.map((p) => (
            <ProductCard key={p.id} product={p} />
          ))}
        </div>
      )}
    </div>
  );
}
