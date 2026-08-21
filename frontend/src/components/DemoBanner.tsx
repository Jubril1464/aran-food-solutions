import { DEMO_MODE, resetDemoData } from "../api/demo";

/**
 * A small, honest marker that this build runs on sample data.
 *
 * Worth having during a client walkthrough: it prevents "is this live?" from
 * being an unanswered question, and gives you a way to put the data back after
 * someone has clicked through a checkout. Renders nothing at all when
 * VITE_DEMO_MODE isn't set, so it costs the real build nothing.
 */
export function DemoBanner() {
  if (!DEMO_MODE) return null;

  const handleReset = () => {
    resetDemoData();
    window.location.reload();
  };

  return (
    <div className="border-b border-amber-200 bg-amber-50">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 px-4 py-2">
        <p className="text-xs text-amber-800">
          <span className="font-semibold uppercase tracking-wide">Demo</span> — sample data, running entirely in your
          browser. Orders and changes are saved locally and affect nothing real.
        </p>
        <button
          onClick={handleReset}
          className="rounded border border-amber-300 bg-white px-2 py-1 text-xs font-medium text-amber-800 hover:bg-amber-100"
        >
          Reset demo data
        </button>
      </div>
    </div>
  );
}
