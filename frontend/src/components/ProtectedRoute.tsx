import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import type { UserRole } from "../types";

export function ProtectedRoute({ role }: { role?: UserRole }) {
  const { user, loading } = useAuth();

  if (loading) {
    return <div className="p-8 text-center text-stone-500">Loading…</div>;
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  if (role && user.role !== role) {
    return <Navigate to="/" replace />;
  }
  return <Outlet />;
}
