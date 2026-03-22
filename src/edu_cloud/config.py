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
    PLATFORM_API_KEY_SALT: str = "change-me"

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

    # Logging
    LOG_LEVEL: str = "DEBUG"
    LOG_DIR: str = "./logs"
    LOG_FILE_LEVEL: str = "INFO"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # LLM (shared AI grading)
    LLM_API_URL: str = ""
    LLM_API_KEY: str = ""
    LLM_MODEL: str = ""
    LLM_TIMEOUT: int = 120
    LLM_MAX_RETRIES: int = 3

    model_config = {"env_file": ".env", "extra": "ignore"}


def get_settings() -> Settings:
    return Settings()


settings = get_settings()
