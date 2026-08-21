import { apiFetch } from "./client";
import type { Address, Cart, Category, Order, OrderDetail, Product } from "../types";

// --- Products & categories ---

export function listCategories() {
  return apiFetch<Category[]>("/categories");
}

export function listProducts(params: { category_id?: string; available_only?: boolean; search?: string } = {}) {
  const qs = new URLSearchParams();
  if (params.category_id) qs.set("category_id", params.category_id);
  if (params.available_only) qs.set("available_only", "true");
  if (params.search) qs.set("search", params.search);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch<Product[]>(`/products${suffix}`);
}

export function getProduct(productId: string) {
  return apiFetch<Product>(`/products/${productId}`);
}

// --- Cart ---

export function getCart() {
  return apiFetch<Cart>("/cart");
}

export function addCartItem(product_id: string, quantity: string) {
  return apiFetch<Cart>("/cart/items", { method: "POST", body: { product_id, quantity } });
}

export function updateCartItem(itemId: string, quantity: string) {
  return apiFetch<Cart>(`/cart/items/${itemId}`, { method: "PATCH", body: { quantity } });
}

export function removeCartItem(itemId: string) {
  return apiFetch<Cart>(`/cart/items/${itemId}`, { method: "DELETE" });
}

// --- Addresses ---

export function listAddresses() {
  return apiFetch<Address[]>("/users/addresses");
}

export function createAddress(data: Omit<Address, "id">) {
  return apiFetch<Address>("/users/addresses", { method: "POST", body: data });
}

// --- Orders ---

export function checkout(delivery_address_id: string) {
  return apiFetch<OrderDetail>("/orders/checkout", { method: "POST", body: { delivery_address_id } });
}

export function listMyOrders(status?: string) {
  const suffix = status ? `?status=${status}` : "";
  return apiFetch<{ orders: Order[]; total: number }>(`/orders${suffix}`);
}

export function getOrder(orderNumber: string) {
  return apiFetch<OrderDetail>(`/orders/${orderNumber}`);
}

// --- Payments ---

export function initializePayment(order_number: string) {
  return apiFetch<{ authorization_url: string; access_code: string; reference: string }>("/payments/initialize", {
    method: "POST",
    body: { order_number },
  });
}

export function verifyPayment(reference: string) {
  return apiFetch<{ status: string }>(`/payments/${reference}/verify`);
}
