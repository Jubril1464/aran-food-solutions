import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { Navbar } from "./components/Navbar";
import { ProtectedRoute } from "./components/ProtectedRoute";

import { Login } from "./pages/Login";
import { Register } from "./pages/Register";
import { VerifyEmail } from "./pages/VerifyEmail";
import { ForgotPassword } from "./pages/ForgotPassword";
import { ResetPassword } from "./pages/ResetPassword";
import { Catalogue } from "./pages/Catalogue";
import { ProductDetail } from "./pages/ProductDetail";
import { Cart } from "./pages/Cart";
import { Checkout } from "./pages/Checkout";
import { MockPaystackCheckout } from "./pages/MockPaystackCheckout";
import { OrderHistory } from "./pages/OrderHistory";
import { OrderTracking } from "./pages/OrderTracking";

import { Dashboard } from "./pages/admin/Dashboard";
import { Products } from "./pages/admin/Products";
import { Customers } from "./pages/admin/Customers";
import { CustomerDetail } from "./pages/admin/CustomerDetail";
import { ProcurementCycles } from "./pages/admin/ProcurementCycles";
import { CycleDetail } from "./pages/admin/CycleDetail";
import { Orders } from "./pages/admin/Orders";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Navbar />
        <Routes>
          {/* Public */}
          <Route path="/" element={<Catalogue />} />
          <Route path="/products/:productId" element={<ProductDetail />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/verify" element={<VerifyEmail />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/mock-paystack-checkout" element={<MockPaystackCheckout />} />

          {/* Any authenticated user can track/view their own order by number */}
          <Route path="/orders/:orderNumber" element={<OrderTracking />} />

          {/* Customer-only */}
          <Route element={<ProtectedRoute role="customer" />}>
            <Route path="/cart" element={<Cart />} />
            <Route path="/checkout" element={<Checkout />} />
            <Route path="/orders" element={<OrderHistory />} />
          </Route>

          {/* Admin-only */}
          <Route element={<ProtectedRoute role="admin" />}>
            <Route path="/admin" element={<Dashboard />} />
            <Route path="/admin/products" element={<Products />} />
            <Route path="/admin/customers" element={<Customers />} />
            <Route path="/admin/customers/:customerId" element={<CustomerDetail />} />
            <Route path="/admin/cycles" element={<ProcurementCycles />} />
            <Route path="/admin/cycles/:cycleId" element={<CycleDetail />} />
            <Route path="/admin/orders" element={<Orders />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
