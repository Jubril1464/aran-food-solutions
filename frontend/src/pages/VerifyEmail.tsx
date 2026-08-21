import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import * as authApi from "../api/auth";
import { ApiError } from "../api/client";

export function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = searchParams.get("token");
    if (!token) {
      setStatus("error");
      setError("Missing verification token.");
      return;
    }
    authApi
      .verifyAccount(token)
      .then(() => setStatus("success"))
      .catch((err) => {
        setStatus("error");
        setError(err instanceof ApiError ? err.message : "Verification failed");
      });
  }, [searchParams]);

  return (
    <div className="mx-auto max-w-sm px-4 py-16 text-center">
      {status === "loading" && <p className="text-stone-600">Verifying your account…</p>}
      {status === "success" && (
        <>
          <h1 className="mb-2 text-2xl font-bold text-stone-900">Account verified</h1>
          <p className="mb-4 text-stone-600">You can now log in.</p>
          <Link to="/login" className="text-brand-600 hover:underline">
            Go to login
          </Link>
        </>
      )}
      {status === "error" && (
        <>
          <h1 className="mb-2 text-2xl font-bold text-stone-900">Verification failed</h1>
          <p className="text-stone-600">{error}</p>
        </>
      )}
    </div>
  );
}
