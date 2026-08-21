"""Guards the assumptions the zip-packaged Lambda deployment rests on.

The deployment ships `requirements-lambda.txt` (a deliberate subset of
`requirements.txt`) as a Lambda layer. Two things silently break that:

  1. A pin drifting between the two files - the app would then run against a
     different dependency version in AWS than it was tested against locally.
  2. A new third-party import appearing in app/ without being added to
     requirements-lambda.txt - which fails at *runtime on Lambda*, as an
     ImportError on a cold start, long after the tests passed.

Neither needs AWS or a built artifact to check, so they're checked here.
"""

import ast
import re
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
APP_DIR = BACKEND_DIR / "app"

# Distribution name (as pinned) -> the module name you actually import.
IMPORT_NAMES = {
    "pyjwt": "jwt",
    "python-multipart": "multipart",
    "email-validator": "email_validator",
    "pydantic-settings": "pydantic_settings",
}

# Already present in the AWS Lambda Python runtime, so deliberately not bundled:
# botocore's service definitions would add roughly 90 MB unzipped.
RUNTIME_PROVIDED = {"boto3", "botocore"}

# Imported directly by our code but intentionally not pinned separately: FastAPI
# cannot function without Starlette (it *is* Starlette underneath), so it is
# always in the layer, and pinning it independently would only create a way for
# it to conflict with the range FastAPI itself requires.
TRANSITIVE_GUARANTEED = {"starlette"}

# The local/docker-compose notification queue. Excluded from the Lambda layer
# because the AWS deployment uses SQS - which is only safe as long as no module
# a Lambda handler imports pulls them in (see the reachability test below).
LOCAL_ONLY = {"arq", "redis"}

# The Lambda entrypoints, as configured in infra/terraform/lambda.tf.
HANDLER_MODULES = [
    "app.lambda_handler",
    "app.notification_worker_handler",
    "app.migration_handler",
    "app.seed_handler",
]


def _parse_pins(path: Path) -> dict[str, str]:
    pins: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([A-Za-z0-9_.\-]+)(\[[^\]]+\])?==(.+)$", line)
        assert match, f"unparsed requirement line in {path.name}: {line!r}"
        pins[match.group(1).lower()] = match.group(3)
    return pins


def test_lambda_pins_match_main_requirements():
    main = _parse_pins(BACKEND_DIR / "requirements.txt")
    lambda_pins = _parse_pins(BACKEND_DIR / "requirements-lambda.txt")

    assert lambda_pins, "requirements-lambda.txt parsed as empty"
    missing = sorted(set(lambda_pins) - set(main))
    assert not missing, f"pinned for Lambda but absent from requirements.txt: {missing}"

    drifted = {
        name: (main[name], version)
        for name, version in lambda_pins.items()
        if main[name] != version
    }
    assert not drifted, (
        "requirements-lambda.txt must never disagree with requirements.txt "
        f"(name: (local, lambda)): {drifted}"
    )


def _third_party_imports() -> dict[str, set[Path]]:
    """Top-level third-party modules imported anywhere under app/, and where."""
    found: dict[str, set[Path]] = {}
    for path in sorted(APP_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                # level > 0 is a relative import, i.e. our own code.
                roots = [node.module.split(".")[0]] if node.module and node.level == 0 else []
            else:
                continue
            for root in roots:
                if root == "app" or root in sys.stdlib_module_names:
                    continue
                found.setdefault(root, set()).add(path)
    return found


def test_every_third_party_import_is_available_on_lambda():
    pins = _parse_pins(BACKEND_DIR / "requirements-lambda.txt")
    packaged = {IMPORT_NAMES.get(name, name.replace("-", "_")) for name in pins}
    available = packaged | RUNTIME_PROVIDED | TRANSITIVE_GUARANTEED | LOCAL_ONLY

    imports = _third_party_imports()
    unavailable = {
        module: sorted(str(p.relative_to(BACKEND_DIR)) for p in paths)
        for module, paths in imports.items()
        if module not in available
    }
    assert not unavailable, (
        "these modules are imported by app/ but would not exist on Lambda - add them to "
        f"requirements-lambda.txt (and requirements.txt): {unavailable}"
    )


def _module_path(module: str) -> Path | None:
    relative = Path(*module.split(".")[1:])  # strip the leading "app"
    for candidate in (APP_DIR / relative.with_suffix(".py"), APP_DIR / relative / "__init__.py"):
        if candidate.exists():
            return candidate
    return None


def _module_scope_imports(path: Path) -> tuple[set[str], set[str]]:
    """(our own modules, third-party roots) imported at import time by this file.

    Module scope only - deliberately not ast.walk - because an import inside a
    function body is not executed when the module is loaded, which is exactly the
    distinction this file exists to enforce.
    """
    own: set[str] = set()
    third_party: set[str] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                (own if alias.name.startswith("app.") else third_party).add(
                    alias.name if alias.name.startswith("app.") else alias.name.split(".")[0]
                )
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            if node.module == "app" or node.module.startswith("app."):
                # `from app.core import database` imports app.core.database too.
                own.add(node.module)
                own.update(f"{node.module}.{alias.name}" for alias in node.names)
            else:
                third_party.add(node.module.split(".")[0])
    return own, third_party


def test_nothing_a_handler_imports_needs_the_excluded_dependencies():
    """arq and redis must not be reachable from any Lambda entrypoint's imports.

    They're excluded from the layer, so if a module a handler loads pulled one in
    at import time, every cold start would die with an ImportError. app/worker.py
    and app/core/redis.py legitimately import arq - they're the local arq path,
    reached only through the lazy import inside ArqNotificationQueue.enqueue - so
    the check has to follow the actual import graph rather than scan every file.
    """
    reachable: dict[str, Path] = {}
    queue = list(HANDLER_MODULES)
    offenders: list[str] = []

    while queue:
        module = queue.pop()
        if module in reachable:
            continue
        path = _module_path(module)
        if path is None:  # e.g. a symbol imported from a package, not a module
            continue
        reachable[module] = path

        own, third_party = _module_scope_imports(path)
        for name in sorted(third_party & LOCAL_ONLY):
            offenders.append(f"{path.relative_to(BACKEND_DIR).as_posix()} imports {name} at module scope")
        queue.extend(own)

    # Sanity-check the traversal itself: if this ever collapses to just the
    # handlers, the test would pass vacuously.
    assert "app.main" in reachable and "app.core.database" in reachable, sorted(reachable)
    assert "app.core.redis" not in reachable, (
        "app.core.redis became reachable from a handler at import time - it imports arq, "
        "which is not in the Lambda layer"
    )
    assert not offenders, "; ".join(offenders)
