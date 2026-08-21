import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import * as authApi from "../api/auth";
import { ApiError } from "../api/client";
import { ErrorBanner } from "../components/ErrorBanner";

export function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await authApi.requestPasswordReset(email);
      setSent(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  };

  if (sent) {
    return (
      <div className="mx-auto max-w-sm px-4 py-16 text-center">
        <h1 className="mb-2 text-2xl font-bold text-stone-900">Check your email</h1>
        <p className="text-stone-600">If an account exists for {email}, we've sent a reset link.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-sm px-4 py-16">
      <h1 className="mb-6 text-2xl font-bold text-stone-900">Reset your password</h1>
      <form onSubmit={handleSubmit} className="space-y-4">
        <ErrorBanner message={error} />
        <div>
          <label className="mb-1 block text-sm font-medium text-stone-700">Email</label>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-md border border-stone-300 px-3 py-2 focus:border-brand-500 focus:outline-none"
          />
        </div>
        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-md bg-brand-600 px-4 py-2 font-medium text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {submitting ? "Sending…" : "Send reset link"}
        </button>
      </form>
      <p className="mt-4 text-sm">
        <Link to="/login" className="text-brand-600 hover:underline">
          Back to login
        </Link>
      </p>
    </div>
  );
}
