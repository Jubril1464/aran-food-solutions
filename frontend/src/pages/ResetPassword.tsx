import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import * as authApi from "../api/auth";
import { ApiError } from "../api/client";
import { ErrorBanner } from "../components/ErrorBanner";

export function ResetPassword() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get("token") || "";
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!token) {
      setError("Missing reset token.");
      return;
    }
    setSubmitting(true);
    try {
      await authApi.confirmPasswordReset(token, password);
      navigate("/login");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-sm px-4 py-16">
      <h1 className="mb-6 text-2xl font-bold text-stone-900">Choose a new password</h1>
      <form onSubmit={handleSubmit} className="space-y-4">
        <ErrorBanner message={error} />
        <div>
          <label className="mb-1 block text-sm font-medium text-stone-700">New password</label>
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-md border border-stone-300 px-3 py-2 focus:border-brand-500 focus:outline-none"
          />
        </div>
        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-md bg-brand-600 px-4 py-2 font-medium text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {submitting ? "Saving…" : "Save new password"}
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
