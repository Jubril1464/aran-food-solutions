import { Link, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-2 rounded-md text-sm font-medium ${isActive ? "bg-brand-100 text-brand-700" : "text-stone-600 hover:bg-stone-100"}`;

export function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <header className="border-b border-stone-200 bg-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <Link to="/" className="text-lg font-bold text-brand-700">
          Aran Food Solutions
        </Link>
        <nav className="flex items-center gap-1">
          <NavLink to="/" className={navLinkClass} end>
            Shop
          </NavLink>
          {user?.role === "customer" && (
            <>
              <NavLink to="/cart" className={navLinkClass}>
                Cart
              </NavLink>
              <NavLink to="/orders" className={navLinkClass}>
                Orders
              </NavLink>
            </>
          )}
          {user?.role === "admin" && (
            <>
              <NavLink to="/admin" className={navLinkClass} end>
                Dashboard
              </NavLink>
              <NavLink to="/admin/products" className={navLinkClass}>
                Products
              </NavLink>
              <NavLink to="/admin/customers" className={navLinkClass}>
                Customers
              </NavLink>
              <NavLink to="/admin/cycles" className={navLinkClass}>
                Procurement
              </NavLink>
              <NavLink to="/admin/orders" className={navLinkClass}>
                Orders
              </NavLink>
            </>
          )}
        </nav>
        <div className="flex items-center gap-3">
          {user ? (
            <>
              <span className="text-sm text-stone-600">{user.full_name}</span>
              <button
                onClick={handleLogout}
                className="rounded-md border border-stone-300 px-3 py-1.5 text-sm font-medium hover:bg-stone-100"
              >
                Log out
              </button>
            </>
          ) : (
            <>
              <Link to="/login" className="text-sm font-medium text-stone-600 hover:text-stone-900">
                Log in
              </Link>
              <Link
                to="/register"
                className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700"
              >
                Sign up
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
