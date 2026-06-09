import logging
import warnings

from pydantic_settings import BaseSettings

_logger = logging.getLogger(__name__)


class Settings(BaseSettings):

    # ── Environment ──────────────────────────────────────────────────
    ENVIRONMENT: str = "development"  # development / staging / production

    # ── Database ─────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///:memory:"
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Security & Auth ──────────────────────────────────────────────
    SECRET_KEY: str = "change-me"
    ENCRYPTION_KEY: str = "change-me-in-production"
    SEED_DEFAULT_PASSWORD: str = "change-me-seed-password"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24h
    ALGORITHM: str = "HS256"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        _INSECURE_KEYS = {"change-me", "change-me-in-production", "dev-secret-key-change-in-production"}
        if self.SECRET_KEY in _INSECURE_KEYS:
            if self.ENVIRONMENT == "production":
                raise RuntimeError("SECRET_KEY is insecure — refusing to start in production")
            warnings.warn(
                "SECRET_KEY is using an insecure default. Set SECRET_KEY in .env!",
                stacklevel=2,
            )
            _logger.warning("SECRET_KEY is using insecure default value")
        if self.ENCRYPTION_KEY in {"change-me-in-production", "change-me"}:
            if self.ENVIRONMENT == "production":
                raise RuntimeError("ENCRYPTION_KEY is insecure — refusing to start in production")
            _logger.warning("ENCRYPTION_KEY is using insecure default value")

    # ── Storage ──────────────────────────────────────────────────────
    UPLOAD_DIR: str = "./uploads"
    STORAGE_ROOT: str = "./storage"  # scanned images from paper-seg
    MAX_UPLOAD_SIZE_MB: int = 10

    # ── Logging ──────────────────────────────────────────────────────
    LOG_LEVEL: str = "DEBUG"
    LOG_DIR: str = "./logs"
    LOG_FILE_LEVEL: str = "INFO"

    # ── CORS ─────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # ── LLM (shared AI grading + AI Agent) ───────────────────────────
    LLM_API_URL: str = "http://localhost:8100"
    LLM_API_KEY: str = "not-needed-for-local-proxy"
    LLM_MODEL: str = "gemini-3-pro-preview"
    LLM_SLOT: str = "grading-vision"
    LLM_TIMEOUT: int = 180
    LLM_MAX_RETRIES: int = 3

    # ── Gemini Official API ──────────────────────────────────────────
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3-flash-preview"
    DEEPSEEK_API_KEY: str = ""

    # ── Vertex AI ────────────────────────────────────────────────────
    VERTEX_AI_PROJECT: str = ""
    VERTEX_AI_LOCATION: str = "global"

    # ── Grading ──────────────────────────────────────────────────────
    GRADING_BATCH_SIZE: int = 40

    # ── AI Agent ─────────────────────────────────────────────────────
    TIER_CONTEXT_THRESHOLDS: list[int] = [100_000, 30_000]
    MODEL_ROUTER_ADVANCED_KEYWORDS: list[str] | None = None  # None = use code defaults
    AI_SESSION_TTL: int = 7200  # seconds
    AI_AGENT_PROVIDER: str = "coze"  # coze / current_pydantic
    AI_AGENT_FALLBACK_PROVIDER: str = "current_pydantic"
    AI_COZE_ENABLED: bool = False
    AI_COZE_API_BASE: str = "http://localhost:8888"
    AI_COZE_BOT_ID: str = ""
    AI_COZE_API_TOKEN: str = ""
    AI_COZE_TIMEOUT: int = 120
    AI_COZE_TOOL_ALLOWLIST: list[str] = [
        "get_exam_list",
        "get_exam_summary",
        "get_class_report",
        "get_class_list",
        "get_knowledge_tree",
        "list_homework_tasks",
        "get_homework_stats",
        "generate_comment",
    ]
    AI_TOOL_GATEWAY_PUBLIC_BASE: str = ""
    AI_TOOL_GATEWAY_TOKEN: str = ""
    AI_TOOL_GATEWAY_HTTP_ENABLED: bool = False

    # ── Knowledge Base ───────────────────────────────────────────────
    KNOWLEDGE_BASE_DIR: str = "./edu-knowledge-base/subjects/biology_senior"
    KNOWLEDGE_ENABLED: bool = True
    KNOWLEDGE_DB_PATH: str = "./edu-knowledge-base/knowledge.db"
    KNOWLEDGE_DRAFT_VISIBLE: bool = True  # 宽限期：True=draft 对所有角色可见

    # ── Paper Skill ──────────────────────────────────────────────────
    PAPER_SKILL_URL: str = "http://localhost:9103"

    model_config = {"env_file": ".env", "extra": "ignore"}


def get_settings() -> Settings:
    return Settings()


settings = get_settings()
