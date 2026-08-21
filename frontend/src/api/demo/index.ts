/**
 * Demo mode: serve the whole API from the browser, with no backend at all.
 *
 * Enabled by `VITE_DEMO_MODE=true` at build time. When off, none of this runs
 * and the app talks to the real API exactly as before — so this is a switch, not
 * a fork of the codebase.
 *
 * State is persisted to localStorage so a reload keeps your cart, your orders
 * and your session. That makes a demo feel like a real product rather than
 * something that resets under the client's hands.
 */

import { handleDemoRequest, type DemoResponse } from "./backend";
import { createDemoState, DEMO_CREDENTIALS, type DemoState } from "./seed";

export const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === "true";
export { DEMO_CREDENTIALS };

// Bump when the shape of DemoState changes, so a returning visitor with older
// data in localStorage gets a clean, working dataset instead of a broken screen.
const STORAGE_KEY = "aran-demo-state-v1";

let state: DemoState | null = null;

function load(): DemoState {
  if (state) return state;
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      state = JSON.parse(saved) as DemoState;
      return state;
    }
  } catch {
    // Corrupt or unavailable storage (private browsing, quota) is not worth
    // failing over: fall through and start from the seed.
  }
  state = createDemoState();
  save();
  return state;
}

function save() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Storage full or blocked. The demo still works for this page view.
  }
}

/** Wipe the demo back to its seeded state. Exposed in the demo banner. */
export function resetDemoData() {
  state = createDemoState();
  save();
}

/**
 * Product image uploads: turn the chosen file into a data URL so the image
 * actually appears. Persisted with everything else, so it survives a reload —
 * an object URL would not.
 */
function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

export interface DemoCallOptions {
  method: string;
  path: string;
  body?: unknown;
  token: string | null;
}

/** A small, believable delay so the UI's loading states are visible. */
const LATENCY_MS = 180;

export async function callDemoBackend(options: DemoCallOptions): Promise<DemoResponse> {
  const current = load();
  await new Promise((resolve) => setTimeout(resolve, LATENCY_MS));

  // Image upload arrives as FormData, which the pure router doesn't handle.
  if (options.body instanceof FormData) {
    const match = /^\/admin\/products\/([^/]+)\/image$/.exec(options.path);
    const file = options.body.get("file");
    if (match && file instanceof File) {
      const product = current.products.find((p) => p.id === match[1]);
      if (!product) return { status: 404, body: { detail: "Product not found" } };
      const maxBytes = 4 * 1024 * 1024;
      if (file.size > maxBytes) {
        return {
          status: 413,
          body: { detail: `Image is too large (${(file.size / 1024 / 1024).toFixed(1)} MB); the limit is 4 MB.` },
        };
      }
      product.image_url = await readFileAsDataUrl(file);
      save();
      return { status: 200, body: product };
    }
    return { status: 400, body: { detail: "Unsupported upload in demo mode" } };
  }

  const response = handleDemoRequest(current, {
    method: options.method,
    path: options.path,
    body: options.body,
    token: options.token,
  });
  save();
  return response;
}
