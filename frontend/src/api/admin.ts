import { apiFetch } from "./client";
import type {
  AggregationReport,
  AnalyticsSummary,
  Category,
  CustomerDetail,
  CustomerSummary,
  Order,
  Product,
  ProcurementCycle,
} from "../types";

// --- Products & categories ---

export function createCategory(name: string) {
  return apiFetch<Category>("/admin/categories", { method: "POST", body: { name } });
}

export interface ProductPayload {
  name: string;
  category_id: string;
  description?: string;
  unit: string;
  price: string;
  minimum_order_quantity: string;
  is_available?: boolean;
  procurement_cycle_id?: string | null;
}

export function createProduct(data: ProductPayload) {
  return apiFetch<Product>("/admin/products", { method: "POST", body: data });
}

export function updateProduct(productId: string, data: Partial<ProductPayload>) {
  return apiFetch<Product>(`/admin/products/${productId}`, { method: "PUT", body: data });
}

export function deleteProduct(productId: string) {
  return apiFetch<void>(`/admin/products/${productId}`, { method: "DELETE" });
}

export function uploadProductImage(productId: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  return apiFetch<Product>(`/admin/products/${productId}/image`, { method: "POST", body: form });
}

// --- Customers ---

export function listCustomers(params: { search?: string; page?: number; page_size?: number } = {}) {
  const qs = new URLSearchParams();
  if (params.search) qs.set("search", params.search);
  if (params.page) qs.set("page", String(params.page));
  if (params.page_size) qs.set("page_size", String(params.page_size));
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch<{ customers: CustomerSummary[]; total: number; page: number; page_size: number }>(
    `/admin/customers${suffix}`
  );
}

export function getCustomer(customerId: string) {
  return apiFetch<CustomerDetail>(`/admin/customers/${customerId}`);
}

export function setCustomerActive(customerId: string, is_active: boolean) {
  return apiFetch<CustomerDetail>(`/admin/customers/${customerId}/active`, { method: "PATCH", body: { is_active } });
}

// --- Procurement cycles ---

export function listCycles() {
  return apiFetch<ProcurementCycle[]>("/admin/procurement-cycles");
}

export interface CyclePayload {
  name: string;
  category_id?: string | null;
  order_window_opens_at: string;
  order_window_closes_at: string;
}

export function createCycle(data: CyclePayload) {
  return apiFetch<ProcurementCycle>("/admin/procurement-cycles", { method: "POST", body: data });
}

export function openCycle(cycleId: string) {
  return apiFetch<ProcurementCycle>(`/admin/procurement-cycles/${cycleId}/open`, { method: "POST" });
}

export function closeCycle(cycleId: string) {
  return apiFetch<ProcurementCycle>(`/admin/procurement-cycles/${cycleId}/close`, { method: "POST" });
}

export function getAggregation(cycleId: string) {
  return apiFetch<AggregationReport>(`/admin/procurement-cycles/${cycleId}/aggregation`);
}

// --- Orders ---

export function listAllOrders(status?: string) {
  const suffix = status ? `?status=${status}` : "";
  return apiFetch<{ orders: Order[]; total: number }>(`/admin/orders${suffix}`);
}

export function cancelOrder(orderNumber: string, refund: boolean) {
  return apiFetch<Order>(`/admin/orders/${orderNumber}/cancel?refund=${refund}`, { method: "POST" });
}

// --- Analytics ---

export function getAnalyticsSummary() {
  return apiFetch<AnalyticsSummary>("/admin/analytics/summary");
}
