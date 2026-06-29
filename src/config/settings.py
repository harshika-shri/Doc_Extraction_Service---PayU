from pydantic import AliasChoices, Field, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str | None = Field(default=None, validation_alias="DATABASE_URL")
    POSTGRES_USER: str = "db"
    POSTGRES_PASSWORD: str = "tiger"
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "PayU_db"

    JWT_SECRET_KEY: str = Field(default="", validation_alias="JWT_SECRET_KEY")
    JWT_ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    GMAIL_TOKEN_PATH: str = "secrets/token.json"
    GMAIL_ATTACHMENT_DOWNLOAD_DIR: str = "downloads/attachments"
    PO_UPLOAD_DIR: str = "uploads/purchase_orders"

    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_STREAM_NAME: str = "extraction.events"

    CELERY_TASK_DEFAULT_QUEUE: str = "extraction"
    CELERY_TASK_MAX_RETRIES: int = 5
    CELERY_TASK_RETRY_BACKOFF_SECONDS: int = 60

    LLAMA_CLOUD_API_KEY: str = Field(
        default="",
        validation_alias=AliasChoices(
            "LLAMA_CLOUD_API_KEY",
            "LLAMAPARSE_API_KEY",
        ),
    )
    LLAMA_CLOUD_API_BASE_URL: str = Field(
        default="https://api.cloud.llamaindex.ai",
        validation_alias="LLAMA_CLOUD_API_BASE_URL",
    )
    LLAMA_CLOUD_PROJECT_ID: str = Field(
        default="",
        validation_alias="LLAMA_CLOUD_PROJECT_ID",
    )
    LLAMA_EXTRACT_TIER: str = Field(
        default="cost_effective",
        validation_alias="LLAMA_EXTRACT_TIER",
    )
    LLAMA_EXTRACT_POLL_INTERVAL_SECONDS: float = Field(
        default=2.0,
        validation_alias="LLAMA_EXTRACT_POLL_INTERVAL_SECONDS",
    )
    LLAMA_EXTRACT_POLL_MAX_ATTEMPTS: int = Field(
        default=90,
        validation_alias="LLAMA_EXTRACT_POLL_MAX_ATTEMPTS",
    )

    GROQ_API_KEY: str = Field(
        default="",
        validation_alias="GROQ_API_KEY",
    )
    GROQ_API_BASE_URL: str = Field(
        default="https://api.groq.com/openai/v1",
        validation_alias="GROQ_API_BASE_URL",
    )
    GROQ_LLM_MODEL: str = Field(
        default="llama-3.1-8b-instant",
        validation_alias="GROQ_LLM_MODEL",
    )
    GROQ_LLM_MAX_TOKENS: int = Field(
        default=1500,
        validation_alias="GROQ_LLM_MAX_TOKENS",
    )

    SENDGRID_API_KEY: str = Field(
        default="",
        validation_alias="SENDGRID_API_KEY",
    )
    SENDGRID_FROM_EMAIL: str = Field(
        default="",
        validation_alias="SENDGRID_FROM_EMAIL",
    )

    @field_validator(
        "LLAMA_CLOUD_API_KEY",
        "LLAMA_CLOUD_PROJECT_ID",
        "GROQ_API_KEY",
        mode="before",
    )
    @classmethod
    def strip_string_values(
        cls,
        value: object,
    ) -> object:
        if isinstance(value, str):
            return value.strip()

        return value

    @computed_field
    @property
    def CELERY_BROKER_URL(self) -> str:
        return (
            f"redis://{self.REDIS_HOST}:"
            f"{self.REDIS_PORT}/{self.REDIS_DB}"
        )

    @computed_field
    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        return self.CELERY_BROKER_URL

    @model_validator(mode="after")
    def build_database_url(self) -> "Settings":
        if not self.DATABASE_URL:
            self.DATABASE_URL = (
                f"postgresql+asyncpg://"
                f"{self.POSTGRES_USER}:"
                f"{self.POSTGRES_PASSWORD}@"
                f"{self.POSTGRES_HOST}:"
                f"{self.POSTGRES_PORT}/"
                f"{self.POSTGRES_DB}"
            )

        return self


settings = Settings()
