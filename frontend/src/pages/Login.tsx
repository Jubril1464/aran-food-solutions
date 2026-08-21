import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../api/client";
import { ErrorBanner } from "../components/ErrorBanner";
import { DEMO_CREDENTIALS, DEMO_MODE } from "../api/demo";

export function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  };

  // Fills the form rather than logging straight in, so whoever is watching sees
  // which account is being used.
  const fillDemoAccount = (account: { email: string; password: string }) => {
    setEmail(account.email);
    setPassword(account.password);
    setError(null);
  };

  return (
    <div className="mx-auto max-w-sm px-4 py-16">
      <h1 className="mb-6 text-2xl font-bold text-stone-900">Log in</h1>
      {DEMO_MODE && (
        <div className="mb-6 rounded-md border border-stone-200 bg-stone-50 p-3">
          <p className="mb-2 text-xs font-medium text-stone-600">Demo accounts</p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => fillDemoAccount(DEMO_CREDENTIALS.admin)}
              className="flex-1 rounded border border-stone-300 bg-white px-2 py-1.5 text-xs font-medium text-stone-700 hover:bg-stone-100"
            >
              Administrator
            </button>
            <button
              type="button"
              onClick={() => fillDemoAccount(DEMO_CREDENTIALS.customer)}
              className="flex-1 rounded border border-stone-300 bg-white px-2 py-1.5 text-xs font-medium text-stone-700 hover:bg-stone-100"
            >
              Customer
            </button>
          </div>
        </div>
      )}
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
        <div>
          <label className="mb-1 block text-sm font-medium text-stone-700">Password</label>
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
          {submitting ? "Logging in…" : "Log in"}
        </button>
      </form>
      <div className="mt-4 flex justify-between text-sm">
        <Link to="/forgot-password" className="text-brand-600 hover:underline">
          Forgot password?
        </Link>
        <Link to="/register" className="text-brand-600 hover:underline">
          Create an account
        </Link>
      </div>
    </div>
  );
}
