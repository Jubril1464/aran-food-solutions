from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Agric Procurement Platform"
    environment: str = "development"
    api_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://agric:agric@localhost:5432/agric"
    db_ssl_required: bool = False

    redis_url: str = "redis://localhost:6379/0"

    # Queue: "redis" (local/docker-compose, via arq) or "sqs" (AWS Lambda deployment)
    queue_backend: str = "redis"
    sqs_notification_queue_url: str = ""

    # Unlike the credential vars, reading Lambda's own injected AWS_REGION here
    # is exactly what we want: it is the region the function runs in, which is
    # also where its SQS queue lives. Blank off-Lambda, where boto3 falls back
    # to its normal resolution chain (~/.aws/config, AWS_DEFAULT_REGION).
    aws_region: str = ""

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14

    cors_origins: list[str] = ["http://localhost:5173"]

    # SameSite policy for the refresh-token cookie. "lax" is right when the API
    # and the frontend share an origin (local dev). The AWS deployment serves
    # the frontend from CloudFront and the API from API Gateway — different
    # registrable domains, so the browser treats every API call as cross-site
    # and drops a Lax cookie, breaking silent refresh. Terraform sets this to
    # "none" for that reason; "none" always implies Secure.
    refresh_cookie_samesite: str = "lax"

    # Storage: "local" or "s3"
    storage_backend: str = "local"
    local_storage_path: str = "storage/uploads"
    local_storage_public_url: str = "/static/uploads"
    s3_bucket: str = ""
    s3_region: str = "eu-west-1"
    s3_endpoint_url: str = ""
    # Deliberately NOT named aws_access_key_id/aws_secret_access_key: pydantic
    # reads env vars case-insensitively, and AWS_ACCESS_KEY_ID /
    # AWS_SECRET_ACCESS_KEY are *injected by Lambda itself* with the execution
    # role's temporary credentials. Fields with those names would silently pick
    # them up and hand boto3 a key+secret with no AWS_SESSION_TOKEN, which AWS
    # rejects. Leave these blank on Lambda so boto3 resolves the role itself;
    # set them only for a static-credential setup (e.g. local MinIO).
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""

    # Max accepted upload size. Lambda's synchronous invocation payload caps at
    # 6 MB and API Gateway at 10 MB, and the request arrives base64-encoded
    # (~33% overhead), so anything above ~4 MB fails at the gateway with an
    # opaque error before FastAPI ever sees it. Reject it ourselves instead.
    max_upload_size_mb: float = 4.0

    # Email: "console" or "smtp"
    email_backend: str = "console"
    email_from: str = "no-reply@agric.local"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""

    # Paystack
    paystack_secret_key: str = ""
    paystack_public_key: str = ""
    paystack_base_url: str = "https://api.paystack.co"

    frontend_url: str = "http://localhost:5173"

    # First-admin bootstrap, consumed only by app/seed_handler.py. /auth/register
    # deliberately only ever creates customers, so a deployed environment needs
    # this one-time step to have an administrator at all. Terraform sets these on
    # the seed function; the password is generated if not supplied.
    seed_admin_email: str = "admin@agric.local"
    seed_admin_password: str = ""
    seed_admin_phone: str = "+2348000000000"
    seed_demo_data: bool = True

    delivery_fee: float = 1000.0
    service_fee_percent: float = 2.5


@lru_cache
def get_settings() -> Settings:
    return Settings()
