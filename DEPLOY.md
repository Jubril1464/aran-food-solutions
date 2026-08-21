# Deploying Aran Food Solutions

Two things live in this repo, and they deploy separately:

1. **The demo** — the frontend on its own, running on sample data. One free
   static host, no backend, no database, no credit card. This is what the steps
   below cover, and it is what you show a client.
2. **The full stack** — that same frontend against the real FastAPI backend and
   a Postgres database. Written, tested, and waiting on a database; see
   [Adding the real backend](#adding-the-real-backend).

## What demo mode actually is

`VITE_DEMO_MODE=true` makes the app serve its own API from
[`frontend/src/api/demo/`](frontend/src/api/demo/) — sample data held in the
browser's localStorage. It is not a set of static screenshots: the real rules
run, so a walkthrough behaves like the product.

- The catalogue is the same 9 products, 4 categories and 4 open procurement
  cycles the real backend seeds.
- **Minimum order quantities are enforced** — try adding one bag of Yellow Maize.
- Checkout resolves an open procurement cycle per line, exactly as the backend
  does, and refuses if there isn't one.
- Payment goes through the mock Paystack page and moves the order
  `PENDING_PAYMENT → PAID → CONFIRMED`; replaying it doesn't double-apply.
- Closing a procurement cycle aggregates demand and advances the orders in it.
- Admin screens are populated: 4 customers, 6 orders in various states, working
  search, product create/edit/delete, and image upload.
- Registering a new account works, including its delivery address.

Two demo logins, offered as buttons on the sign-in page so you don't have to
type them in front of anyone:

| Role | Email | Password |
|---|---|---|
| Administrator | `admin@aranfood.example` | `demo-admin` |
| Customer | `buyer@aranfood.example` | `demo-buyer` |

Changes persist across reloads, and **Reset demo data** in the amber banner puts
everything back — useful between walkthroughs.

## Step 1 — Push to GitHub (5 min)

```bash
cd /c/Users/lukma/agric
git add -A
git commit -m "Demo build"
```

Create an empty repository at [github.com/new](https://github.com/new) — name it
`aran-food-solutions`, no README or .gitignore — then:

```bash
git remote add origin https://github.com/<your-username>/aran-food-solutions.git
git push -u origin main
```

A browser window opens for GitHub sign-in; approve it and the push completes.

## Step 2 — Deploy (5 min)

Either host works, both free, neither needs a card. Pick one.

### Option A — Vercel (best if you already have an account)

1. [vercel.com/new](https://vercel.com/new) → import your repository.
2. Set **Root Directory** to `frontend`. That is the only setting to change:
   [`frontend/vercel.json`](frontend/vercel.json) already supplies the build
   command, the SPA rewrite, and `VITE_DEMO_MODE=true`.
3. **Deploy.** ~2 minutes, then you get a `*.vercel.app` URL.

### Option B — Render

1. [render.com](https://render.com) → sign in with GitHub → **New → Blueprint**.
2. Pick the repository. Render reads [`render.yaml`](render.yaml) and offers to
   create `aran-food-web`.
3. **Apply.** It asks for nothing — demo mode needs no configuration. ~2 minutes,
   then you get an `*.onrender.com` URL.

Static sites don't sleep on either host, so there is no cold start to warm up
before a meeting.

## Step 3 — Check it before you show anyone (5 min)

| # | Do this | Expect |
|---|---|---|
| 1 | Open the URL | Amber demo banner, catalogue of **9 products** |
| 2 | Sign in → **Administrator** button → Log in | Dashboard with 4 customers, 6 orders, GMV |
| 3 | Admin → Procurement Cycles | **4 open** cycles; open one to see aggregated demand |
| 4 | Sign out, sign in as **Customer** | Order history with 2 past orders |
| 5 | Add **1** bag of Yellow Maize | Rejected: "Minimum order quantity … is 2.00 bag" |
| 6 | Add 2 bags → Cart → Checkout → Simulate payment | Order reaches **CONFIRMED** |
| 7 | Reload the page | Still signed in, order still there |

If step 7 fails, the browser is blocking localStorage (private browsing) — the
app still works, it just won't remember anything between reloads.

## Turning the demo banner off

It is one line: delete `<DemoBanner />` from
[`frontend/src/App.tsx`](frontend/src/App.tsx), commit, push. I would leave it —
being straight about "this is sample data" is usually worth more in a client
meeting than the polish of hiding it.

## Adding the real backend

Nothing about demo mode is throwaway: it is a switch, not a fork. The backend,
its migrations, its bootstrap and its tests are all still here and passing.

When you have a Postgres database (Neon, Supabase, Railway, or a Render Postgres
if a 30-day database is acceptable):

1. `mv render.backend.yaml render.yaml` — the full-stack blueprint, which adds
   the FastAPI web service alongside the static site.
2. Set `DATABASE_URL` on the API service to the provider's connection string,
   pasted verbatim. The app rewrites it for its async driver, strips the
   libpq-only parameters asyncpg rejects, and detects a pgbouncer pooler
   endpoint.
3. Set `VITE_DEMO_MODE=false` and `VITE_API_BASE_URL=<api URL>/api/v1` on the
   static site, plus `CORS_ORIGINS` and `FRONTEND_URL` on the API.
4. Redeploy both. `backend/start.sh` migrates and creates the admin on boot, so
   there is no release command to run by hand.

Neon may tell you to create projects through its Vercel integration. Either use
that integration — it provisions the database and sets `DATABASE_URL` in your
Vercel project for you — or use Supabase, whose free Postgres has no such
restriction and needs no card.

## Running it locally

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173
```

`frontend/.env` sets `VITE_DEMO_MODE=true`, so this runs on sample data with no
backend. Set it to `false` to point at a local API instead — see
[README.md](README.md#running-it).
