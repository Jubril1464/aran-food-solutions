import secrets
from datetime import datetime, timezone


def generate_order_number() -> str:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    suffix = secrets.token_hex(3).upper()
    return f"ORD-{today}-{suffix}"


def slugify(value: str) -> str:
    return "-".join(value.strip().lower().split())
