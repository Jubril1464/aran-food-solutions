"""Migration Lambda entrypoint: runs `alembic upgrade head` inside the VPC-less
Lambda environment, using the same image as the API and worker functions.

Invoked manually as a deploy step, never on a schedule or a request path:

    aws lambda invoke --function-name agric-prod-migrate /dev/stdout

Why a Lambda rather than only the local script (infra/scripts/run-migrations.sh):
the local path needs a Python 3.12 venv, the backend's dependencies, and direct
network access to the database from the operator's machine. Running it here uses
the exact image and dependency set the application itself runs with, which is
the difference between "migrations passed on my laptop" and "migrations passed
against what is deployed".
"""

import os

from alembic import command
from alembic.config import Config

from app.core.logging import configure_logging, logger

# Alembic resolves script_location relative to the process's working directory,
# which on Lambda is /var/task (where the deployment artifact puts alembic.ini
# and alembic/ - see infra/scripts/build-lambda-package.py), not wherever the
# caller happened to be.
_TASK_ROOT = os.environ.get("LAMBDA_TASK_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def handler(event, context):
    """`event` may carry {"revision": "<rev>"} to target a specific revision
    (e.g. a downgrade target); it defaults to upgrading to head."""
    configure_logging()

    config = Config(os.path.join(_TASK_ROOT, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(_TASK_ROOT, "alembic"))

    revision = (event or {}).get("revision", "head")
    direction = (event or {}).get("direction", "upgrade")
    if direction not in ("upgrade", "downgrade"):
        raise ValueError(f"direction must be 'upgrade' or 'downgrade', got {direction!r}")

    logger.info("migration_started", direction=direction, revision=revision)
    getattr(command, direction)(config, revision)
    logger.info("migration_finished", direction=direction, revision=revision)
    return {"status": "ok", "direction": direction, "revision": revision}
