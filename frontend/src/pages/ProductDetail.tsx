import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import * as shopApi from "../api/shop";
import type { Product } from "../types";
import { ProductCard } from "../components/ProductCard";
import { ErrorBanner } from "../components/ErrorBanner";
import { ApiError } from "../api/client";

export function ProductDetail() {
  const { productId } = useParams();
  const [product, setProduct] = useState<Product | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!productId) return;
    shopApi
      .getProduct(productId)
      .then(setProduct)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Product not found"));
  }, [productId]);

  if (error) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-8">
        <ErrorBanner message={error} />
      </div>
    );
  }

  if (!product) {
    return <p className="p-8 text-center text-stone-500">Loading…</p>;
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <ProductCard product={product} />
      {product.description && (
        <div className="mt-6">
          <h2 className="mb-2 text-lg font-semibold text-stone-900">Description</h2>
          <p className="text-stone-600">{product.description}</p>
        </div>
      )}
    </div>
  );
}
