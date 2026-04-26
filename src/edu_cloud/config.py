import logging
import warnings

from pydantic_settings import BaseSettings

_logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # Database (PostgreSQL required for cloud)
    DATABASE_URL: str = "sqlite+aiosqlite:///:memory:"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security
    SECRET_KEY: str = "change-me"
    ENCRYPTION_KEY: str = "change-me-in-production"
    SEED_DEFAULT_PASSWORD: str = "change-me-seed-password"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.SECRET_KEY == "change-me":
            warnings.warn(
                "SECRET_KEY is using default value 'change-me'. "
                "Set SECRET_KEY in .env for production!",
                stacklevel=2,
            )
            _logger.warning("SECRET_KEY is using insecure default value")

    # JWT
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24h
    ALGORITHM: str = "HS256"

    # File storage
    UPLOAD_DIR: str = "./uploads"
    STORAGE_ROOT: str = "./storage"  # scanned images from paper-seg
    MAX_UPLOAD_SIZE_MB: int = 10

    # Logging
    LOG_LEVEL: str = "DEBUG"
    LOG_DIR: str = "./logs"
    LOG_FILE_LEVEL: str = "INFO"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # LLM (shared AI grading + AI Agent)
    LLM_API_URL: str = "http://localhost:8100"
    LLM_API_KEY: str = "not-needed-for-local-proxy"
    LLM_MODEL: str = "gemini-3-pro-preview"
    LLM_SLOT: str = "grading-vision"
    LLM_TIMEOUT: int = 180
    LLM_MAX_RETRIES: int = 3

    # AI Grading batch concurrency
    GRADING_BATCH_SIZE: int = 20

    # AI Agent — capability tiers
    TIER_CONTEXT_THRESHOLDS: list[int] = [100_000, 30_000]
    MODEL_ROUTER_ADVANCED_KEYWORDS: list[str] | None = None  # None = use code defaults

    # AI Agent
    AI_SESSION_TTL: int = 7200  # seconds

    # Knowledge base
    KNOWLEDGE_BASE_DIR: str = "./edu-knowledge-base/subjects/biology_senior"
    KNOWLEDGE_ENABLED: bool = True
    KNOWLEDGE_DB_PATH: str = "./edu-knowledge-base/knowledge.db"
    KNOWLEDGE_DRAFT_VISIBLE: bool = True  # 宽限期：True=draft 对所有角色可见

    # Paper-skill
    PAPER_SKILL_URL: str = "http://localhost:9103"

    model_config = {"env_file": ".env", "extra": "ignore"}


def get_settings() -> Settings:
    return Settings()


settings = get_settings()
