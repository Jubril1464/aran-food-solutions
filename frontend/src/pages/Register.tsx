import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import * as authApi from "../api/auth";
import { ApiError } from "../api/client";
import { ErrorBanner } from "../components/ErrorBanner";

const emptyForm = {
  full_name: "",
  phone_number: "",
  email: "",
  password: "",
  street: "",
  city: "",
  state: "",
  business_name: "",
  business_type: "",
};

export function Register() {
  const [form, setForm] = useState(emptyForm);
  const [isBusiness, setIsBusiness] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const update = (field: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [field]: e.target.value }));

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await authApi.register({
        ...form,
        business_name: isBusiness ? form.business_name : undefined,
        business_type: isBusiness ? form.business_type : undefined,
      });
      setSuccess(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  };

  if (success) {
    return (
      <div className="mx-auto max-w-sm px-4 py-16 text-center">
        <h1 className="mb-2 text-2xl font-bold text-stone-900">Check your email</h1>
        <p className="text-stone-600">
          We've sent a verification link to <strong>{form.email}</strong>. Verify your account, then{" "}
          <Link to="/login" className="text-brand-600 hover:underline">
            log in
          </Link>
          .
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-md px-4 py-16">
      <h1 className="mb-6 text-2xl font-bold text-stone-900">Create an account</h1>
      <form onSubmit={handleSubmit} className="space-y-4">
        <ErrorBanner message={error} />
        <Field label="Full name" value={form.full_name} onChange={update("full_name")} />
        <Field label="Phone number" value={form.phone_number} onChange={update("phone_number")} placeholder="+234..." />
        <Field label="Email" type="email" value={form.email} onChange={update("email")} />
        <Field label="Password" type="password" value={form.password} onChange={update("password")} />
        <Field label="Street address" value={form.street} onChange={update("street")} />
        <div className="grid grid-cols-2 gap-4">
          <Field label="City" value={form.city} onChange={update("city")} />
          <Field label="State" value={form.state} onChange={update("state")} />
        </div>
        <label className="flex items-center gap-2 text-sm text-stone-700">
          <input type="checkbox" checked={isBusiness} onChange={(e) => setIsBusiness(e.target.checked)} />
          I'm registering as a business
        </label>
        {isBusiness && (
          <div className="grid grid-cols-2 gap-4">
            <Field label="Business name" value={form.business_name} onChange={update("business_name")} />
            <Field label="Business type" value={form.business_type} onChange={update("business_type")} />
          </div>
        )}
        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-md bg-brand-600 px-4 py-2 font-medium text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {submitting ? "Creating account…" : "Create account"}
        </button>
      </form>
      <p className="mt-4 text-sm">
        Already have an account?{" "}
        <Link to="/login" className="text-brand-600 hover:underline">
          Log in
        </Link>
      </p>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  type = "text",
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  type?: string;
  placeholder?: string;
}) {
  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-stone-700">{label}</label>
      <input
        type={type}
        required
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        className="w-full rounded-md border border-stone-300 px-3 py-2 focus:border-brand-500 focus:outline-none"
      />
    </div>
  );
}
