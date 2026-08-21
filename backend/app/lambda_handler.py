"""API Lambda entrypoint: API Gateway HTTP API (payload format 2.0) -> ASGI.

Deployed by infra/terraform/lambda.tf as the `-api` function's image command.
"""

import asyncio

from mangum import Mangum

from app.main import app

# Mangum resolves the event loop when the adapter is constructed and reuses it
# for every invocation, so it must exist at import time. Python 3.12 would
# auto-create one here (with a DeprecationWarning) and 3.14 raises instead;
# creating it explicitly keeps this working on any base image, and is also what
# keeps the loop alive across warm invocations.
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

# lifespan="off" is deliberate, not a shortcut: Mangum runs the *whole* ASGI
# lifespan (startup + shutdown) on every single invocation, not once per cold
# start. app.main's lifespan does no work - the DB engine and boto3 clients are
# module-level and lazily built - so running it per request buys nothing and
# costs a task spawn plus two run_until_complete calls on every request.
handler = Mangum(app, lifespan="off")
