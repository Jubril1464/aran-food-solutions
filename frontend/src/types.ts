export type UserRole = "customer" | "admin";

export interface User {
  id: string;
  full_name: string;
  phone_number: string;
  email: string;
  role: UserRole;
  business_name: string | null;
  business_type: string | null;
  is_verified: boolean;
  is_active: boolean;
}

export interface Address {
  id: string;
  label: string;
  street: string;
  city: string;
  state: string;
  phone_number: string;
  is_default: boolean;
}

export interface Category {
  id: string;
  name: string;
  slug: string;
}

export interface Product {
  id: string;
  name: string;
  category_id: string;
  category: Category | null;
  description: string | null;
  unit: string;
  price: string;
  minimum_order_quantity: string;
  is_available: boolean;
  image_url: string | null;
  procurement_cycle_id: string | null;
}

export interface CartItem {
  id: string;
  product: Product;
  quantity: string;
  line_total: string;
}

export interface Cart {
  id: string;
  items: CartItem[];
  subtotal: string;
  delivery_fee: string;
  service_fee: string;
  total: string;
}

export type OrderStatus =
  | "PENDING_PAYMENT"
  | "PAID"
  | "CONFIRMED"
  | "AGGREGATING"
  | "PROCUREMENT"
  | "RECEIVED"
  | "PROCESSING"
  | "PACKAGED"
  | "DISPATCHED"
  | "DELIVERED"
  | "CANCELLED"
  | "REFUNDED"
  | "PARTIALLY_FULFILLED"
  | "FAILED_DELIVERY";

export interface OrderItem {
  id: string;
  product_id: string;
  product_name: string;
  quantity: string;
  unit_price: string;
  line_total: string;
  procurement_cycle_id: string;
}

export interface OrderStatusHistoryEntry {
  status: OrderStatus;
  note: string | null;
  created_at: string;
}

export interface Order {
  id: string;
  order_number: string;
  status: OrderStatus;
  subtotal: string;
  delivery_fee: string;
  service_fee: string;
  total: string;
  created_at: string;
  items: OrderItem[];
}

export interface OrderDetail extends Order {
  status_history: OrderStatusHistoryEntry[];
}

export interface CustomerSummary {
  id: string;
  full_name: string;
  email: string;
  phone_number: string;
  business_name: string | null;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
}

export interface CustomerDetail extends CustomerSummary {
  addresses: Address[];
  orders: Order[];
}

export type CycleStatus = "draft" | "open" | "closed" | "completed";

export interface ProcurementCycle {
  id: string;
  name: string;
  category_id: string | null;
  order_window_opens_at: string;
  order_window_closes_at: string;
  status: CycleStatus;
}

export interface AggregationLine {
  product_id: string;
  product_name: string;
  unit: string;
  total_quantity: string;
}

export interface AggregationReport {
  cycle_id: string;
  cycle_name: string;
  lines: AggregationLine[];
}

export interface AnalyticsSummary {
  customers: number;
  products: number;
  orders: number;
  orders_awaiting_payment: number;
  active_procurement_cycles: number;
  gmv: string;
}
