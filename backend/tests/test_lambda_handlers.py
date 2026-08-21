"""Regression tests for the three AWS Lambda entrypoints.

These run in a **subprocess**, not in-process, and that's deliberate: the
behaviour under test is decided at import time from the environment Lambda
provides (AWS_LAMBDA_FUNCTION_NAME, the injected AWS_* credentials,
QUEUE_BACKEND=sqs), and `get_settings()` plus the SQLAlchemy engine are
module-level singletons. A fresh process is also the honest simulation of a
Lambda cold start, and re-invoking the handler in that same process is the
honest simulation of a warm one - which is where the loop/pooling bugs live.

Everything is real except the SQS wire call: the notification ids the worker
consumes are the ids the API function actually enqueued.

Covered here (and nowhere else in the suite):
  * Mangum translating API Gateway HTTP API v2 events, cold and warm
  * the refresh cookie being usable cross-site (CloudFront -> API Gateway)
  * Lambda's injected AWS credentials not shadowing the S3 client's
  * NullPool on Lambda, and the local StaticFiles mount being skipped
  * SQS partial batch failures: a bad message must not re-send a good one
  * a failed send being reported for retry rather than silently dropped
"""

import json
import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]

# Runs inside the subprocess. Self-asserting: a non-zero exit fails the test,
# and its stdout is attached to the failure for diagnosis.
LAMBDA_SCENARIO = r'''
import json, uuid, asyncio

# 1. Schema, via the migration function's entrypoint.
from app.migration_handler import handler as migrate_handler
assert migrate_handler({}, None)["status"] == "ok"

# Alembic's asyncio.run() clears the thread's event loop on exit. Importing the
# API handler only afterwards is the harsher ordering, so that's what we do.
from app.lambda_handler import handler as api_handler
from app.notification_worker_handler import handler as worker_handler

import app.core.queue as queue_module

assert isinstance(queue_module.get_notification_queue(), queue_module.SqsNotificationQueue)

SENT = []


class FakeSqs:
    """Stands in for the SQS wire call only; both sides of it are the real code."""

    def send_message(self, QueueUrl, MessageBody):
        assert QueueUrl.startswith("https://sqs."), QueueUrl
        SENT.append(MessageBody)
        return {"MessageId": "msg-%d" % len(SENT)}


queue_module._sqs_client = lambda: FakeSqs()


class Ctx:
    function_name = "agric-test-api"
    memory_limit_in_mb = 512
    invoked_function_arn = "arn:aws:lambda:eu-west-1:123456789012:function:agric-test-api"
    aws_request_id = "req-1"


def event(method, path, body=None, cookies=None, token=None):
    headers = {"content-type": "application/json", "origin": "https://example.cloudfront.net"}
    if token:
        headers["authorization"] = "Bearer " + token
    e = {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": path,
        "rawQueryString": "",
        "headers": headers,
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "abc123",
            "domainName": "abc123.execute-api.eu-west-1.amazonaws.com",
            "http": {"method": method, "path": path, "protocol": "HTTP/1.1",
                     "sourceIp": "203.0.113.7", "userAgent": "pytest"},
            "requestId": "req-1", "routeKey": "$default", "stage": "$default",
            "timeEpoch": 1700000000000,
        },
        "isBase64Encoded": False,
    }
    if cookies:
        e["cookies"] = cookies
    if body is not None:
        e["body"] = json.dumps(body)
    return e


def call(label, ev, expect):
    r = api_handler(ev, Ctx())
    assert r["statusCode"] == expect, "%s -> %s %s" % (label, r["statusCode"], r.get("body"))
    print("ok:", label)
    return r


# 2. Cold invocation, then warm ones - including a DB query on a warm
#    invocation, which is what breaks if a pooled connection outlives its loop.
call("cold GET /health", event("GET", "/health"), 200)
call("warm GET /health", event("GET", "/health"), 200)
call("warm GET /api/v1/products (db on warm invocation)", event("GET", "/api/v1/products"), 200)

# 3. A request that enqueues a notification must reach SQS.
call("POST /api/v1/auth/register", event("POST", "/api/v1/auth/register", {
    "full_name": "Lambda Test", "email": "lambda@agric-mvp-test.com",
    "phone_number": "+2348012345678", "password": "supersecret123",
    "street": "12 Market Road", "city": "Ibadan", "state": "Oyo",
}), 201)
assert len(SENT) == 1, SENT

# 4. The refresh cookie has to survive a cross-site request: the deployed
#    frontend (CloudFront) and API (API Gateway) are different sites, so a
#    SameSite=Lax cookie would never be sent back and refresh would always 401.
r = call("POST /api/v1/auth/login", event("POST", "/api/v1/auth/login",
         {"email": "lambda@agric-mvp-test.com", "password": "supersecret123"}), 200)
set_cookie = (r.get("cookies") or [r["headers"].get("set-cookie", "")])[0]
assert "samesite=none" in set_cookie.lower(), set_cookie
assert "Secure" in set_cookie, set_cookie
assert "HttpOnly" in set_cookie, set_cookie
assert "Path=/api/v1/auth" in set_cookie, set_cookie

token = json.loads(r["body"])["access_token"]
call("GET /api/v1/auth/me", event("GET", "/api/v1/auth/me", token=token), 200)
call("POST /api/v1/auth/refresh", event("POST", "/api/v1/auth/refresh",
     cookies=[set_cookie.split(";")[0]]), 200)

# 5. Lambda injects AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN
#    for the execution role. Settings fields named after the first two would
#    silently capture them and hand boto3 a key+secret with no session token,
#    which AWS rejects - so uploads must resolve the role through boto3 instead.
from app.core.config import get_settings
from app.core.storage import get_storage_backend

assert get_settings().s3_access_key_id == "", get_settings().s3_access_key_id
backend = get_storage_backend()
creds = backend.client._request_signer._credentials
assert creds.token, "boto3 must resolve the role's session token"
assert get_storage_backend() is backend, "storage backend should be cached across requests"

# 6. Nothing may serve uploads off the (read-only, ephemeral) Lambda filesystem.
assert not [x for x in api_handler.app.routes if getattr(x, "name", "") == "uploads"]

# 7. NullPool: no connection may be reused across invocations/event loops.
from app.core.database import engine
assert type(engine.pool).__name__ == "NullPool", type(engine.pool).__name__

# 8. Partial batch failure: a message whose row can't be found must not take an
#    already-delivered message down with it (SQS would redeliver the whole batch
#    and re-send that notification).
missing_id = str(uuid.uuid4())
result = worker_handler({"Records": [
    {"messageId": "msg-real", "body": SENT[0]},
    {"messageId": "msg-missing", "body": missing_id},
]}, Ctx())
assert result == {"batchItemFailures": [{"itemIdentifier": "msg-missing"}]}, result

# Warm worker invocation, and a duplicate delivery of a sent notification.
assert worker_handler({"Records": [{"messageId": "again", "body": SENT[0]}]}, Ctx()) == {"batchItemFailures": []}

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.notification import Notification, NotificationStatus, NotificationType
from app.models.user import User


async def one_notification():
    async with AsyncSessionLocal() as db:
        n = (await db.execute(select(Notification))).scalars().one()
        return n.status, n.sent_at is not None


status, has_sent_at = asyncio.run(one_notification())
assert status == NotificationStatus.SENT and has_sent_at, (status, has_sent_at)

# 9. A failed delivery must be reported back so SQS retries it (and eventually
#    DLQs it) rather than being swallowed into a FAILED row nobody retries.
import app.modules.notifications.tasks as tasks


class ExplodingChannel:
    async def send(self, **kwargs):
        raise RuntimeError("smtp unavailable")


async def seed():
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User))).scalars().first()
        n = Notification(user_id=user.id, type=NotificationType.ORDER_CONFIRMED, channel="email",
                         payload={"full_name": user.full_name, "order_number": "AG-2", "cycle_name": "Cycle 1"})
        db.add(n)
        await db.commit()
        return str(n.id)


second_id = asyncio.run(seed())
original = tasks.get_email_channel
tasks.get_email_channel = lambda: ExplodingChannel()
try:
    result = worker_handler({"Records": [{"messageId": "smtp-down", "body": second_id}]}, Ctx())
finally:
    tasks.get_email_channel = original
assert result == {"batchItemFailures": [{"itemIdentifier": "smtp-down"}]}, result

# ...and the retry delivers once the channel recovers.
assert worker_handler({"Records": [{"messageId": "smtp-down", "body": second_id}]}, Ctx()) == {"batchItemFailures": []}


async def second_status():
    async with AsyncSessionLocal() as db:
        return (await db.execute(
            select(Notification).where(Notification.id == uuid.UUID(second_id))
        )).scalar_one().status


assert asyncio.run(second_status()) == NotificationStatus.SENT

print("LAMBDA_SCENARIO_OK")
'''


# The bootstrap step a fresh deployment cannot do without: /auth/register only
# ever creates customers, so without this there is no admin, and therefore no
# products, no categories and no open cycle for the customer flow to use.
SEED_SCENARIO = r'''
import json

from app.migration_handler import handler as migrate
from app.seed_handler import handler as seed

assert migrate({}, None)["status"] == "ok"

first = seed({}, None)
assert first["admin"] == "created", first
assert first["categories_created"] > 0 and first["products_created"] > 0, first
assert first["cycles_created"] == first["categories_created"], first

# Re-invoking must repair rather than duplicate - it's a step people re-run.
second = seed({}, None)
assert second["admin"] == "unchanged", second
assert (second["categories_created"], second["products_created"], second["cycles_created"]) == (0, 0, 0), second

from app.lambda_handler import handler as api
import app.core.queue as queue_module

queue_module._sqs_client = lambda: type("F", (), {"send_message": lambda self, **kw: {"MessageId": "m"}})()


class Ctx:
    aws_request_id = "r"
    function_name = "agric-test-seed"
    memory_limit_in_mb = 512
    invoked_function_arn = "arn"


def ev(method, path, body=None, token=None):
    headers = {"content-type": "application/json"}
    if token:
        headers["authorization"] = "Bearer " + token
    e = {
        "version": "2.0", "rawPath": path, "rawQueryString": "", "headers": headers, "routeKey": "$default",
        "requestContext": {"http": {"method": method, "path": path, "sourceIp": "1.2.3.4",
                                    "protocol": "HTTP/1.1", "userAgent": "pytest"},
                           "requestId": "r", "stage": "$default", "apiId": "a", "accountId": "1",
                           "domainName": "d", "routeKey": "$default", "timeEpoch": 1700000000000},
        "isBase64Encoded": False,
    }
    if body is not None:
        e["body"] = json.dumps(body)
    return e


def call(label, e, expect):
    r = api(e, Ctx())
    assert r["statusCode"] == expect, "%s -> %s %s" % (label, r["statusCode"], r.get("body"))
    return json.loads(r["body"]) if r["statusCode"] != 204 else None


# The seeded admin must actually be able to log in and reach an admin-only route.
login = call("admin login", ev("POST", "/api/v1/auth/login",
             {"email": "admin@agric-seed-test.com", "password": "seed-test-password-123"}), 200)
cycles = call("list cycles", ev("GET", "/api/v1/admin/procurement-cycles", token=login["access_token"]), 200)
assert cycles and all(c["status"] == "open" for c in cycles), cycles

# ...and a visitor must not land on an empty catalogue.
products = call("public catalogue", ev("GET", "/api/v1/products"), 200)
assert len(products) >= len(cycles), products
assert any(float(p["minimum_order_quantity"]) > 1 for p in products), "MOQ enforcement should be demoable"

print("SEED_SCENARIO_OK")
'''


def _lambda_env(tmp_path, db_name, extra=None):
    db_path = str(tmp_path / db_name).replace("\\", "/")
    env = {
        **os.environ,
        # The environment infra/terraform/lambda.tf actually sets, with Postgres
        # swapped for SQLite (same reason the rest of the suite does).
        "DATABASE_URL": f"sqlite+aiosqlite:///{db_path}",
        "AWS_LAMBDA_FUNCTION_NAME": "agric-test-api",
        "LAMBDA_TASK_ROOT": str(BACKEND_DIR),
        "ENVIRONMENT": "prod",
        "JWT_SECRET": "test-secret-key-for-pytest-only-not-for-prod-use",
        "PAYSTACK_SECRET_KEY": "",
        "QUEUE_BACKEND": "sqs",
        "SQS_NOTIFICATION_QUEUE_URL": "https://sqs.eu-west-1.amazonaws.com/123456789012/agric-test",
        "REFRESH_COOKIE_SAMESITE": "none",
        "STORAGE_BACKEND": "s3",
        "S3_BUCKET": "agric-test-uploads",
        "S3_REGION": "eu-west-1",
        "AWS_REGION": "eu-west-1",
        "CORS_ORIGINS": json.dumps(["https://example.cloudfront.net"]),
        # Stand-ins for what the Lambda runtime injects for the execution role.
        "AWS_ACCESS_KEY_ID": "ASIAEXAMPLEROLEKEY",
        "AWS_SECRET_ACCESS_KEY": "example-role-secret",
        "AWS_SESSION_TOKEN": "example-role-session-token",
        "PYTHONPATH": str(BACKEND_DIR),
        **(extra or {}),
    }
    # A real profile would make boto3 try to reach STS instead of reading the
    # fake "injected role" credentials above.
    env.pop("AWS_PROFILE", None)
    return env


def _run(env, tmp_path, scenario, marker):
    result = subprocess.run(
        [sys.executable, "-c", scenario],
        env=env,
        # Run from a scratch directory so the repo's own .env can't override the
        # environment under test: pydantic reads it relative to the cwd.
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert marker in result.stdout, (
        f"exit={result.returncode}\n--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr[-4000:]}"
    )


def test_lambda_entrypoints(tmp_path):
    _run(_lambda_env(tmp_path, "lambda_test.db"), tmp_path, LAMBDA_SCENARIO, "LAMBDA_SCENARIO_OK")


def test_seed_bootstrap(tmp_path):
    env = _lambda_env(tmp_path, "seed_test.db", {
        "AWS_LAMBDA_FUNCTION_NAME": "agric-test-seed",
        "SEED_ADMIN_EMAIL": "admin@agric-seed-test.com",
        "SEED_ADMIN_PASSWORD": "seed-test-password-123",
        "SEED_DEMO_DATA": "true",
    })
    _run(env, tmp_path, SEED_SCENARIO, "SEED_SCENARIO_OK")
