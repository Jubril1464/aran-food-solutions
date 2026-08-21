import { useState } from "react";
import { Link } from "react-router-dom";
import type { Product } from "../types";
import { formatNaira } from "../utils";
import { useAuth } from "../context/AuthContext";
import * as shopApi from "../api/shop";
import { ApiError } from "../api/client";

export function ProductCard({ product, onAdded }: { product: Product; onAdded?: () => void }) {
  const { user } = useAuth();
  const [quantity, setQuantity] = useState(product.minimum_order_quantity);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [added, setAdded] = useState(false);

  const handleAdd = async () => {
    setError(null);
    setAdding(true);
    setAdded(false);
    try {
      await shopApi.addCartItem(product.id, quantity);
      setAdded(true);
      onAdded?.();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not add to cart");
    } finally {
      setAdding(false);
    }
  };

  return (
    <div className="flex flex-col overflow-hidden rounded-lg border border-stone-200 bg-white">
      <div className="aspect-[4/3] w-full bg-stone-100">
        {product.image_url ? (
          <img src={product.image_url} alt={product.name} className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full items-center justify-center text-stone-400">No image</div>
        )}
      </div>
      <div className="flex flex-1 flex-col gap-2 p-4">
        <Link to={`/products/${product.id}`} className="font-semibold text-stone-900 hover:text-brand-700">
          {product.name}
        </Link>
        <span className="text-xs uppercase tracking-wide text-stone-500">{product.category?.name}</span>
        <div className="mt-1 flex items-baseline justify-between">
          <span className="text-lg font-bold text-brand-700">{formatNaira(product.price)}</span>
          <span className="text-xs text-stone-500">per {product.unit}</span>
        </div>
        <p className="text-xs text-stone-500">
          Min. order: {product.minimum_order_quantity} {product.unit}
        </p>
        {!product.is_available && (
          <span className="rounded bg-stone-100 px-2 py-1 text-xs font-medium text-stone-600">Unavailable</span>
        )}
        {user?.role === "customer" && product.is_available && (
          <div className="mt-auto flex items-center gap-2 pt-2">
            <input
              type="number"
              min={product.minimum_order_quantity}
              step="0.01"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              className="w-20 rounded-md border border-stone-300 px-2 py-1 text-sm"
            />
            <button
              onClick={handleAdd}
              disabled={adding}
              className="flex-1 rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
            >
              {adding ? "Adding…" : added ? "Added ✓" : "Add to cart"}
            </button>
          </div>
        )}
        {error && <p className="text-xs text-red-600">{error}</p>}
      </div>
    </div>
  );
}
