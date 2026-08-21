export function formatNaira(value: string | number): string {
  const n = typeof value === "string" ? parseFloat(value) : value;
  return new Intl.NumberFormat("en-NG", { style: "currency", currency: "NGN" }).format(n);
}

export function formatDate(value: string): string {
  return new Date(value).toLocaleString("en-NG", { dateStyle: "medium", timeStyle: "short" });
}

export const STATUS_LABELS: Record<string, string> = {
  PENDING_PAYMENT: "Awaiting payment",
  PAID: "Paid",
  CONFIRMED: "Confirmed",
  AGGREGATING: "Aggregating demand",
  PROCUREMENT: "Procurement in progress",
  RECEIVED: "Goods received",
  PROCESSING: "Processing",
  PACKAGED: "Packaged",
  DISPATCHED: "Dispatched",
  DELIVERED: "Delivered",
  CANCELLED: "Cancelled",
  REFUNDED: "Refunded",
  PARTIALLY_FULFILLED: "Partially fulfilled",
  FAILED_DELIVERY: "Delivery failed",
};

export const STATUS_COLORS: Record<string, string> = {
  PENDING_PAYMENT: "bg-amber-100 text-amber-800",
  PAID: "bg-blue-100 text-blue-800",
  CONFIRMED: "bg-blue-100 text-blue-800",
  AGGREGATING: "bg-purple-100 text-purple-800",
  PROCUREMENT: "bg-purple-100 text-purple-800",
  RECEIVED: "bg-teal-100 text-teal-800",
  PROCESSING: "bg-teal-100 text-teal-800",
  PACKAGED: "bg-teal-100 text-teal-800",
  DISPATCHED: "bg-indigo-100 text-indigo-800",
  DELIVERED: "bg-brand-100 text-brand-700",
  CANCELLED: "bg-stone-200 text-stone-700",
  REFUNDED: "bg-stone-200 text-stone-700",
  PARTIALLY_FULFILLED: "bg-orange-100 text-orange-800",
  FAILED_DELIVERY: "bg-red-100 text-red-800",
};
