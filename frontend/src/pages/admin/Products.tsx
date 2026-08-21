import { useEffect, useState, type FormEvent } from "react";
import * as shopApi from "../../api/shop";
import * as adminApi from "../../api/admin";
import type { Category, Product } from "../../types";
import { formatNaira } from "../../utils";
import { ErrorBanner } from "../../components/ErrorBanner";
import { ApiError } from "../../api/client";

const emptyProduct = { name: "", category_id: "", unit: "kg", price: "", minimum_order_quantity: "1" };

export function Products() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [newCategoryName, setNewCategoryName] = useState("");
  const [form, setForm] = useState(emptyProduct);
  const [error, setError] = useState<string | null>(null);

  const loadAll = () => {
    shopApi.listCategories().then(setCategories);
    shopApi.listProducts().then(setProducts);
  };

  useEffect(loadAll, []);

  const handleCreateCategory = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await adminApi.createCategory(newCategoryName);
      setNewCategoryName("");
      loadAll();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create category");
    }
  };

  const handleCreateProduct = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await adminApi.createProduct(form);
      setForm(emptyProduct);
      loadAll();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create product");
    }
  };

  const toggleAvailability = async (product: Product) => {
    await adminApi.updateProduct(product.id, { is_available: !product.is_available });
    loadAll();
  };

  const handleDelete = async (product: Product) => {
    if (!confirm(`Delete ${product.name}?`)) return;
    await adminApi.deleteProduct(product.id);
    loadAll();
  };

  const handleImageUpload = async (product: Product, file: File) => {
    await adminApi.uploadProductImage(product.id, file);
    loadAll();
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <h1 className="mb-6 text-2xl font-bold text-stone-900">Products</h1>
      <ErrorBanner message={error} />

      <div className="mb-6 grid gap-4 md:grid-cols-2">
        <form onSubmit={handleCreateCategory} className="rounded-lg border border-stone-200 bg-white p-4">
          <h2 className="mb-3 font-semibold text-stone-900">New category</h2>
          <div className="flex gap-2">
            <input
              required
              value={newCategoryName}
              onChange={(e) => setNewCategoryName(e.target.value)}
              placeholder="e.g. Grains"
              className="flex-1 rounded-md border border-stone-300 px-3 py-2 text-sm"
            />
            <button type="submit" className="rounded-md bg-stone-800 px-3 py-2 text-sm font-medium text-white">
              Add
            </button>
          </div>
        </form>

        <form onSubmit={handleCreateProduct} className="rounded-lg border border-stone-200 bg-white p-4">
          <h2 className="mb-3 font-semibold text-stone-900">New product</h2>
          <div className="grid grid-cols-2 gap-2">
            <input
              required
              placeholder="Name"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              className="col-span-2 rounded-md border border-stone-300 px-3 py-2 text-sm"
            />
            <select
              required
              value={form.category_id}
              onChange={(e) => setForm((f) => ({ ...f, category_id: e.target.value }))}
              className="col-span-2 rounded-md border border-stone-300 px-3 py-2 text-sm"
            >
              <option value="">Select category</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
            <input
              required
              placeholder="Unit (kg, bag…)"
              value={form.unit}
              onChange={(e) => setForm((f) => ({ ...f, unit: e.target.value }))}
              className="rounded-md border border-stone-300 px-3 py-2 text-sm"
            />
            <input
              required
              type="number"
              step="0.01"
              placeholder="Price (NGN)"
              value={form.price}
              onChange={(e) => setForm((f) => ({ ...f, price: e.target.value }))}
              className="rounded-md border border-stone-300 px-3 py-2 text-sm"
            />
            <input
              required
              type="number"
              step="0.01"
              placeholder="Min order qty"
              value={form.minimum_order_quantity}
              onChange={(e) => setForm((f) => ({ ...f, minimum_order_quantity: e.target.value }))}
              className="col-span-2 rounded-md border border-stone-300 px-3 py-2 text-sm"
            />
          </div>
          <button type="submit" className="mt-3 w-full rounded-md bg-brand-600 px-3 py-2 text-sm font-medium text-white">
            Create product
          </button>
        </form>
      </div>

      <div className="divide-y divide-stone-200 rounded-lg border border-stone-200 bg-white">
        {products.map((p) => (
          <div key={p.id} className="flex items-center gap-4 p-4">
            <div className="h-12 w-12 flex-shrink-0 overflow-hidden rounded bg-stone-100">
              {p.image_url && <img src={p.image_url} alt={p.name} className="h-full w-full object-cover" />}
            </div>
            <div className="flex-1">
              <p className="font-medium text-stone-900">{p.name}</p>
              <p className="text-sm text-stone-500">
                {p.category?.name} · {formatNaira(p.price)} / {p.unit} · MOQ {p.minimum_order_quantity}
              </p>
            </div>
            <label className="cursor-pointer text-sm text-brand-600 hover:underline">
              Upload image
              <input
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && handleImageUpload(p, e.target.files[0])}
              />
            </label>
            <button onClick={() => toggleAvailability(p)} className="text-sm text-stone-600 hover:underline">
              {p.is_available ? "Mark unavailable" : "Mark available"}
            </button>
            <button onClick={() => handleDelete(p)} className="text-sm text-red-600 hover:underline">
              Delete
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
