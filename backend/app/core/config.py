import json
from typing import List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_SECRET_KEY = "insecure_dev_secret_key_change_in_production"


class Settings(BaseSettings):
    PROJECT_NAME: str = "VSPL Material Management & Costing System"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # Security & CORS
    SECRET_KEY: str = DEFAULT_SECRET_KEY
    # "none" (fail-closed: all protected routes 401) or "dev" (development/test only).
    # The production provider (JWT / Entra ID / session) is pending IT Head approval.
    AUTH_PROVIDER: str = "dev"
    # Google Identity-Aware Proxy (AUTH_PROVIDER=iap): the expected token audience, for Cloud Run
    # "/projects/<PROJECT_NUMBER>/locations/<REGION>/services/<SERVICE>", and the JSON map of
    # e-mail to application role. See app/core/iap_auth.py.
    IAP_AUDIENCE: str = ""
    IAP_ROLE_MAP: str = ""
    # Google Identity Platform (AUTH_PROVIDER=identity): admin-created e-mail + password users and admin approval.
    # IDENTITY_PROJECT_ID is the Google Cloud project id that owns the Identity Platform tenant; IDENTITY_API_KEY is
    # its public web API key (sent to the browser by /auth/status; restrict it in the console).
    IDENTITY_PROJECT_ID: str = ""
    IDENTITY_API_KEY: str = ""
    # Reserved for Microsoft sign-in; the UI only offers it when true.
    MICROSOFT_SIGNIN_ENABLED: bool = False
    # Comma-separated or JSON list of e-mails that become Admin on their first successful sign-in when no user
    # record exists yet (used once, to create the first administrator).
    BOOTSTRAP_ADMIN_EMAILS: str = ""
    # Document attachments (for example on a GRN). "local" keeps files in ATTACHMENT_LOCAL_DIR (development);
    # "gcs" keeps them in the private Cloud Storage bucket ATTACHMENT_BUCKET (production).
    ATTACHMENT_STORAGE: str = "local"
    ATTACHMENT_LOCAL_DIR: str = "data/attachments"
    ATTACHMENT_BUCKET: str = ""
    ATTACHMENT_MAX_MB: int = 10
    ATTACHMENT_MAX_PER_DOCUMENT: int = 10
    # A GRN cannot be approved (stock added) until the Quality role has passed it.
    GRN_QA_REQUIRED: bool = True
    # Interactive API documentation is off in production unless explicitly enabled.
    ENABLE_API_DOCS: bool | None = None
    # Directory with the built frontend. When set, the backend serves it (single-origin deployment).
    FRONTEND_DIST_DIR: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    ALLOWED_ORIGINS: Union[List[str], str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, str) and v.startswith("["):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except Exception:
                pass
        return v if isinstance(v, list) else ["*"]

    # PostgreSQL Database Settings
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "vspl_material_management"
    DATABASE_URL: str | None = None

    @property
    def sync_database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        # Using psycopg 3 for PostgreSQL connectivity with SQLAlchemy 2.x
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # Business Constants (Mandatory per VSPL Business Rules)
    COSTING_START_DATE: str = "2026-10-12"
    # Comma-separated document types where the creator may not approve their own document.
    # Provisional default (pending management sign-off); supported: GRN, ISSUE, WASTE, PHYSICAL_AUDIT, ALIAS.
    MAKER_CHECKER_DOCUMENTS: str = "GRN,ISSUE,WASTE,PHYSICAL_AUDIT"
    ALLOW_NEGATIVE_STOCK: bool = False  # Strict default per VSPL inventory governance

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )


settings = Settings()
