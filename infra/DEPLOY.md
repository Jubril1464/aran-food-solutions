# Deploying Agric to AWS (serverless / Lambda)

Terraform for a fresh AWS account, built for one goal: **as close to zero
recurring cost as possible**, to run a pitch demo, not real production
traffic. Four Lambda functions sharing one zip artifact and one dependency
layer — API, notification worker, and two manually-invoked task runners
(migrations, first-run bootstrap) — with an API Gateway HTTP API in front of the
API function, SQS in front of the worker, RDS Postgres, and S3 + CloudFront for
the static frontend.

**Packaged as zip, not a container image.** Terraform uploads the artifacts
itself, so there is no ECR repository, no `docker login`, and no ordering
problem where the registry must exist before the functions do — one `apply`
creates everything. Building needs only Python, which matters on Windows where
Docker Desktop is a heavyweight prerequisite for what is really just a pip
download. Zip functions also cold-start faster than image-based ones.

| Function | Entrypoint | Triggered by |
|---|---|---|
| `agric-prod-api` | `app.lambda_handler.handler` (Mangum → FastAPI) | API Gateway, every HTTP request |
| `agric-prod-worker` | `app.notification_worker_handler.handler` | SQS event source mapping |
| `agric-prod-migrate` | `app.migration_handler.handler` (`alembic upgrade head`) | manual invoke, as a deploy step |
| `agric-prod-seed` | `app.seed_handler.handler` (first admin + starter catalogue) | manual invoke, once after the first deploy |

There is no always-on compute: all four scale to zero and cost nothing
between requests.

**This has not been applied.** Everything below is written and syntax-checked
(`terraform validate` passes), but provisioning real AWS resources is your
call to make from your own machine with your own credentials.

## The trade-off this design makes, explicitly

To avoid a NAT Gateway's fixed ~$32/mo cost, **RDS is publicly reachable on
the internet** (Lambda has no VPC attachment and therefore no stable outbound
IP to scope a security group to, so "Lambda-only access" isn't achievable
without a NAT gateway or RDS Proxy — both of which cost money continuously).
This is mitigated by:
- A random 32-character generated password (never checked into git).
- `rds.force_ssl = 1` on the DB parameter group — the server itself rejects
  any unencrypted connection, not just a client that opts into SSL.

It is **not** mitigated by verified TLS (the connection is encrypted, but the
client doesn't verify the server's certificate — that would need
`sslmode=verify-full` plus bundling the RDS CA certificate, skipped here to
keep this simple). Don't put real customer PII or payment data in this
database as deployed; it's built for a demo.

## Prerequisites

- An AWS account + IAM credentials with permissions for VPC, RDS, Lambda,
  API Gateway, SQS, S3, CloudFront, IAM (configured via `aws configure`
  or environment variables).
- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.7.
- [AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html).
- Python 3.9+ **of any version, on any OS**, to run the packaging script. It
  fetches Linux wheels for the target runtime rather than reusing whatever is
  installed locally, so the version you build with doesn't have to match the
  version Lambda runs.
- Node.js + npm, for the frontend build.
- **No Docker.** Nothing in this deployment path builds or runs a container.
  (`docker-compose.yml` is still there for local development, and still needs
  Docker — but it has nothing to do with deploying.)

## First deploy, in order

Run everything from the repo root unless a step says otherwise.

### 1. Bootstrap the Terraform state backend (once, ever)

```bash
cd infra/bootstrap
terraform init
terraform apply
```

Note the two outputs (`state_bucket_name`, `lock_table_name`).

### 2. Initialize the main config against that remote state

```bash
cd ../terraform
terraform init \
  -backend-config="bucket=<state_bucket_name>" \
  -backend-config="dynamodb_table=<lock_table_name>" \
  -backend-config="region=<your aws_region>"
```

### 3. Build the deployment artifacts

```bash
cd ../..
python infra/scripts/build-lambda-package.py
```

Writes `infra/build/layer.zip` (~12 MB of dependencies, shared by all four
functions) and `infra/build/app.zip` (~100 KB of application code). Both are
byte-reproducible: rebuilding without changing anything produces an identical
file, so Terraform won't redeploy functions that haven't changed.

The script downloads **Linux** wheels for CPython 3.12 regardless of the OS
you run it on, and refuses to build anything from source — a source build would
produce binaries for your machine that fail on Lambda with a bare "invalid ELF
header". It also fails loudly if any host binary (`.exe`, `.pyd`, `.dylib`)
ends up in the tree.

### 4. Apply everything

```bash
cd infra/terraform
terraform apply
```

Creates the VPC (public subnets only, no NAT), RDS, the dependency layer, all
four Lambda functions, SQS + DLQ, API Gateway, and the frontend S3/CloudFront.
Takes a few minutes — RDS is the slow part. If it complains that
`infra/build/layer.zip` doesn't exist, step 3 hasn't been run: that's deliberate,
so a deploy can never silently ship a stale artifact. Pass `-var paystack_secret_key=...` etc. now if
you have real values, or edit `terraform.tfvars` (copy from
`terraform.tfvars.example` — never commit the real file).

> If apply fails with a Lambda concurrency error
> (`InvalidParameterValueException: ... reserved concurrent executions`), the
> account's per-region concurrency limit is below
> `lambda_api_reserved_concurrency` (default 20). Re-apply with
> `-var lambda_api_reserved_concurrency=-1` to skip the reservation, and read
> the note under [Database connections](#database-connections-and-concurrency).

### 5. Run database migrations

```bash
cd ../..
infra/scripts/run-migrations.sh
```

Invokes the migration Lambda, which runs `alembic upgrade head` from the same
artifact and dependency layer the API runs — so migrations execute against the
deployed dependency set, not whatever Python is on your machine. The script surfaces the
function's log tail and fails loudly if the migration raised (a Lambda
invocation that ends in an exception is still an HTTP 200, so exit status alone
would report a failed migration as a success).

`infra/scripts/run-migrations.sh --local` is the fallback: it runs Alembic on
your machine against the public RDS endpoint (see
[the trade-off](#the-trade-off-this-design-makes-explicitly) above). Useful
while iterating on a revision you haven't packaged and deployed yet.

### 6. Create the first admin (and starter data)

```bash
aws lambda invoke   --function-name "$(terraform -chdir=infra/terraform output -raw seed_function_name)"   seed-result.json
cat seed-result.json
```

(Write to a real file rather than `/dev/stdout`: on Windows under Git Bash, MSYS
rewrites `/dev/stdout` into a Windows path before the AWS CLI ever sees it, and
the invoke fails on a path that doesn't exist.)

**This step is not optional if you want a usable site.** `/auth/register`
deliberately only ever creates *customers* — there is no self-service route to
an admin account — so until this runs there is no administrator, and therefore
no way to create categories, products or a procurement cycle. It also seeds a
starter catalogue and opens one procurement cycle per category (set
`-var seed_demo_data=false` to skip that and start empty).

Then read the login it created:

```bash
terraform -chdir=infra/terraform output -raw admin_email
terraform -chdir=infra/terraform output -raw admin_password
```

The password is generated unless you set `-var admin_password=...`, and is
passed to the function as an environment variable rather than in the invoke
payload, so it never lands in your shell history.

The function is idempotent — re-invoking promotes/repairs instead of
duplicating, and **extends an expired order window**, which is how you revive a
demo environment weeks later without touching the database. Pass
`--payload '{"reset_password": true}'` (with
`--cli-binary-format raw-in-base64-out`) if you lose the admin password and
want it reset to the current Terraform value.

### 7. Deploy the frontend

```bash
infra/scripts/deploy-frontend.sh
```

### 8. Open it

```bash
terraform -chdir=infra/terraform output frontend_url
```

## Ongoing deploys

- **Backend/worker code change**: `python infra/scripts/build-lambda-package.py --app-only`
  → `terraform apply` → `infra/scripts/run-migrations.sh` if the change includes
  a new Alembic revision. `--app-only` skips re-downloading the dependency tree,
  which is correct whenever no pin changed; drop it after editing
  `requirements-lambda.txt`. All four functions share the artifact and move
  together, so the task runners are never behind the API.
- **Frontend change**: `infra/scripts/deploy-frontend.sh`.
- **Infra change**: edit the `.tf` files, `terraform plan`, review, `terraform apply`.

## What running on Lambda changes about the app

Serverless isn't only a packaging choice — these are the places the
application code has to know it's on Lambda, and why:

### Database connections and concurrency

Lambda hands each invocation a fresh event loop, so a pooled asyncpg
connection carried over from a previous invocation fails with "Future attached
to a different loop". `app/core/database.py` therefore switches to SQLAlchemy's
`NullPool` when `AWS_LAMBDA_FUNCTION_NAME` is set: **one new Postgres
connection per invocation**, closed at the end.

That makes concurrency the connection limit. `db.t4g.micro` allows roughly 110
connections, so the API function is capped with
`reserved_concurrent_executions` (`lambda_api_reserved_concurrency`, default
20) and the worker's event source mapping with `maximum_concurrency`
(`worker_max_concurrency`, default 5). Without those caps a retry storm would
scale to the account's whole concurrency limit and exhaust the database
instead of queueing. If you raise either, raise the instance class too.
(RDS Proxy would remove the trade-off entirely, at roughly $15/month — not
provisioned here, for the same zero-cost reason as everything else.)

### The refresh-token cookie is cross-site

The frontend is served from CloudFront and the API from API Gateway — different
registrable domains, so every API call is cross-site and a `SameSite=Lax`
cookie is never sent. The refresh cookie would be silently dropped and silent
token refresh would 401 forever. Terraform sets `REFRESH_COOKIE_SAMESITE=none`
on the API function for this; the app forces `Secure` alongside it, since
browsers reject `SameSite=None` without it. Local dev keeps `lax` (same
origin, and `Secure` wouldn't work over plain HTTP).

### Uploads go to S3, and are size-capped

The Lambda filesystem is read-only apart from `/tmp` and is discarded with the
execution environment, so `STORAGE_BACKEND=s3` is set and the local
static-file mount is skipped entirely. Uploads are also capped at
`MAX_UPLOAD_SIZE_MB` (4 MB): Lambda's synchronous payload limit is 6 MB and
the body arrives base64-encoded, so anything larger dies at the gateway with
an opaque error before the app ever sees it — better to reject it ourselves
with a real message.

`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` are **injected by the Lambda
runtime** with the execution role's temporary credentials, so the app's own
S3 credential settings are deliberately named `S3_ACCESS_KEY_ID` /
`S3_SECRET_ACCESS_KEY`. Naming them after the AWS variables would capture the
role's key and secret without its session token, and every upload would fail
authentication. Leave them blank on AWS and let boto3 resolve the role.

boto3 itself is **not** in the dependency layer — the Lambda runtime already
ships it, and bundling botocore's service definitions would add ~90 MB unzipped
for nothing. The trade-off is that the version is AWS's choice, not ours; the
two calls made here (`sqs:SendMessage`, `s3:PutObject`) are as stable as the SDK
gets. Add `boto3` to `backend/requirements-lambda.txt` if that ever stops being
true.

### Notification delivery is at-least-once

The API function is the producer (`sqs:SendMessage`, granted in `iam.tf`) and
the worker the consumer. The worker reports **partial batch failures**
(`ReportBatchItemFailures`), so one bad message in a batch doesn't make SQS
redeliver — and re-send — the messages that already succeeded. A failed send
is reported for redelivery rather than swallowed, and reaches the DLQ after
`maxReceiveCount` (3) attempts; delivery is idempotent, so a duplicate is a
no-op. Notifications are enqueued on flush, inside the request transaction, so
a worker can occasionally beat the commit — that's treated as retryable, not
as a message to discard.

### Rate limiting is per execution environment

slowapi stores counters in process memory, so limits apply per warm Lambda
container rather than globally. It still stops a single client hammering an
endpoint, but a burst spread across cold starts can exceed the nominal limit.
A shared counter needs Redis/ElastiCache, deliberately not provisioned.

### Cold starts

A zip function's first invocation after idle is dominated by Python import time
plus the first TLS handshake to Postgres — noticeably cheaper than the container
image this replaced, which also had to pull and unpack an image. Provisioned
concurrency would remove the rest and costs money continuously, so it's off. For
a pitch demo, hit the API once before you present.

## Cost

AWS's Free Tier terms depend on **when your account was created** — check
your own account's Billing → Free Tier page rather than trust a number here.
Two honest estimates:

| Scenario | ~Monthly cost |
|---|---|
| **With RDS Free Tier active** (new-enough account, `db.t4g.micro`, single-AZ, 20GB) | **~$0–2** — Lambda (1M free requests/mo, permanent), SQS (1M free/mo, permanent), API Gateway HTTP API (1M free/mo for 12 months), S3 + CloudFront (near-free at demo traffic) all round to ~$0; RDS itself is the only line item and it's free |
| **Without RDS Free Tier** (older/expired, or your account's model doesn't include it) | **~$12–15** — RDS `db.t4g.micro` is the entire baseline; everything else stays effectively free at demo volume |

There is **no NAT Gateway, no ALB, no ElastiCache, and no always-on compute**
in this design (Lambda scales to zero) — RDS is the only resource with a
real always-on cost, which is exactly why the public-RDS trade-off above is
worth it for this use case.

If you want to go even cheaper/simpler than AWS RDS long-term, an external
managed Postgres with a permanent free tier (e.g. Neon, Supabase) is worth
considering as a drop-in `DATABASE_URL` swap — not implemented here, since
"stay on AWS" was the starting brief, but worth knowing about.

## Tearing it down

```bash
cd infra/terraform
terraform destroy
```

`skip_final_snapshot` is tied to `db_deletion_protection` (off by default),
so this does not leave an RDS snapshot behind — take one manually first if
you want the data back. The state bucket/lock table from `infra/bootstrap`
are `prevent_destroy`-protected and unaffected.

## Local development is unchanged

None of this touches `docker-compose.yml` — Postgres, Redis, the FastAPI
backend, the arq worker, and the Vite dev server all still run locally
exactly as before. This Lambda/SQS path only activates when `QUEUE_BACKEND=sqs`
is set (which only happens via the Terraform-managed Lambda environment
variables); the default (`redis`) is what local dev and the test suite use.
