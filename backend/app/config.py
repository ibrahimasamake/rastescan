"""Settings, read from environment variables (see backend/.env.example)."""
import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _list(name: str, default: str) -> list[str]:
    return [v.strip() for v in os.getenv(name, default).split(",") if v.strip()]


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


@dataclass(frozen=True)
class Settings:
    # "bedrock", "groq" or "ollama" for real inspections. "fake" returns canned results for UI work and tests only.
    ai_mode: str = field(default_factory=lambda: _env("AI_MODE", "bedrock"))
    aws_region: str = field(default_factory=lambda: _env("AWS_REGION", "ap-south-1"))
    # Region for Bedrock calls only. Defaults to aws_region; set it when Bedrock works in a different region.
    bedrock_region: str = field(default_factory=lambda: _env("BEDROCK_REGION") or _env("AWS_REGION", "ap-south-1"))
    # Nova model or inference profile id, e.g. "apac.amazon.nova-pro-v1:0" or "eu.amazon.nova-pro-v1:0".
    bedrock_model_id: str = field(default_factory=lambda: _env("BEDROCK_MODEL_ID", "apac.amazon.nova-pro-v1:0"))
    groq_api_key: str = field(default_factory=lambda: _env("GROQ_API_KEY"))
    groq_model: str = field(default_factory=lambda: _env("GROQ_MODEL", "qwen/qwen3.8-27b"))
    ollama_url: str = field(default_factory=lambda: _env("OLLAMA_URL", "http://localhost:11434"))
    ollama_model: str = field(default_factory=lambda: _env("OLLAMA_MODEL", "qwen2.5vl:7b"))
    # The separate YOLO road-damage detector (services/yolo).
    yolo_url: str = field(default_factory=lambda: _env("YOLO_URL", "http://localhost:8020"))
    s3_bucket: str = field(default_factory=lambda: _env("S3_BUCKET"))
    data_dir: Path = field(default_factory=lambda: Path(_env("DATA_DIR", str(REPO_ROOT / "backend" / "data"))))
    web_dist: Path = field(default_factory=lambda: Path(_env("WEB_DIST", str(REPO_ROOT / "web" / "dist"))))
    prompt_file: Path = field(default_factory=lambda: Path(_env("PROMPT_FILE", str(REPO_ROOT / "prompts" / "inspection-prompt.md"))))
    wards_file: Path = field(default_factory=lambda: Path(_env("WARDS_FILE", str(REPO_ROOT / "data" / "wards.geojson"))))
    # Shown in the portal header. Never use a real government's name or emblem here without permission.
    site_name: str = field(default_factory=lambda: _env("SITE_NAME", "Municipal Road Services"))
    public_base_url: str = field(default_factory=lambda: _env("PUBLIC_BASE_URL").rstrip("/"))
    timezone: str = field(default_factory=lambda: _env("TIMEZONE", "Asia/Kolkata"))
    # Officer accounts. The admin is created on first start if no officer exists yet.
    admin_email: str = field(default_factory=lambda: _env("ADMIN_EMAIL"))
    admin_password: str = field(default_factory=lambda: _env("ADMIN_PASSWORD"))
    admin_name: str = field(default_factory=lambda: _env("ADMIN_NAME", "Administrator"))
    # Signs session tokens. If empty, a random key is generated once and kept in DATA_DIR/secret.key.
    secret_key: str = field(default_factory=lambda: _env("SECRET_KEY"))
    session_hours: int = field(default_factory=lambda: int(_env("SESSION_HOURS", "12")))
    cookie_secure: bool = field(default_factory=lambda: _env("COOKIE_SECURE", "auto") != "false")
    # Shared PIN kept as a fallback for the expo demo. Leave empty to require officer accounts.
    dashboard_pin: str = field(default_factory=lambda: _env("DASHBOARD_PIN"))
    smtp_host: str = field(default_factory=lambda: _env("SMTP_HOST"))
    smtp_port: int = field(default_factory=lambda: int(_env("SMTP_PORT", "587")))
    smtp_user: str = field(default_factory=lambda: _env("SMTP_USER"))
    smtp_password: str = field(default_factory=lambda: _env("SMTP_PASSWORD"))
    smtp_from: str = field(default_factory=lambda: _env("SMTP_FROM"))
    max_upload_mb: int = field(default_factory=lambda: int(_env("MAX_UPLOAD_MB", "8")))
    reports_per_hour: int = field(default_factory=lambda: int(_env("REPORTS_PER_HOUR", "30")))
    logins_per_15min: int = field(default_factory=lambda: int(_env("LOGINS_PER_15MIN", "10")))
    merge_radius_m: float = field(default_factory=lambda: float(_env("MERGE_RADIUS_M", "15")))
    cors_origins: list[str] = field(default_factory=lambda: _list(
        "CORS_ORIGINS", "https://localhost,http://localhost,capacitor://localhost,http://localhost:5173"))
