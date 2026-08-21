import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import * as shopApi from "../api/shop";
import type { Cart as CartType } from "../types";
import { formatNaira } from "../utils";
import { ErrorBanner } from "../components/ErrorBanner";
import { ApiError } from "../api/client";

export function Cart() {
  const [cart, setCart] = useState<CartType | null>(null);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const load = () => {
    shopApi
      .getCart()
      .then(setCart)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load cart"));
  };

  useEffect(load, []);

  const handleQuantityChange = async (itemId: string, quantity: string) => {
    setError(null);
    try {
      const updated = await shopApi.updateCartItem(itemId, quantity);
      setCart(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not update item");
    }
  };

  const handleRemove = async (itemId: string) => {
    setError(null);
    try {
      const updated = await shopApi.removeCartItem(itemId);
      setCart(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not remove item");
    }
  };

  if (!cart) {
    return <p className="p-8 text-center text-stone-500">Loading…</p>;
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <h1 className="mb-6 text-2xl font-bold text-stone-900">Your cart</h1>
      <ErrorBanner message={error} />
      {cart.items.length === 0 ? (
        <p className="text-stone-500">
          Your cart is empty.{" "}
          <Link to="/" className="text-brand-600 hover:underline">
            Browse products
          </Link>
        </p>
      ) : (
        <>
          <div className="divide-y divide-stone-200 rounded-lg border border-stone-200 bg-white">
            {cart.items.map((item) => (
              <div key={item.id} className="flex items-center gap-4 p-4">
                <div className="flex-1">
                  <p className="font-medium text-stone-900">{item.product.name}</p>
                  <p className="text-sm text-stone-500">
                    {formatNaira(item.product.price)} / {item.product.unit}
                  </p>
                </div>
                <input
                  type="number"
                  min={item.product.minimum_order_quantity}
                  step="0.01"
                  defaultValue={item.quantity}
                  onBlur={(e) => handleQuantityChange(item.id, e.target.value)}
                  className="w-20 rounded-md border border-stone-300 px-2 py-1 text-sm"
                />
                <span className="w-28 text-right font-medium">{formatNaira(item.line_total)}</span>
                <button onClick={() => handleRemove(item.id)} className="text-sm text-red-600 hover:underline">
                  Remove
                </button>
              </div>
            ))}
          </div>
          <div className="mt-6 space-y-1 rounded-lg border border-stone-200 bg-white p-4 text-sm">
            <div className="flex justify-between">
              <span className="text-stone-600">Subtotal</span>
              <span>{formatNaira(cart.subtotal)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-stone-600">Delivery fee</span>
              <span>{formatNaira(cart.delivery_fee)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-stone-600">Service fee</span>
              <span>{formatNaira(cart.service_fee)}</span>
            </div>
            <div className="flex justify-between border-t border-stone-200 pt-2 text-base font-bold">
              <span>Total</span>
              <span>{formatNaira(cart.total)}</span>
            </div>
          </div>
          <button
            onClick={() => navigate("/checkout")}
            className="mt-6 w-full rounded-md bg-brand-600 px-4 py-3 font-medium text-white hover:bg-brand-700"
          >
            Proceed to checkout
          </button>
        </>
      )}
    </div>
  );
}
