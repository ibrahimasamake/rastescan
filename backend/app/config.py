"""Settings, read from environment variables (see backend/.env.example)."""
import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _list(name: str, default: str) -> list[str]:
    return [v.strip() for v in os.getenv(name, default).split(",") if v.strip()]


@dataclass(frozen=True)
class Settings:
    # "bedrock" in production. "fake" returns canned results for local UI work and tests only.
    ai_mode: str = field(default_factory=lambda: os.getenv("AI_MODE", "bedrock"))
    aws_region: str = field(default_factory=lambda: os.getenv("AWS_REGION", "ap-south-1"))
    # Region for Bedrock calls only. Defaults to aws_region; set it when Bedrock is enabled in a different region.
    bedrock_region: str = field(default_factory=lambda: os.getenv("BEDROCK_REGION") or os.getenv("AWS_REGION", "ap-south-1"))
    # Nova model or inference profile id, e.g. "apac.amazon.nova-pro-v1:0" or "amazon.nova-lite-v1:0".
    bedrock_model_id: str = field(default_factory=lambda: os.getenv("BEDROCK_MODEL_ID", "apac.amazon.nova-pro-v1:0"))
    s3_bucket: str = field(default_factory=lambda: os.getenv("S3_BUCKET", ""))
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("DATA_DIR", str(REPO_ROOT / "backend" / "data"))))
    web_dist: Path = field(default_factory=lambda: Path(os.getenv("WEB_DIST", str(REPO_ROOT / "web" / "dist"))))
    prompt_file: Path = field(default_factory=lambda: Path(os.getenv("PROMPT_FILE", str(REPO_ROOT / "prompts" / "inspection-prompt.md"))))
    dashboard_pin: str = field(default_factory=lambda: os.getenv("DASHBOARD_PIN", ""))
    max_upload_mb: int = field(default_factory=lambda: int(os.getenv("MAX_UPLOAD_MB", "8")))
    reports_per_hour: int = field(default_factory=lambda: int(os.getenv("REPORTS_PER_HOUR", "30")))
    merge_radius_m: float = field(default_factory=lambda: float(os.getenv("MERGE_RADIUS_M", "15")))
    cors_origins: list[str] = field(default_factory=lambda: _list(
        "CORS_ORIGINS", "https://localhost,http://localhost,capacitor://localhost,http://localhost:5173"))
