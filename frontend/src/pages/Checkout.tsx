import { useEffect, useState, type FormEvent } from "react";
import * as shopApi from "../api/shop";
import type { Address, Cart } from "../types";
import { formatNaira } from "../utils";
import { ErrorBanner } from "../components/ErrorBanner";
import { ApiError } from "../api/client";

export function Checkout() {
  const [cart, setCart] = useState<Cart | null>(null);
  const [addresses, setAddresses] = useState<Address[]>([]);
  const [selectedAddressId, setSelectedAddressId] = useState("");
  const [showNewAddress, setShowNewAddress] = useState(false);
  const [newAddress, setNewAddress] = useState({ label: "Home", street: "", city: "", state: "", phone_number: "" });
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const loadAddresses = () => {
    shopApi.listAddresses().then((addrs) => {
      setAddresses(addrs);
      const preferred = addrs.find((a) => a.is_default) ?? addrs[0];
      if (preferred) setSelectedAddressId(preferred.id);
      if (addrs.length === 0) setShowNewAddress(true);
    });
  };

  useEffect(() => {
    shopApi.getCart().then(setCart);
    loadAddresses();
  }, []);

  const handleAddAddress = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const created = await shopApi.createAddress({ ...newAddress, is_default: addresses.length === 0 });
      setAddresses((a) => [...a, created]);
      setSelectedAddressId(created.id);
      setShowNewAddress(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save address");
    }
  };

  const handlePlaceOrder = async () => {
    if (!selectedAddressId) {
      setError("Please select or add a delivery address.");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      const order = await shopApi.checkout(selectedAddressId);
      const payment = await shopApi.initializePayment(order.order_number);
      window.location.href = payment.authorization_url;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Checkout failed");
      setSubmitting(false);
    }
  };

  if (!cart) {
    return <p className="p-8 text-center text-stone-500">Loading…</p>;
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <h1 className="mb-6 text-2xl font-bold text-stone-900">Checkout</h1>
      <ErrorBanner message={error} />

      <section className="mt-4 rounded-lg border border-stone-200 bg-white p-4">
        <h2 className="mb-3 font-semibold text-stone-900">Delivery address</h2>
        <div className="space-y-2">
          {addresses.map((a) => (
            <label key={a.id} className="flex items-start gap-2 text-sm">
              <input
                type="radio"
                name="address"
                checked={selectedAddressId === a.id}
                onChange={() => setSelectedAddressId(a.id)}
              />
              <span>
                <strong>{a.label}</strong> — {a.street}, {a.city}, {a.state} ({a.phone_number})
              </span>
            </label>
          ))}
        </div>
        {!showNewAddress ? (
          <button onClick={() => setShowNewAddress(true)} className="mt-3 text-sm text-brand-600 hover:underline">
            + Add a new address
          </button>
        ) : (
          <form onSubmit={handleAddAddress} className="mt-3 space-y-2">
            <input
              placeholder="Street"
              required
              value={newAddress.street}
              onChange={(e) => setNewAddress((a) => ({ ...a, street: e.target.value }))}
              className="w-full rounded-md border border-stone-300 px-3 py-2 text-sm"
            />
            <div className="grid grid-cols-2 gap-2">
              <input
                placeholder="City"
                required
                value={newAddress.city}
                onChange={(e) => setNewAddress((a) => ({ ...a, city: e.target.value }))}
                className="rounded-md border border-stone-300 px-3 py-2 text-sm"
              />
              <input
                placeholder="State"
                required
                value={newAddress.state}
                onChange={(e) => setNewAddress((a) => ({ ...a, state: e.target.value }))}
                className="rounded-md border border-stone-300 px-3 py-2 text-sm"
              />
            </div>
            <input
              placeholder="Phone number"
              required
              value={newAddress.phone_number}
              onChange={(e) => setNewAddress((a) => ({ ...a, phone_number: e.target.value }))}
              className="w-full rounded-md border border-stone-300 px-3 py-2 text-sm"
            />
            <button type="submit" className="rounded-md bg-stone-800 px-3 py-1.5 text-sm font-medium text-white">
              Save address
            </button>
          </form>
        )}
      </section>

      <section className="mt-4 rounded-lg border border-stone-200 bg-white p-4">
        <h2 className="mb-3 font-semibold text-stone-900">Order summary</h2>
        <ul className="mb-3 space-y-1 text-sm text-stone-600">
          {cart.items.map((item) => (
            <li key={item.id} className="flex justify-between">
              <span>
                {item.product.name} × {item.quantity} {item.product.unit}
              </span>
              <span>{formatNaira(item.line_total)}</span>
            </li>
          ))}
        </ul>
        <div className="space-y-1 border-t border-stone-200 pt-2 text-sm">
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
          <div className="flex justify-between text-base font-bold">
            <span>Total</span>
            <span>{formatNaira(cart.total)}</span>
          </div>
        </div>
      </section>

      <button
        onClick={handlePlaceOrder}
        disabled={submitting || cart.items.length === 0}
        className="mt-6 w-full rounded-md bg-brand-600 px-4 py-3 font-medium text-white hover:bg-brand-700 disabled:opacity-50"
      >
        {submitting ? "Redirecting to payment…" : "Place order & pay"}
      </button>
    </div>
  );
}
