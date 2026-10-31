"""Configuration, read once at startup. The rest of the code imports `settings`."""

from functools import cached_property
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # process
    app_env: str = "development"
    port: int = 4000
    app_url: str = "http://localhost:5173"
    log_level: str = "info"

    # database
    database_url: str
    database_url_direct: str | None = None
    db_pool_size: int = 20  # per process (API and worker each); RDS allows far more. Chat no longer pins one per answer

    # auth
    jwt_secret: str = Field(min_length=32)
    access_token_ttl_min: int = 15
    refresh_token_ttl_days: int = 30
    google_client_id: str | None = None
    google_client_secret: str | None = None
    x_client_id: str | None = None
    x_client_secret: str | None = None

    # mail
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    mail_from: str = "Stash <no-reply@localhost>"

    # save by email: mail to save+<token>@INBOUND_EMAIL_DOMAIN is posted to /api/v1/inbound/email by a forwarder
    # (see deploy/inbound-email-worker.js) that sends INBOUND_SECRET in the X-Inbound-Secret header
    inbound_email_domain: str | None = None
    inbound_secret: str | None = None

    # AI (names match the reference .env)
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    voyager_api_key: str | None = None
    embed_model: str = "voyage-4"
    rerank_model: str = "rerank-3-lite"
    ai_enabled: bool = True
    ai_monthly_token_budget: int = 300_000  # every account, every AI task, counted from ai_requests
    chat_requests_per_hour: int = 30
    # One model per agent, all on Bedrock Mantle. Chosen by benchmark on 2026-10-31 (see AI.md).
    chat_model: str = "zai.glm-5"  # writer: grounded answer with citations
    writer_fallback_model: str = "moonshotai.kimi-k2.5"
    fast_model: str = "zai.glm-4.7-flash"  # planner, evidence judge, verifier, memory
    reader_model: str = "moonshotai.kimi-k2.5"  # understands links and long cards
    vision_model: str = "qwen.qwen3-vl-235b-a22b-instruct"  # image caption + visible text
    moderator_model: str = "openai.gpt-oss-safeguard-120b"  # policy-based content safety
    moderation_model_enabled: bool = True
    ingest_debounce_s: float = 8.0  # wait for typing to settle before the reader runs
    ingest_ai_daily_cards: int = 400  # reader/vision calls per user per day; indexing continues without them
    answer_cache_hours: int = 24
    memory_enabled: bool = True

    # content safety: word list + moderator model (text) and vision model (images), all on Mantle
    aws_region: str = "ap-south-1"  # S3
    safety_required: bool = True

    # uploads
    s3_bucket: str | None = None
    upload_max_bytes: int = 10 * 1024 * 1024
    user_storage_quota_mb: int = 500
    local_upload_dir: str = ".uploads"
    # S3-compatible storage in development (custom endpoint + keys). On EC2 leave these unset: the instance role
    # and the regional AWS endpoint are used.
    aws_endpoint_url_s3: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None

    @model_validator(mode="after")
    def _check(self) -> "Settings":
        if self.is_production:
            missing = [
                name
                for name, value in {
                    "SMTP_HOST": self.smtp_host,
                    "S3_BUCKET": self.s3_bucket,
                    "OPENAI_API_KEY": self.openai_api_key,  # the moderator needs it: safety is required
                    "OPENAI_BASE_URL": self.openai_base_url,
                }.items()
                if not value
            ]
            if missing:
                raise ValueError(f"missing required production settings: {', '.join(missing)}")
            if not self.safety_required:
                raise ValueError("SAFETY_REQUIRED must be true in production")
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def cookie_secure(self) -> bool:
        return self.app_url.startswith("https://")

    @property
    def app_origin(self) -> str:
        parts = urlsplit(self.app_url)
        return f"{parts.scheme}://{parts.netloc}"

    @property
    def mail_enabled(self) -> bool:
        return bool(self.smtp_host)

    @property
    def chat_ai_configured(self) -> bool:
        return self.ai_enabled and bool(self.openai_api_key and self.openai_base_url)

    @property
    def embeddings_configured(self) -> bool:
        return self.ai_enabled and bool(self.voyager_api_key)

    @cached_property
    def async_database_url(self) -> tuple[str, dict]:
        """Neon gives `postgres://…?sslmode=require`; asyncpg wants `postgresql+asyncpg://` and an ssl arg."""
        return _asyncpg_url(self.database_url)


def _asyncpg_url(url: str) -> tuple[str, dict]:
    parts = urlsplit(url)
    scheme = "postgresql+asyncpg"
    query = dict(parse_qsl(parts.query))
    connect_args: dict = {}
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)
    if sslmode in {"require", "verify-ca", "verify-full"}:
        connect_args["ssl"] = "require"
    return urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)), connect_args


settings = Settings()  # type: ignore[call-arg]
