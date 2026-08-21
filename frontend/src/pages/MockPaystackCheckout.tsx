import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import * as shopApi from "../api/shop";
import { ApiError } from "../api/client";
import { ErrorBanner } from "../components/ErrorBanner";

/**
 * Stands in for Paystack's hosted checkout page when the backend has no
 * PAYSTACK_SECRET_KEY configured (mock mode) — lets the whole checkout →
 * payment → order-confirmed flow be exercised locally without a real
 * Paystack account. Never used when a real secret key is set: initialize_payment
 * then returns a real Paystack authorization_url instead of this route.
 */
export function MockPaystackCheckout() {
  const [searchParams] = useSearchParams();
  const reference = searchParams.get("reference") || "";
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handlePay = async () => {
    setError(null);
    setSubmitting(true);
    try {
      await shopApi.verifyPayment(reference);
      navigate("/orders");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Payment verification failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-sm px-4 py-16 text-center">
      <div className="rounded-lg border border-dashed border-amber-400 bg-amber-50 p-6">
        <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-amber-700">Development mode</p>
        <h1 className="mb-2 text-xl font-bold text-stone-900">Mock Paystack Checkout</h1>
        <p className="mb-4 text-sm text-stone-600">
          No PAYSTACK_SECRET_KEY is configured on the backend, so this stands in for the real hosted checkout page.
          Reference: <code className="text-xs">{reference}</code>
        </p>
        <ErrorBanner message={error} />
        <button
          onClick={handlePay}
          disabled={submitting}
          className="mt-3 w-full rounded-md bg-brand-600 px-4 py-2 font-medium text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {submitting ? "Processing…" : "Simulate successful payment"}
        </button>
      </div>
    </div>
  );
}
