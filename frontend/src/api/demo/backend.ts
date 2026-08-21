/**
 * An in-browser stand-in for the FastAPI backend, for demo mode.
 *
 * Every route the frontend calls is implemented against the in-memory state in
 * seed.ts, including the rules worth demonstrating: minimum order quantities,
 * cycle resolution at checkout, the payment round trip, and admin-only access.
 * Wrong inputs return the same status codes the real API does, so the UI's error
 * handling is exercised rather than bypassed.
 *
 * Deliberately free of browser APIs and `import.meta`, so it can be driven
 * directly from a test.
 */

import type {
  AggregationReport,
  Cart,
  CartItem,
  CustomerDetail,
  CustomerSummary,
  Order,
  OrderDetail,
  OrderStatus,
  Product,
  User,
} from "../../types";
import type { DemoState, DemoUser } from "./seed";

export interface DemoResponse {
  status: number;
  body: unknown;
}

const DELIVERY_FEE = 1000;
const SERVICE_FEE_PERCENT = 2.5;

/** Money as an integer number of kobo, so repeated arithmetic can't drift. */
const kobo = (amount: string | number) => Math.round(Number(amount) * 100);
const naira = (k: number) => (k / 100).toFixed(2);

const ok = (body: unknown): DemoResponse => ({ status: 200, body });
const created = (body: unknown): DemoResponse => ({ status: 201, body });
const noContent = (): DemoResponse => ({ status: 204, body: null });
const fail = (status: number, detail: string): DemoResponse => ({ status, body: { detail } });

const newId = () =>
  typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `id-${Math.random().toString(36).slice(2)}`;

function publicUser(u: DemoUser): User {
  const { password: _password, created_at: _createdAt, ...rest } = u;
  return rest;
}

// --- cart -------------------------------------------------------------------

function cartOf(state: DemoState, userId: string) {
  if (!state.carts[userId]) {
    state.carts[userId] = { id: `cart-${userId}`, items: [] };
  }
  return state.carts[userId];
}

function renderCart(state: DemoState, userId: string): Cart {
  const cart = cartOf(state, userId);
  const items: CartItem[] = cart.items.flatMap((item) => {
    const product = state.products.find((p) => p.id === item.product_id);
    if (!product) return [];
    return [{
      id: item.id,
      product,
      quantity: Number(item.quantity).toFixed(2),
      line_total: naira(kobo(product.price) * Number(item.quantity)),
    }];
  });
  const subtotal = items.reduce((sum, i) => sum + kobo(i.line_total), 0);
  const serviceFee = Math.round((subtotal * SERVICE_FEE_PERCENT) / 100);
  const deliveryFee = items.length ? kobo(DELIVERY_FEE) : 0;
  return {
    id: cart.id,
    items,
    subtotal: naira(subtotal),
    delivery_fee: naira(deliveryFee),
    service_fee: naira(serviceFee),
    total: naira(subtotal + serviceFee + deliveryFee),
  };
}

// --- orders -----------------------------------------------------------------

function publicOrder(o: DemoState["orders"][number]): Order {
  const { user_id: _userId, status_history: _history, ...rest } = o;
  return rest;
}

function detailOrder(o: DemoState["orders"][number]): OrderDetail {
  const { user_id: _userId, ...rest } = o;
  return rest;
}

function orderNumber(): string {
  const now = new Date();
  const stamp = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}${String(now.getDate()).padStart(2, "0")}`;
  return `ORD-${stamp}-${newId().replace(/-/g, "").slice(0, 6).toUpperCase()}`;
}

function advance(order: DemoState["orders"][number], status: OrderStatus, note: string | null = null) {
  order.status = status;
  order.status_history.push({ status, note, created_at: new Date().toISOString() });
}

/** The cycle a product's order line attaches to: its category's open cycle. */
function activeCycleFor(state: DemoState, product: Product) {
  const now = Date.now();
  return state.cycles.find(
    (c) =>
      c.category_id === product.category_id &&
      c.status === "open" &&
      Date.parse(c.order_window_opens_at) <= now &&
      now <= Date.parse(c.order_window_closes_at)
  );
}

// --- router -----------------------------------------------------------------

export interface DemoRequest {
  method: string;
  /** Path after the API prefix, e.g. "/products?available_only=true". */
  path: string;
  body?: unknown;
  /** Bearer token, if the caller sent one. */
  token?: string | null;
}

const TOKEN_PREFIX = "demo-token:";

export function handleDemoRequest(state: DemoState, request: DemoRequest): DemoResponse {
  const [rawPath, rawQuery = ""] = request.path.split("?");
  const path = rawPath.replace(/\/$/, "") || "/";
  const query = new URLSearchParams(rawQuery);
  const method = request.method.toUpperCase();
  const body = (request.body ?? {}) as Record<string, string | boolean | null>;

  const authUser = (): DemoUser | null => {
    if (!request.token?.startsWith(TOKEN_PREFIX)) return null;
    const id = request.token.slice(TOKEN_PREFIX.length);
    return state.users.find((u) => u.id === id && u.is_active) ?? null;
  };

  const route = `${method} ${path}`;

  // ---- auth ----------------------------------------------------------------

  if (route === "POST /auth/login") {
    const user = state.users.find((u) => u.email.toLowerCase() === String(body.email ?? "").toLowerCase());
    if (!user || user.password !== body.password) {
      return fail(401, "Incorrect email or password");
    }
    if (!user.is_active) return fail(403, "Account is deactivated");
    state.sessionUserId = user.id;
    return ok({ access_token: TOKEN_PREFIX + user.id, token_type: "bearer" });
  }

  if (route === "POST /auth/register") {
    const email = String(body.email ?? "").toLowerCase();
    if (state.users.some((u) => u.email.toLowerCase() === email)) {
      return fail(409, "An account with this email already exists");
    }
    const user: DemoUser = {
      id: newId(),
      full_name: String(body.full_name ?? ""),
      email: String(body.email ?? ""),
      phone_number: String(body.phone_number ?? ""),
      role: "customer",
      business_name: (body.business_name as string) || null,
      business_type: (body.business_type as string) || null,
      // Skipped rather than pretended: there is no mailbox in demo mode, and an
      // unverifiable account would dead-end the flow being demonstrated.
      is_verified: true,
      is_active: true,
      password: String(body.password ?? ""),
      created_at: new Date().toISOString(),
    };
    state.users.push(user);
    if (body.street) {
      state.addresses.push({
        id: newId(),
        user_id: user.id,
        label: "Home",
        street: String(body.street),
        city: String(body.city ?? ""),
        state: String(body.state ?? ""),
        phone_number: user.phone_number,
        is_default: true,
      });
    }
    return created(publicUser(user));
  }

  if (route === "POST /auth/refresh") {
    if (!state.sessionUserId) return fail(401, "Missing refresh token");
    const user = state.users.find((u) => u.id === state.sessionUserId);
    if (!user) return fail(401, "Invalid refresh token");
    return ok({ access_token: TOKEN_PREFIX + user.id, token_type: "bearer" });
  }

  if (route === "POST /auth/logout") {
    state.sessionUserId = null;
    return noContent();
  }

  if (route === "GET /auth/me") {
    const user = authUser();
    return user ? ok(publicUser(user)) : fail(401, "Not authenticated");
  }

  if (route === "POST /auth/verify") {
    const user = state.users.find((u) => u.id === state.sessionUserId) ?? state.users[1];
    user.is_verified = true;
    return ok(publicUser(user));
  }

  // Accepted and ignored: there is no mail in demo mode, and the UI only needs
  // the success path to show its confirmation screen.
  if (route === "POST /auth/password-reset/request" || route === "POST /auth/password-reset/confirm") {
    return noContent();
  }

  // ---- catalogue (public) --------------------------------------------------

  if (route === "GET /categories") return ok(state.categories);

  if (route === "GET /products") {
    let items = state.products;
    const categoryId = query.get("category_id");
    const search = query.get("search");
    if (categoryId) items = items.filter((p) => p.category_id === categoryId);
    if (query.get("available_only") === "true") items = items.filter((p) => p.is_available);
    if (search) {
      const needle = search.toLowerCase();
      items = items.filter((p) => p.name.toLowerCase().includes(needle));
    }
    return ok([...items].sort((a, b) => a.name.localeCompare(b.name)));
  }

  if (method === "GET" && path.startsWith("/products/")) {
    const product = state.products.find((p) => p.id === path.slice("/products/".length));
    return product ? ok(product) : fail(404, "Product not found");
  }

  // ---- everything below needs a signed-in user -----------------------------

  const user = authUser();
  if (!user) return fail(401, "Not authenticated");

  const requireAdmin = () => user.role === "admin";
  if (path.startsWith("/admin") && !requireAdmin()) {
    return fail(403, "Insufficient permissions");
  }

  // ---- cart ----------------------------------------------------------------

  if (route === "GET /cart") return ok(renderCart(state, user.id));

  if (route === "POST /cart/items") {
    const product = state.products.find((p) => p.id === body.product_id);
    if (!product) return fail(404, "Product not found");
    if (!product.is_available) return fail(400, `${product.name} is not currently available`);
    const quantity = Number(body.quantity);
    if (!Number.isFinite(quantity) || quantity <= 0) return fail(400, "Quantity must be greater than zero");
    if (quantity < Number(product.minimum_order_quantity)) {
      return fail(
        400,
        `Minimum order quantity for ${product.name} is ${Number(product.minimum_order_quantity).toFixed(2)} ${product.unit}`
      );
    }
    const cart = cartOf(state, user.id);
    const existing = cart.items.find((i) => i.product_id === product.id);
    if (existing) {
      existing.quantity = String(Number(existing.quantity) + quantity);
    } else {
      cart.items.push({ id: newId(), product_id: product.id, quantity: String(quantity) });
    }
    return ok(renderCart(state, user.id));
  }

  if (method === "PATCH" && path.startsWith("/cart/items/")) {
    const cart = cartOf(state, user.id);
    const item = cart.items.find((i) => i.id === path.slice("/cart/items/".length));
    if (!item) return fail(404, "Cart item not found");
    const product = state.products.find((p) => p.id === item.product_id)!;
    const quantity = Number(body.quantity);
    if (quantity < Number(product.minimum_order_quantity)) {
      return fail(
        400,
        `Minimum order quantity for ${product.name} is ${Number(product.minimum_order_quantity).toFixed(2)} ${product.unit}`
      );
    }
    item.quantity = String(quantity);
    return ok(renderCart(state, user.id));
  }

  if (method === "DELETE" && path.startsWith("/cart/items/")) {
    const cart = cartOf(state, user.id);
    const id = path.slice("/cart/items/".length);
    cart.items = cart.items.filter((i) => i.id !== id);
    return ok(renderCart(state, user.id));
  }

  // ---- addresses -----------------------------------------------------------

  if (route === "GET /users/addresses") {
    return ok(state.addresses.filter((a) => a.user_id === user.id).map(({ user_id: _u, ...a }) => a));
  }

  if (route === "POST /users/addresses") {
    const address = {
      id: newId(),
      user_id: user.id,
      label: String(body.label ?? "Home"),
      street: String(body.street ?? ""),
      city: String(body.city ?? ""),
      state: String(body.state ?? ""),
      phone_number: String(body.phone_number ?? user.phone_number),
      is_default: Boolean(body.is_default),
    };
    state.addresses.push(address);
    const { user_id: _u, ...rest } = address;
    return created(rest);
  }

  // ---- checkout & orders ---------------------------------------------------

  if (route === "POST /orders/checkout") {
    const cart = cartOf(state, user.id);
    if (!cart.items.length) return fail(400, "Your cart is empty");
    if (!state.addresses.some((a) => a.id === body.delivery_address_id && a.user_id === user.id)) {
      return fail(404, "Delivery address not found");
    }

    const lines = [];
    for (const item of cart.items) {
      const product = state.products.find((p) => p.id === item.product_id)!;
      const cycle = activeCycleFor(state, product);
      if (!cycle) {
        return fail(400, `There is no open procurement cycle for ${product.name} right now`);
      }
      lines.push({
        id: newId(),
        product_id: product.id,
        product_name: product.name,
        quantity: Number(item.quantity).toFixed(2),
        unit_price: product.price,
        line_total: naira(kobo(product.price) * Number(item.quantity)),
        procurement_cycle_id: cycle.id,
      });
    }

    const subtotal = lines.reduce((sum, l) => sum + kobo(l.line_total), 0);
    const serviceFee = Math.round((subtotal * SERVICE_FEE_PERCENT) / 100);
    const order = {
      id: newId(),
      user_id: user.id,
      order_number: orderNumber(),
      status: "PENDING_PAYMENT" as OrderStatus,
      subtotal: naira(subtotal),
      delivery_fee: naira(kobo(DELIVERY_FEE)),
      service_fee: naira(serviceFee),
      total: naira(subtotal + serviceFee + kobo(DELIVERY_FEE)),
      created_at: new Date().toISOString(),
      items: lines,
      status_history: [{ status: "PENDING_PAYMENT" as OrderStatus, note: null, created_at: new Date().toISOString() }],
    };
    state.orders.unshift(order);
    cart.items = [];
    return created(detailOrder(order));
  }

  if (route === "GET /orders") {
    const status = query.get("status");
    const mine = state.orders.filter((o) => o.user_id === user.id && (!status || o.status === status));
    return ok({ orders: mine.map(publicOrder), total: mine.length });
  }

  if (method === "GET" && path.startsWith("/orders/")) {
    const number = path.slice("/orders/".length);
    const order = state.orders.find((o) => o.order_number === number && o.user_id === user.id);
    return order ? ok(detailOrder(order)) : fail(404, "Order not found");
  }

  // ---- payments ------------------------------------------------------------

  if (route === "POST /payments/initialize") {
    const order = state.orders.find((o) => o.order_number === body.order_number && o.user_id === user.id);
    if (!order) return fail(404, "Order not found");
    if (order.status !== "PENDING_PAYMENT") return fail(400, "This order is not awaiting payment");
    const reference = `aran_${newId().replace(/-/g, "")}`;
    state.payments[reference] = { order_number: order.order_number, status: "pending" };
    return ok({
      // Relative on purpose: the browser resolves it against whatever origin the
      // demo is hosted on, so no build-time URL is needed.
      authorization_url: `/mock-paystack-checkout?reference=${reference}`,
      access_code: `mock_${reference}`,
      reference,
    });
  }

  if (method === "GET" && path.startsWith("/payments/") && path.endsWith("/verify")) {
    const reference = path.slice("/payments/".length, -"/verify".length);
    const payment = state.payments[reference];
    if (!payment) return fail(404, "Payment not found");
    const order = state.orders.find((o) => o.order_number === payment.order_number);
    if (!order) return fail(404, "Order not found");
    // Idempotent, exactly like the real verify endpoint: replaying it must not
    // move an already-paid order on a second time.
    if (payment.status !== "successful") {
      payment.status = "successful";
      advance(order, "PAID", "Payment confirmed");
      advance(order, "CONFIRMED", "Attached to procurement cycle");
    }
    return ok({ status: "successful", reference, amount: order.total, channel: "mock" });
  }

  // ---- admin: catalogue ----------------------------------------------------

  if (route === "POST /admin/categories") {
    const name = String(body.name ?? "").trim();
    if (!name) return fail(400, "Name is required");
    const category = { id: newId(), name, slug: name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") };
    state.categories.push(category);
    return created(category);
  }

  if (route === "POST /admin/products") {
    const category = state.categories.find((c) => c.id === body.category_id);
    if (!category) return fail(404, "Category not found");
    const product: Product = {
      id: newId(),
      name: String(body.name ?? ""),
      category_id: category.id,
      category,
      description: (body.description as string) || null,
      unit: String(body.unit ?? "bag"),
      price: Number(body.price ?? 0).toFixed(2),
      minimum_order_quantity: Number(body.minimum_order_quantity ?? 1).toFixed(2),
      is_available: body.is_available !== false,
      image_url: null,
      procurement_cycle_id: (body.procurement_cycle_id as string) || null,
    };
    state.products.push(product);
    return created(product);
  }

  if (method === "PUT" && path.startsWith("/admin/products/")) {
    const product = state.products.find((p) => p.id === path.slice("/admin/products/".length));
    if (!product) return fail(404, "Product not found");
    if (body.name !== undefined) product.name = String(body.name);
    if (body.description !== undefined) product.description = (body.description as string) || null;
    if (body.unit !== undefined) product.unit = String(body.unit);
    if (body.price !== undefined) product.price = Number(body.price).toFixed(2);
    if (body.minimum_order_quantity !== undefined) {
      product.minimum_order_quantity = Number(body.minimum_order_quantity).toFixed(2);
    }
    if (body.is_available !== undefined) product.is_available = Boolean(body.is_available);
    if (body.category_id !== undefined) {
      const category = state.categories.find((c) => c.id === body.category_id);
      if (category) {
        product.category_id = category.id;
        product.category = category;
      }
    }
    return ok(product);
  }

  if (method === "DELETE" && path.startsWith("/admin/products/")) {
    const id = path.slice("/admin/products/".length);
    state.products = state.products.filter((p) => p.id !== id);
    return noContent();
  }

  // ---- admin: customers ----------------------------------------------------

  if (route === "GET /admin/customers") {
    const search = (query.get("search") ?? "").toLowerCase();
    const page = Number(query.get("page") ?? 1);
    const pageSize = Number(query.get("page_size") ?? 20);
    const all = state.users
      .filter((u) => u.role === "customer")
      .filter((u) =>
        !search ||
        u.full_name.toLowerCase().includes(search) ||
        u.email.toLowerCase().includes(search) ||
        u.phone_number.includes(search)
      );
    const slice = all.slice((page - 1) * pageSize, page * pageSize);
    const customers: CustomerSummary[] = slice.map((u) => ({
      id: u.id,
      full_name: u.full_name,
      email: u.email,
      phone_number: u.phone_number,
      business_name: u.business_name,
      is_active: u.is_active,
      is_verified: u.is_verified,
      created_at: u.created_at,
    }));
    return ok({ customers, total: all.length, page, page_size: pageSize });
  }

  if (method === "GET" && path.startsWith("/admin/customers/")) {
    const id = path.slice("/admin/customers/".length);
    const customer = state.users.find((u) => u.id === id);
    if (!customer) return fail(404, "Customer not found");
    const detail: CustomerDetail = {
      id: customer.id,
      full_name: customer.full_name,
      email: customer.email,
      phone_number: customer.phone_number,
      business_name: customer.business_name,
      is_active: customer.is_active,
      is_verified: customer.is_verified,
      created_at: customer.created_at,
      addresses: state.addresses.filter((a) => a.user_id === customer.id).map(({ user_id: _u, ...a }) => a),
      orders: state.orders.filter((o) => o.user_id === customer.id).map(publicOrder),
    };
    return ok(detail);
  }

  if (method === "PATCH" && path.startsWith("/admin/customers/") && path.endsWith("/active")) {
    const id = path.slice("/admin/customers/".length, -"/active".length);
    const customer = state.users.find((u) => u.id === id);
    if (!customer) return fail(404, "Customer not found");
    customer.is_active = Boolean(body.is_active);
    return handleDemoRequest(state, { ...request, method: "GET", path: `/admin/customers/${id}` });
  }

  // ---- admin: procurement cycles -------------------------------------------

  if (route === "GET /admin/procurement-cycles") {
    return ok([...state.cycles].sort(
      (a, b) => Date.parse(b.order_window_opens_at) - Date.parse(a.order_window_opens_at)
    ));
  }

  if (route === "POST /admin/procurement-cycles") {
    if (Date.parse(String(body.order_window_closes_at)) <= Date.parse(String(body.order_window_opens_at))) {
      return fail(400, "Close time must be after open time");
    }
    const cycle = {
      id: newId(),
      name: String(body.name ?? "Untitled cycle"),
      category_id: (body.category_id as string) || null,
      order_window_opens_at: String(body.order_window_opens_at),
      order_window_closes_at: String(body.order_window_closes_at),
      status: "draft" as const,
    };
    state.cycles.push(cycle);
    return created(cycle);
  }

  if (method === "POST" && path.startsWith("/admin/procurement-cycles/") && path.endsWith("/open")) {
    const id = path.slice("/admin/procurement-cycles/".length, -"/open".length);
    const cycle = state.cycles.find((c) => c.id === id);
    if (!cycle) return fail(404, "Procurement cycle not found");
    if (cycle.status !== "draft") return fail(400, "Only draft cycles can be opened");
    // The same one-open-cycle-per-category rule the real service enforces.
    if (state.cycles.some((c) => c.id !== cycle.id && c.status === "open" && c.category_id === cycle.category_id)) {
      return fail(409, "Another cycle is already open for this category. Close it before opening a new one.");
    }
    cycle.status = "open";
    return ok(cycle);
  }

  if (method === "POST" && path.startsWith("/admin/procurement-cycles/") && path.endsWith("/close")) {
    const id = path.slice("/admin/procurement-cycles/".length, -"/close".length);
    const cycle = state.cycles.find((c) => c.id === id);
    if (!cycle) return fail(404, "Procurement cycle not found");
    if (cycle.status !== "open") return fail(400, "Only open cycles can be closed");
    cycle.status = "closed";
    // Closing aggregates demand: every order wholly inside this cycle moves on.
    for (const order of state.orders) {
      if (order.status !== "CONFIRMED") continue;
      if (order.items.every((i) => i.procurement_cycle_id === cycle.id)) {
        advance(order, "AGGREGATING", `Cycle ${cycle.name} closed`);
      }
    }
    return ok(cycle);
  }

  if (method === "GET" && path.startsWith("/admin/procurement-cycles/") && path.endsWith("/aggregation")) {
    const id = path.slice("/admin/procurement-cycles/".length, -"/aggregation".length);
    const cycle = state.cycles.find((c) => c.id === id);
    if (!cycle) return fail(404, "Procurement cycle not found");
    const totals = new Map<string, number>();
    for (const order of state.orders) {
      if (order.status === "CANCELLED" || order.status === "PENDING_PAYMENT") continue;
      for (const item of order.items) {
        if (item.procurement_cycle_id !== cycle.id) continue;
        totals.set(item.product_id, (totals.get(item.product_id) ?? 0) + Number(item.quantity));
      }
    }
    const report: AggregationReport = {
      cycle_id: cycle.id,
      cycle_name: cycle.name,
      lines: [...totals.entries()].map(([productId, quantity]) => {
        const product = state.products.find((p) => p.id === productId);
        return {
          product_id: productId,
          product_name: product?.name ?? "Unknown product",
          unit: product?.unit ?? "unit",
          total_quantity: quantity.toFixed(2),
        };
      }),
    };
    return ok(report);
  }

  // ---- admin: orders & analytics -------------------------------------------

  if (route === "GET /admin/orders") {
    const status = query.get("status");
    const all = state.orders.filter((o) => !status || o.status === status);
    return ok({ orders: all.map(publicOrder), total: all.length });
  }

  if (method === "POST" && path.startsWith("/admin/orders/") && path.endsWith("/cancel")) {
    const number = path.slice("/admin/orders/".length, -"/cancel".length);
    const order = state.orders.find((o) => o.order_number === number);
    if (!order) return fail(404, "Order not found");
    const refund = query.get("refund") === "true";
    advance(order, refund ? "REFUNDED" : "CANCELLED", refund ? "Cancelled with refund" : "Cancelled");
    return ok(publicOrder(order));
  }

  if (route === "GET /admin/analytics/summary") {
    const gmv = state.orders
      .filter((o) => o.status !== "CANCELLED" && o.status !== "PENDING_PAYMENT")
      .reduce((sum, o) => sum + kobo(o.total), 0);
    return ok({
      customers: state.users.filter((u) => u.role === "customer").length,
      products: state.products.length,
      orders: state.orders.length,
      orders_awaiting_payment: state.orders.filter((o) => o.status === "PENDING_PAYMENT").length,
      active_procurement_cycles: state.cycles.filter((c) => c.status === "open").length,
      gmv: naira(gmv),
    });
  }

  return fail(404, `Demo mode has no handler for ${method} ${path}`);
}
