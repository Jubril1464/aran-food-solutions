# Deploying Agric (Render + Neon)

The whole app runs on **two free Render services and one free Neon Postgres**.
No Docker, no container registry, no credit card, and nothing to install beyond
a browser and git.

| Piece | Where | Why |
|---|---|---|
| API (FastAPI) | Render **web service**, native Python | Runs `pip install` and `uvicorn` directly from this repo |
| Frontend (React) | Render **static site** | Builds with `npm run build`, served as plain files |
| Database | **Neon** Postgres | Free tier is *permanent*; Render's free Postgres is deleted 30 days after creation |
| Notifications | A background task inside the API process | No Redis and no second service, so it fits on one free instance |

Everything is declared in [`render.yaml`](render.yaml), so Render creates both
services from this file rather than from a pile of dashboard clicking.

## Read this before you start

Three honest limitations of the free tier. None of them stop a demo; all of them
would matter for real traffic:

- **The API sleeps.** A free Render service spins down after ~15 minutes of
  inactivity, and the next request takes roughly 30–60 seconds while it starts
  again. Open the site once a minute before you present. ($7/month removes it.)
- **Uploaded images are temporary.** Free instances have no persistent disk, so
  product images you upload disappear on the next deploy or restart. The seeded
  catalogue doesn't rely on images. Point `STORAGE_BACKEND` at any S3-compatible
  bucket (Supabase Storage, Backblaze B2, Cloudflare R2 — all have free tiers)
  to make them permanent.
- **The database sleeps too.** Neon suspends an idle project after 5 minutes;
  the first query afterwards takes an extra moment. The app expects this and
  recycles dead connections rather than failing (`app/core/database.py`).

## Step 1 — Push this repo to GitHub (5 min)

Render deploys from a git repository, so it needs one.

```bash
cd /c/Users/lukma/agric
git add -A
git commit -m "Deploy to Render"
```

Create an empty repository on GitHub (no README, no .gitignore), then:

```bash
git remote add origin https://github.com/<your-username>/agric.git
git branch -M main
git push -u origin main
```

`.gitignore` already excludes `backend/.env`, `frontend/.env`, `node_modules/`,
and `*.db`, so no secrets or junk go up. Make the repository **private** if you
prefer — Render works with both.

## Step 2 — Create the database on Neon (5 min)

1. Sign up at [neon.com](https://neon.com) — GitHub sign-in, no card.
2. Create a project. Name it `agric`, and pick a region near your users;
   **Europe (Frankfurt)** pairs well with the Render region used below.
3. On the project dashboard, copy the **connection string**. It looks like:

   ```
   postgresql://agric_owner:npg_xxxxxxxx@ep-cool-name-123456.eu-central-1.aws.neon.tech/agric?sslmode=require&channel_binding=require
   ```

Copy it **exactly as given**, including the `?sslmode=require&channel_binding=require`.
The app rewrites it for its async driver and strips the parameters asyncpg
doesn't accept — hand-editing it is the usual cause of a confusing
`connect() got an unexpected keyword argument 'sslmode'` on first boot.

## Step 3 — Create both services on Render (10 min)

1. Sign up at [render.com](https://render.com) with GitHub — no card for the
   free tier.
2. **New → Blueprint**, pick your `agric` repository. Render reads
   `render.yaml` and offers to create `agric-api` and `agric-web`.
3. It will ask for the values marked "sync: false". Fill in what you can now:

   | Variable | Service | Value |
   |---|---|---|
   | `DATABASE_URL` | agric-api | the Neon string from step 2 |
   | `PAYSTACK_SECRET_KEY` | agric-api | leave **blank** (runs Paystack in mock mode) |
   | `CORS_ORIGINS` | agric-api | `["https://agric-web.onrender.com"]` |
   | `FRONTEND_URL` | agric-api | `https://agric-web.onrender.com` |
   | `VITE_API_BASE_URL` | agric-web | `https://agric-api.onrender.com/api/v1` |

   The last three depend on the URLs Render is about to assign. If your service
   names got a suffix (because someone already has `agric-api`), use the real
   URLs from each service's page and correct these in step 5.
4. **Apply**. The API build takes ~3 minutes, the static site ~2.

## Step 4 — Get your admin password (1 min)

`start.sh` has already created the admin account and the starter catalogue on
first boot — you don't run anything.

Open **agric-api → Environment** and copy the generated `SEED_ADMIN_PASSWORD`.
Your login is:

- **Email:** `admin@agric.example` (or whatever you set `SEED_ADMIN_EMAIL` to)
- **Password:** the generated `SEED_ADMIN_PASSWORD`

Check **agric-api → Logs**. A healthy first boot reads:

```
==> Applying database migrations
INFO  [alembic.runtime.migration] Running upgrade  -> 4ee78057c86d, initial schema
==> Ensuring admin account and starter data exist
{"status": "ok", "admin": "created", "categories_created": 4, "products_created": 9, "cycles_created": 4, ...}
==> Starting API on port 10000
```

## Step 5 — Fix up the URLs, if you guessed any wrong (2 min)

Open each service, copy its real `onrender.com` URL, and make sure:

- `agric-api` → `CORS_ORIGINS` is `["<frontend URL>"]` and `FRONTEND_URL` is that
  same URL without the brackets.
- `agric-web` → `VITE_API_BASE_URL` is `<api URL>/api/v1`.

Changing `VITE_API_BASE_URL` needs a rebuild of the static site to take effect —
it's compiled into the bundle. Use **Manual Deploy → Deploy latest commit**.

## Step 6 — Check it works (10 min)

Open the frontend URL and run these in order. Each one exercises something that
breaks in a different place, so the order tells you *where* a problem is:

| # | Do this | Expect | Tells you |
|---|---|---|---|
| 1 | Load the home page | Catalogue with **9 products** | API reachable, database migrated and seeded |
| 2 | Log in as admin → Procurement Cycles | **4 open** cycles | Admin bootstrap worked |
| 3 | Register a customer | Succeeds; API log shows `email_sent_console` | Background notification delivery works |
| 4 | Add **1** bag of Yellow Maize | Rejected, "minimum order quantity … is 2" | Business rules live |
| 5 | Add 2 bags → checkout → pay on the mock page | Order reaches **CONFIRMED** | Cycle resolution + payment state machine |
| 6 | Hard-refresh while logged in | Still logged in | The cross-site refresh cookie |

Step 6 is the one people skip. It's the check that the `SameSite=none` cookie
survives the frontend and API being on different hostnames.

## Ongoing deploys

Push to `main`. Render rebuilds both services automatically. Migrations and the
seed step run again on every boot and are idempotent, so a schema change needs
no extra command — and re-running the seed also **extends an expired order
window**, which is how you revive this demo weeks later.

## If something fails

| Symptom | Cause | Fix |
|---|---|---|
| Build: `No matching distribution found` | `PYTHON_VERSION` changed to a version without wheels | Keep it at `3.12.11` |
| Boot: `unexpected keyword argument 'sslmode'` | `DATABASE_URL` was hand-edited into a shape the driver rejects | Paste Neon's string verbatim |
| Boot: `SEED_ADMIN_PASSWORD is not set; skipping bootstrap` | Blueprint didn't generate it | Set any strong value in the dashboard, then redeploy |
| Site loads, catalogue empty | Seed skipped (see above), or `SEED_DEMO_DATA` is `false` | Fix the variable, redeploy |
| Catalogue empty **and** browser console shows CORS errors | `CORS_ORIGINS` doesn't exactly match the frontend URL | Correct it (include `https://`, no trailing slash) |
| Login works, but refresh logs you out | `REFRESH_COOKIE_SAMESITE` isn't `none` | Set it, redeploy |
| First request takes ~40s | Free instance was asleep | Normal; warm it before demoing |
| `502` right after deploy | Service still starting | Wait for the log to show `Starting API on port` |

## Costs

$0/month, permanently, for everything above. The two things worth paying for
later, in order: Render's **Starter** web service ($7/month) to stop the API
sleeping, and Neon's paid tier only once 0.5 GB or 100 compute-hours a month
stops being enough — which, for a pitch demo, it won't be.

## Running it locally

Unchanged, and documented in [README.md](README.md#running-it). Local
development uses a real arq worker over Redis (`QUEUE_BACKEND=redis` in
`docker-compose.yml`) rather than in-process delivery, so both transports stay
exercised.
