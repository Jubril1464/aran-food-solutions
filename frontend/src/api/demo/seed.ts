/**
 * Sample data for demo mode.
 *
 * Mirrors what the real backend's bootstrap (`backend/app/seed.py`) creates, so
 * a demo shows the same catalogue the deployed product would - plus a little
 * history (past orders, extra customers) so the admin screens aren't empty
 * tables, which is what makes a demo look unfinished.
 *
 * Passwords are stored in plain text here on purpose: this file never runs
 * anywhere near a real credential. Nothing in demo mode is a security boundary.
 */

import type {
  Address,
  Category,
  Order,
  OrderStatus,
  ProcurementCycle,
  Product,
  User,
} from "../../types";

export interface DemoUser extends User {
  password: string;
  created_at: string;
}

export interface DemoState {
  users: DemoUser[];
  addresses: (Address & { user_id: string })[];
  categories: Category[];
  products: Product[];
  cycles: ProcurementCycle[];
  orders: (Order & { user_id: string; status_history: { status: OrderStatus; note: string | null; created_at: string }[] })[];
  carts: Record<string, { id: string; items: { id: string; product_id: string; quantity: string }[] }>;
  /** Payment reference -> order number, for the mock Paystack round trip. */
  payments: Record<string, { order_number: string; status: string }>;
  /** Signed-in user id, so a page reload doesn't log you out. */
  sessionUserId: string | null;
}

const DAY = 86_400_000;

function iso(offsetDays: number): string {
  return new Date(Date.now() + offsetDays * DAY).toISOString();
}

/** Deterministic ids so links survive a page reload and read cleanly in a demo. */
const ID = {
  admin: "u-admin",
  buyer: "u-buyer",
  chidinma: "u-chidinma",
  tunde: "u-tunde",
  amaka: "u-amaka",
  grains: "c-grains",
  legumes: "c-legumes",
  tubers: "c-tubers",
  oils: "c-oils",
};

const categories: Category[] = [
  { id: ID.grains, name: "Grains & Cereals", slug: "grains-cereals" },
  { id: ID.legumes, name: "Legumes & Beans", slug: "legumes-beans" },
  { id: ID.tubers, name: "Tubers & Flour", slug: "tubers-flour" },
  { id: ID.oils, name: "Oils", slug: "oils" },
];

function product(
  id: string,
  categoryId: string,
  name: string,
  unit: string,
  price: string,
  moq: string,
  description: string,
  image: string
): Product {
  return {
    id,
    name,
    category_id: categoryId,
    category: categories.find((c) => c.id === categoryId) ?? null,
    description,
    unit,
    price,
    minimum_order_quantity: moq,
    is_available: true,
    // Served from frontend/public/products/. A root-relative path, so it
    // resolves against whichever origin the app is on - and works unchanged when
    // these products come from the real API instead.
    image_url: `/products/${image}.svg`,
    procurement_cycle_id: null,
  };
}

const products: Product[] = [
  product("p-rice", ID.grains, "Long Grain Rice (50kg bag)", "bag", "85000.00", "1.00",
    "Parboiled long grain rice, 50kg bag. Pooled directly from mill-level bulk purchase.", "rice"),
  // Deliberately above 1, so the minimum-order rule is visible in a demo.
  product("p-maize", ID.grains, "Yellow Maize (100kg bag)", "bag", "62000.00", "2.00",
    "Dried yellow maize, 100kg bag. Minimum two bags per order at this tier.", "maize"),
  product("p-millet", ID.grains, "Millet (50kg bag)", "bag", "48000.00", "1.00",
    "Cleaned millet, 50kg bag.", "millet"),
  product("p-beans", ID.legumes, "Brown Beans (50kg bag)", "bag", "97000.00", "1.00",
    "Oloyin brown beans, 50kg bag, hand-sorted.", "beans"),
  product("p-groundnut", ID.legumes, "Groundnuts (25kg bag)", "bag", "41000.00", "1.00",
    "Raw shelled groundnuts, 25kg bag.", "groundnuts"),
  product("p-garri", ID.tubers, "White Garri (50kg bag)", "bag", "43000.00", "1.00",
    "Fine white garri, 50kg bag.", "garri"),
  product("p-elubo", ID.tubers, "Yam Flour / Elubo (25kg bag)", "bag", "38000.00", "1.00",
    "Stone-milled yam flour, 25kg bag.", "elubo"),
  product("p-palm-oil", ID.oils, "Palm Oil (25 litre keg)", "keg", "52000.00", "1.00",
    "Unrefined red palm oil, 25 litre keg.", "palm-oil"),
  product("p-groundnut-oil", ID.oils, "Groundnut Oil (25 litre keg)", "keg", "64000.00", "1.00",
    "Filtered groundnut oil, 25 litre keg.", "groundnut-oil"),
];

function cycle(id: string, categoryId: string, name: string): ProcurementCycle {
  return {
    id,
    name,
    category_id: categoryId,
    // The window has to span "now" or checkout has nothing to attach an order to.
    order_window_opens_at: iso(-1),
    order_window_closes_at: iso(13),
    status: "open",
  };
}

const monthLabel = new Date().toLocaleDateString("en-NG", { month: "long", year: "numeric" });

const cycles: ProcurementCycle[] = [
  cycle("cy-grains", ID.grains, `${monthLabel} — Grains & Cereals`),
  cycle("cy-legumes", ID.legumes, `${monthLabel} — Legumes & Beans`),
  cycle("cy-tubers", ID.tubers, `${monthLabel} — Tubers & Flour`),
  cycle("cy-oils", ID.oils, `${monthLabel} — Oils`),
];

function user(
  id: string,
  fullName: string,
  email: string,
  phone: string,
  password: string,
  role: "admin" | "customer",
  createdDaysAgo: number,
  businessName: string | null = null
): DemoUser {
  return {
    id,
    full_name: fullName,
    email,
    phone_number: phone,
    role,
    business_name: businessName,
    business_type: businessName ? "restaurant" : null,
    is_verified: true,
    is_active: true,
    password,
    created_at: iso(-createdDaysAgo),
  };
}

/** Credentials shown on the sign-in screen in demo mode. */
export const DEMO_CREDENTIALS = {
  admin: { email: "admin@aranfood.example", password: "demo-admin" },
  customer: { email: "buyer@aranfood.example", password: "demo-buyer" },
};

const users: DemoUser[] = [
  user(ID.admin, "Platform Administrator", DEMO_CREDENTIALS.admin.email, "+2348000000000",
    DEMO_CREDENTIALS.admin.password, "admin", 90),
  user(ID.buyer, "Demo Buyer", DEMO_CREDENTIALS.customer.email, "+2348011111111",
    DEMO_CREDENTIALS.customer.password, "customer", 45, "Buka Express"),
  user(ID.chidinma, "Chidinma Okeke", "chidinma@example.com", "+2348022222222", "demo", "customer", 30),
  user(ID.tunde, "Tunde Bakare", "tunde@example.com", "+2348033333333", "demo", "customer", 18,
    "Bakare Foods"),
  user(ID.amaka, "Amaka Nwosu", "amaka@example.com", "+2348044444444", "demo", "customer", 6),
];

const addresses: (Address & { user_id: string })[] = [
  { id: "a-buyer", user_id: ID.buyer, label: "Home", street: "12 Market Road", city: "Ibadan",
    state: "Oyo", phone_number: "+2348011111111", is_default: true },
  { id: "a-chidinma", user_id: ID.chidinma, label: "Home", street: "4 Aba Road", city: "Port Harcourt",
    state: "Rivers", phone_number: "+2348022222222", is_default: true },
  { id: "a-tunde", user_id: ID.tunde, label: "Shop", street: "9 Allen Avenue", city: "Ikeja",
    state: "Lagos", phone_number: "+2348033333333", is_default: true },
];

const DELIVERY_FEE = "1000.00";

/**
 * Past orders, so the customer's history and every admin table has something in
 * it. Amounts are precomputed to match the fee rules the cart applies
 * (2.5% service fee + a flat delivery fee).
 */
function order(
  id: string,
  userId: string,
  orderNumber: string,
  status: OrderStatus,
  daysAgo: number,
  lines: { productId: string; quantity: string }[]
) {
  const items = lines.map((line, index) => {
    const p = products.find((x) => x.id === line.productId)!;
    const lineTotal = (Number(p.price) * Number(line.quantity)).toFixed(2);
    return {
      id: `${id}-i${index}`,
      product_id: p.id,
      product_name: p.name,
      quantity: Number(line.quantity).toFixed(2),
      unit_price: p.price,
      line_total: lineTotal,
      procurement_cycle_id: cycles.find((c) => c.category_id === p.category_id)!.id,
    };
  });
  const subtotal = items.reduce((sum, i) => sum + Number(i.line_total), 0);
  const serviceFee = subtotal * 0.025;

  // A plausible trail rather than just the final state, so the tracking page has
  // something to show.
  const flow: OrderStatus[] = ["PENDING_PAYMENT", "PAID", "CONFIRMED", "AGGREGATING", "PROCUREMENT",
    "RECEIVED", "PROCESSING", "PACKAGED", "DISPATCHED", "DELIVERED"];
  const reached = flow.slice(0, Math.max(1, flow.indexOf(status) + 1));
  const history = (reached.includes(status) ? reached : [status]).map((s, index) => ({
    status: s,
    note: null,
    created_at: iso(-daysAgo + index * 0.2),
  }));

  return {
    id,
    user_id: userId,
    order_number: orderNumber,
    status,
    subtotal: subtotal.toFixed(2),
    delivery_fee: DELIVERY_FEE,
    service_fee: serviceFee.toFixed(2),
    total: (subtotal + serviceFee + Number(DELIVERY_FEE)).toFixed(2),
    created_at: iso(-daysAgo),
    items,
    status_history: history,
  };
}

export function createDemoState(): DemoState {
  return {
    users: users.map((u) => ({ ...u })),
    addresses: addresses.map((a) => ({ ...a })),
    categories: categories.map((c) => ({ ...c })),
    products: products.map((p) => ({ ...p })),
    cycles: cycles.map((c) => ({ ...c })),
    orders: [
      order("o-1", ID.buyer, "ORD-20260805-A31F7C", "DELIVERED", 16, [{ productId: "p-rice", quantity: "2" }]),
      order("o-2", ID.buyer, "ORD-20260814-B88E21", "PROCUREMENT", 7, [
        { productId: "p-beans", quantity: "1" },
        { productId: "p-garri", quantity: "2" },
      ]),
      order("o-3", ID.chidinma, "ORD-20260817-C40A93", "CONFIRMED", 4, [{ productId: "p-palm-oil", quantity: "3" }]),
      order("o-4", ID.tunde, "ORD-20260819-D17B55", "PAID", 2, [
        { productId: "p-maize", quantity: "4" },
        { productId: "p-millet", quantity: "1" },
      ]),
      order("o-5", ID.amaka, "ORD-20260820-E92C08", "PENDING_PAYMENT", 1, [
        { productId: "p-elubo", quantity: "1" },
      ]),
    ],
    carts: {},
    payments: {},
    sessionUserId: null,
  };
}
